"""Explicitly selected OW source evidence; no legal interpretation or approval."""
from copy import deepcopy
from bvc_ai.adapters.dso_diagnostics import validation_error
import hashlib
from urllib.parse import urlsplit

from bvc_ai.adapters.dso_contract import canonical, digest
from bvc_ai.adapters.dso_discovery import CONTRACT_VERSION
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin
from bvc_ai.adapters.ow_document import OWDocumentAdapter, BASE, _link, build_request
from bvc_ai.application.dso_discovery import DSODiscoveryService, _utc_now


def validate_discovery(discovery, expected_hash):
    data = deepcopy(discovery)
    if (data.get('format') != 'BVC_A06_DSO_DISCOVERY_V1'
            or data.get('discovery_hash') != expected_hash
            or digest({k: v for k, v in data.items() if k != 'discovery_hash'}) != expected_hash):
        raise validation_error(ValueError('Changed discovery binding'), 'DOCUMENT_IDENTITY')
    provenance = data['provenance']
    raw = data['raw_response_utf8'].encode()
    if hashlib.sha256(raw).hexdigest() != provenance['raw_response_sha256']:
        raise validation_error(ValueError('Changed discovery evidence'), 'DOCUMENT_IDENTITY')
    class Replay:
        def post(self, request):
            return HttpResponse(200, (('Content-Type', 'application/hal+json'), ('API-Version', CONTRACT_VERSION)),
                                raw, ResponseOrigin(data['source_status']))
    ticks = iter((provenance['retrieval_started_at'], provenance['retrieval_finished_at']))
    params = provenance['query_parameters']
    rebuilt = DSODiscoveryService(Replay(), clock=lambda: next(ticks)).discover_point(
        provenance['request_body']['geometrie']['coordinates'],
        peildatum=params['geldigOp'], beschikbaar_op=params['beschikbaarOp'])
    if 'a02_binding' in data:
        rebuilt['a02_binding'] = data['a02_binding']
        del rebuilt['discovery_hash']
        rebuilt['discovery_hash'] = digest(rebuilt)
    if canonical(rebuilt) != canonical(data):
        raise validation_error(ValueError('Discovery package cannot be replayed'), 'DOCUMENT_IDENTITY')
    return data


