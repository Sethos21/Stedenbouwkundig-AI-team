"""Controlled synthetic A06 rules, never official policy or legal source data."""
from copy import deepcopy


def planological_fixture(spatial):
    full = dict(kind='FULL_ANALYSIS_SCOPE',
                scope_contracts=[s['source_contract'] for s in spatial['scope']],
                record_refs=[], geometry_refs=[])
    pand = next(p for p in spatial['provenance'] if p['record_ref'][0] == 'BAG/pand')
    geometry = dict(kind='A02_GEOMETRY', scope_contracts=[], record_refs=[],
                    geometry_refs=[pand['geometry_ref']])
    obj = dict(kind='SOURCE_OBJECT', scope_contracts=[], geometry_refs=[],
               record_refs=[pand['record_ref']])

    def rule(identity, text, kind, subject, target, **extra):
        return dict(rule_id=identity, locator='synthetic-article/' + identity,
                    text=text, structured=dict(kind=kind, subject=subject, **extra),
                    certainty='EXPLICIT', uncertainties=[],
                    applicability=dict(status='APPLIES',
                                       basis='TESTDATA: explicit assignment in controlled fixture.',
                                       target=deepcopy(target)))

    rules = [
        rule('height', 'TESTDATA: maximum building height is 12 metres for this source object.',
             'BINDING', 'building_height', obj,
             quantity=dict(value=12, unit='m', operator='MAXIMUM')),
        rule('green', 'TESTDATA: aim for more green within the referenced existing geometry.',
             'POLICY_AMBITION', 'green_ambition', geometry),
        rule('info', 'TESTDATA: the study covers the full listed analysis scope.',
             'NEUTRAL_INFORMATION', 'study_scope', full),
        rule('unclear', 'TESTDATA: an unspecified condition might apply.',
             'UNKNOWN', 'unspecified_condition', full),
    ]
    rules[-1]['certainty'] = 'UNCLEAR'
    rules[-1]['uncertainties'] = ['TESTDATA: legal meaning and applicability are unspecified.']
    rules[-1]['applicability']['status'] = 'UNKNOWN'
    return dict(format='BVC_A06_FIXTURE_INPUT_V1', source_status='TESTDATA',
                input_revision='synthetic/v1', a02_context_hash=spatial['context_hash'],
                sources=[dict(source_id='SYNTHETIC_PLAN_001', source_status='TESTDATA',
                              version='fixture/v1', legal_status='EFFECTIVE', rules=rules)])
