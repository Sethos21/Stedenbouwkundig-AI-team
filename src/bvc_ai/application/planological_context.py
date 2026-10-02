"""A06 V1: deterministic interpretation of controlled, structured TESTDATA only.

Trusted local callers pin the current input hash. Downstream agents receive JSON,
never this service or its spatial reader. Hashes are not authentication.
"""
from copy import deepcopy
import hashlib
import json
import math

from bvc_ai.application.spatial_context import SpatialContextService


def input_hash(value):
    """Canonical JSON SHA-256, also used for source, rule and output bindings."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _fields(value, required, optional=()):
    if (type(value) is not dict or not set(required) <= set(value)
            or set(value) - set(required) - set(optional)):
        raise ValueError('Invalid planological fields')


def _text(value):
    if type(value) is not str or not value.strip():
        raise ValueError('Nonempty literal text required')


def _choice(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError('Invalid planological enum')


def _texts(value):
    if type(value) is not list:
        raise ValueError('Literal text list required')
    for item in value:
        _text(item)
    if len(set(value)) != len(value):
        raise ValueError('Duplicate reference or uncertainty')


def _target(target, spatial):
    _fields(target, ('kind', 'scope_contracts', 'record_refs', 'geometry_refs'))
    _choice(target['kind'], ('FULL_ANALYSIS_SCOPE', 'A02_GEOMETRY', 'SOURCE_OBJECT'))
    _texts(target['scope_contracts'])
    _texts(target['geometry_refs'])
    refs = target['record_refs']
    if type(refs) is not list:
        raise ValueError('Record reference list required')
    for ref in refs:
        if type(ref) is not list or len(ref) != 3:
            raise ValueError('Invalid A02 record reference')
        for part in ref:
            _text(part)
    if len({tuple(r) for r in refs}) != len(refs):
        raise ValueError('Duplicate A02 record reference')
    scope = {s['source_contract'] for s in spatial['scope']}
    records = {tuple(p['record_ref']) for p in spatial['provenance']}
    geometries = {p['geometry_ref'] for p in spatial['provenance']}
    if (not set(target['scope_contracts']) <= scope
            or not {tuple(r) for r in refs} <= records
            or not set(target['geometry_refs']) <= geometries):
        raise ValueError('Unknown A02 applicability reference')
    kind = target['kind']
    valid = {
        'FULL_ANALYSIS_SCOPE': set(target['scope_contracts']) == scope and not refs and not target['geometry_refs'],
        'A02_GEOMETRY': bool(target['geometry_refs']) and not refs and not target['scope_contracts'],
        'SOURCE_OBJECT': bool(refs) and not target['geometry_refs'] and not target['scope_contracts'],
    }
    if not valid[kind]:
        raise ValueError('Ambiguous or empty applicability target')
    return [i for i, p in enumerate(spatial['provenance'])
            if kind == 'FULL_ANALYSIS_SCOPE'
            or (kind == 'SOURCE_OBJECT' and p['record_ref'] in refs)
            or (kind == 'A02_GEOMETRY' and p['geometry_ref'] in target['geometry_refs'])]


def _rule(rule, spatial):
    _fields(rule, ('rule_id', 'locator', 'text', 'structured', 'certainty',
                   'applicability', 'uncertainties'))
    for field in ('rule_id', 'locator', 'text'):
        _text(rule[field])
    _choice(rule['certainty'], ('EXPLICIT', 'UNCLEAR'))
    _texts(rule['uncertainties'])
    structured = rule['structured']
    _fields(structured, ('kind', 'subject'), ('quantity',))
    _choice(structured['kind'], ('BINDING', 'POLICY_AMBITION', 'NEUTRAL_INFORMATION', 'UNKNOWN'))
    _text(structured['subject'])
    if 'quantity' in structured:
        q = structured['quantity']
        _fields(q, ('value', 'unit', 'operator'))
        if type(q['value']) not in (int, float) or not math.isfinite(q['value']):
            raise ValueError('Finite numeric source quantity required')
        _text(q['unit'])
        _choice(q['operator'], ('MAXIMUM', 'MINIMUM', 'EQUALS', 'INDICATIVE'))
    applicability = rule['applicability']
    _fields(applicability, ('status', 'basis', 'target'))
    _choice(applicability['status'], ('APPLIES', 'DOES_NOT_APPLY', 'UNKNOWN'))
    # An absent basis is representable, but can never produce a constraint.
    if type(applicability['basis']) is not str:
        raise ValueError('Applicability basis must be literal text')
    return _target(applicability['target'], spatial)


def _classify(source, rule):
    reasons = [dict(code='SOURCE_UNCERTAINTY', detail=u) for u in rule['uncertainties']]
    kind = rule['structured']['kind']
    checks = (
        (source['legal_status'] == 'UNKNOWN', 'UNKNOWN_SOURCE_STATUS'),
        (rule['certainty'] != 'EXPLICIT', 'UNCLEAR_SOURCE_RULE'),
        (kind == 'UNKNOWN', 'UNKNOWN_RULE_MEANING'),
        (rule['applicability']['status'] != 'APPLIES', 'APPLICABILITY_' + rule['applicability']['status']),
        (not rule['applicability']['basis'].strip(), 'MISSING_APPLICABILITY_BASIS'),
        (kind == 'BINDING' and source['legal_status'] != 'EFFECTIVE', 'BINDING_RULE_NOT_EFFECTIVE'),
        (kind == 'BINDING' and rule['structured'].get('quantity', {}).get('operator') == 'INDICATIVE',
         'INDICATIVE_VALUE_IS_NOT_A_HARD_LIMIT'),
    )
    for condition, code in checks:
        if condition:
            reasons.append(dict(code=code))
    if reasons:
        return 'UNCERTAINTY', reasons
    return {'BINDING': 'CONSTRAINT', 'POLICY_AMBITION': 'STEERING',
            'NEUTRAL_INFORMATION': 'INFORMATION'}[kind], []


class PlanologicalContextService:
    """Read-only local service. No connector, provider, publication or approval."""

    def __init__(self, store):
        self._spatial = SpatialContextService(store)

    def build(self, spatial_context, planological_input, *, expected_input_hash):
        spatial = deepcopy(spatial_context)
        data = deepcopy(planological_input)
        self._spatial.verify(spatial)
        digest = input_hash(data)
        if digest != expected_input_hash:
            raise ValueError('Changed planological input')
        _fields(data, ('format', 'source_status', 'input_revision', 'a02_context_hash', 'sources'))
        if data['format'] != 'BVC_A06_FIXTURE_INPUT_V1' or data['source_status'] != 'TESTDATA':
            raise ValueError('A06 V1 requires controlled TESTDATA')
        _text(data['input_revision'])
        if data['a02_context_hash'] != spatial['context_hash']:
            raise ValueError('Stale A02 binding in planological input')
        if type(data['sources']) is not list or not data['sources']:
            raise ValueError('Explicit fixture sources required')
        sources, rules, identities = [], [], set()
        for source in data['sources']:
            _fields(source, ('source_id', 'source_status', 'version', 'legal_status', 'rules'))
            for field in ('source_id', 'version'):
                _text(source[field])
            if source['source_status'] != 'TESTDATA':
                raise ValueError('A06 V1 requires controlled TESTDATA sources')
            _choice(source['legal_status'], ('EFFECTIVE', 'DRAFT', 'UNKNOWN'))
            if source['source_id'] in identities:
                raise ValueError('Duplicate source identity')
            identities.add(source['source_id'])
            if type(source['rules']) is not list or not source['rules']:
                raise ValueError('Explicit source rules required')
            source_digest = input_hash(source)
            sources.append(dict(source_id=source['source_id'], source_hash=source_digest,
                                source_status=source['source_status'], version=source['version'],
                                legal_status=source['legal_status']))
            rule_ids = set()
            for rule in source['rules']:
                refs = _rule(rule, spatial)
                if rule['rule_id'] in rule_ids:
                    raise ValueError('Duplicate rule identity within source')
                rule_ids.add(rule['rule_id'])
                classification, uncertainties = _classify(source, rule)
                provenance = dict(source_id=source['source_id'], source_hash=source_digest,
                                  rule_id=rule['rule_id'], rule_hash=input_hash(rule), locator=rule['locator'],
                                  input_hash=digest, a02_context_hash=spatial['context_hash'],
                                  applicability_hash=input_hash(rule['applicability']),
                                  a02_provenance_refs=refs)
                rules.append(dict(
                    rule_identity=[source['source_id'], rule['rule_id']],
                    source_ref=source['source_id'], source_rule=deepcopy(rule),
                    applicability=deepcopy(rule['applicability']),
                    interpretation=dict(method='EXPLICIT_FIXTURE_RULE_MAPPING_V1',
                                        subject=rule['structured']['subject'],
                                        meaning={'CONSTRAINT': 'EXPLICIT_APPLICABLE_REQUIREMENT',
                                                 'STEERING': 'POLICY_AMBITION_ONLY',
                                                 'INFORMATION': 'RELEVANT_NEUTRAL_SOURCE_INFORMATION',
                                                 'UNCERTAINTY': 'NO_APPLICABLE_REQUIREMENT_ESTABLISHED'}[classification],
                                        provenance_path='rules/' + str(len(rules)) + '/provenance'),
                    classification=classification,
                    classification_provenance_path='rules/' + str(len(rules)) + '/provenance',
                    quantity=deepcopy(rule['structured'].get('quantity')),
                    uncertainties=uncertainties, provenance=provenance))
        result = dict(format='BVC_A06_PLANOLOGICAL_CONTEXT_V1', source_status='TESTDATA',
                      task_id=spatial['task_id'], a02_revision_id=spatial['revision_id'],
                      a02_context_hash=spatial['context_hash'], a02_basis_hash=spatial['basis_hash'],
                      input_revision=data['input_revision'], input_hash=digest,
                      sources=sources, rules=rules,
                      limitations=['SYNTHETIC_RULES_NOT_LEGAL_ADVICE_OR_REAL_POLICY',
                                   'APPLICABILITY_IS_EXPLICIT_FIXTURE_EVIDENCE_NOT_SPATIAL_INFERENCE',
                                   'ANALYSIS_SCOPE_IS_NOT_PROJECT_OR_LEGAL_BOUNDARY',
                                   'GEOMETRY_TARGETS_REFERENCE_EXISTING_A02_GEOMETRIES_ONLY',
                                   'QUANTITIES_ARE_LITERAL_SOURCE_VALUES_NOT_UNCONDITIONAL_REQUIREMENTS',
                                   'DOES_NOT_APPLY_IS_RETAINED_AS_UNCERTAINTY_NOT_A_CONSTRAINT'])
        self._spatial.verify(spatial)
        result['context_hash'] = input_hash(result)
        return result

    def verify(self, context, spatial_context, planological_input, *, expected_input_hash):
        current = self.build(spatial_context, planological_input, expected_input_hash=expected_input_hash)
        if input_hash(current) != input_hash(context):
            raise ValueError('Changed planological context')
        return current