class OWDocumentRetrievalService:
    def __init__(self, transport, *, clock=_utc_now):
        self._adapter = OWDocumentAdapter(transport, clock)

    def retrieve(self, discovery, document_identity, *, expected_discovery_hash):
        data = validate_discovery(discovery, expected_discovery_hash)
        selected = [d for d in data['documents'] if d['identificatie'] == document_identity]
        if len(selected) != 1:
            raise validation_error(ValueError('Explicit unique discovery document identity required'), 'DOCUMENT_IDENTITY')
        selected = selected[0]
        metadata = selected.get('omgevingsdocumentMetadata')
        if (metadata is None or 'imroDocumentMetadata' in selected
                or not selected['identificatie'].startswith('/akn/nl/act/')
                or metadata['isOntwerp'] or metadata['isBesluit']
                or selected['type'] in ('Omgevingsvergunning', 'omgevingsvergunning')):
            raise validation_error(ValueError('Only established OW regelingen supported'), 'DOCUMENT_FAMILY')
        day = data['provenance']['query_parameters']['geldigOp']
        available = data['provenance']['query_parameters']['beschikbaarOp']
        first = self._adapter.fetch(selected, 'metadata', day, available)
        uri = selected['identificatie'].replace('/', '_').replace('-', '_')
        annotation_link = first['source']['_links']['annotaties']['href']
        path = urlsplit(annotation_link).path
        kinds = {'/regeltekstannotaties': 'rule_annotations', '/divisieannotaties': 'division_annotations'}
        kind = next((value for suffix, value in kinds.items()
                     if path == urlsplit(BASE).path + '/regelingen/' + uri + suffix), None)
        if kind is None:
            raise validation_error(ValueError('Unsupported official annotation endpoint'), 'DOCUMENT_IDENTITY')
        request = build_request(uri, 'metadata', day, available)
        _link(annotation_link, uri, next(s for s, k in kinds.items() if k == kind), request.parameters)
        structure = self._adapter.fetch(selected, 'structure', day, available)
        _link(structure['source']['_links']['annotaties']['href'], uri,
              next(s for s, k in kinds.items() if k == kind), request.parameters)
        annotations = self._adapter.fetch(selected, kind, day, available)
        final = self._adapter.fetch(selected, 'metadata', day, available)
        if canonical(first['source']) != canonical(final['source']):
            raise validation_error(ValueError('OW metadata changed during retrieval'), 'DOCUMENT_IDENTITY')
        captures = [first, structure, annotations, final]
        if {c['provenance']['source_status'] for c in captures} != {data['source_status']}:
            raise validation_error(ValueError('Mixed OW evidence origins'), 'DOCUMENT_IDENTITY')
        # Source JSON is preserved. The separate index only points into that JSON.
        components = []
        def index(nodes, pointer):
            for i, node in enumerate(nodes):
                path = pointer + '/' + str(i)
                components.append(dict(work_id=node['identificatie'], expression_id=node['expressie'],
                                       source_pointer=path))
                if '_embedded' in node:
                    index(node['_embedded']['documentComponenten'], path + '/_embedded/documentComponenten')
        index(structure['source']['_embedded']['documentComponenten'],
              '/source_evidence/1/source/_embedded/documentComponenten')
        annotation_data = annotations['source']
        annotation_ids = []
        for name, rows in annotation_data.items():
            if name != '_links':
                for row in rows:
                    identity = row.get('identificatie')
                    if not isinstance(identity, str) or not identity.strip():
                        raise validation_error(ValueError('Missing OW annotation identity'), 'DOCUMENT_IDENTITY')
                    annotation_ids.append(identity)
        if len(set(annotation_ids)) != len(annotation_ids):
            raise validation_error(ValueError('Ambiguous OW annotation identity'), 'DOCUMENT_IDENTITY')
        component_ids = {c['work_id'] for c in components}
        def check_refs(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'wId' and item not in component_ids:
                        raise validation_error(ValueError('Unresolved OW component reference'), 'DOCUMENT_IDENTITY')
                    refs = [item] if key.endswith('Ref') else item if key.endswith('Refs') else []
                    if any(ref not in annotation_ids for ref in refs):
                        raise validation_error(ValueError('Unresolved OW annotation reference'), 'DOCUMENT_IDENTITY')
                    check_refs(item)
            elif isinstance(value, list):
                for item in value:
                    check_refs(item)
        check_refs(annotation_data)
        result = dict(
            format='BVC_A06_OW_SOURCE_EVIDENCE_V1', evidence_role='SOURCE_EVIDENCE_ONLY',
            discovery_hash=data['discovery_hash'], selected_discovery_document=deepcopy(selected),
            source_status=first['provenance']['source_status'],
            source_evidence=captures,
            derived_structure=dict(method='LITERAL_COMPONENT_POINTERS_V1', components=components),
            limitations=['ESTABLISHED_OW_REGELING_ONLY', 'NO_APPLICABILITY_OR_LEGAL_CLASSIFICATION',
                         'NO_GEOMETRIES_OR_EXTERNAL_LINK_RETRIEVAL',
                         'FOUR_REQUESTS_MAXIMUM_4_MIB_AND_15_SECONDS_EACH',
                         'EXPLICIT_DISCOVERY_PIN_REQUIRED_HASH_IS_NOT_AUTHENTICATION',
                         'DISCOVERY_TIME_COORDINATES_PLUS_INWERKINGOP_EQUALS_GELDIGOP',
                         'METADATA_BRACKET_CHECK_NOT_AN_ATOMIC_SERVER_SNAPSHOT'])
        result['evidence_hash'] = digest(result)
        return result
