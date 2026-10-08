"""Synthetic Presenteren retrieval; no network and no stored API credentials."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import secrets
import os
import traceback
import unittest
from unittest.mock import Mock, patch

from dso_fixtures import discovery_page, imro_document
from bvc_ai.adapters.dso_contract import canonical, digest
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin
from bvc_ai.adapters.ow_document import BASE, VERSION, build_request, parse_response, validate_request, contract
from bvc_ai.adapters.dso_live import DSOLiveOWTransport
from bvc_ai.application.dso_discovery import DSODiscoveryService
from bvc_ai.application.ow_document import OWDocumentRetrievalService

DAY = '2026-10-02'
AVAILABLE = '2026-10-02T09:00:00Z'
IDENTITY = '/akn/nl/act/gm0000/2026/test'
URI = IDENTITY.replace('/', '_')


def discovery():
    transport = Mock()
    transport.post.return_value = HttpResponse(
        200, (('Content-Type', 'application/hal+json'), ('API-Version', '2.13.1')),
        canonical(discovery_page()).encode(), ResponseOrigin.TESTDATA)
    return DSODiscoveryService(transport, clock=lambda: AVAILABLE).discover_point(
        [155000, 463000], peildatum=DAY, beschikbaar_op=AVAILABLE)


def fixtures():
    def href(kind):
        return dict(href=build_request(URI, kind, DAY, AVAILABLE).url)
    annotation = href('rule_annotations')
    metadata = dict(
        identificatie=IDENTITY, expressionId=IDENTITY + '/nld@2026-01-01;1',
        officieleTitel='TESTDATA source title',
        aangeleverdDoorEen=dict(bestuurslaag='gemeentebestuur', code='gm0000', naam='TESTDATA'),
        type=dict(code='https://example.invalid/TESTDATA', waarde='Omgevingsplan'),
        geregistreerdMet=dict(versie=1, beginGeldigheid='2026-01-01', beginInwerking='2026-01-01',
                             tijdstipRegistratie='2026-01-01T00:00:00Z'),
        _links=dict(self=href('metadata'), documentstructuur=href('structure'), annotaties=annotation))
    structure = dict(
        _links=dict(self=href('structure'), regeling=href('metadata'), annotaties=annotation,
                    afbeeldingenBasePath=dict(href='https://example.invalid/never-fetch')),
        _embedded=dict(documentComponenten=[
            dict(identificatie='test__art_1', expressie='art_1', type='Artikel', volgordeNummer=1,
                 inhoud='<Al>TESTDATA literal legal source, no interpretation.</Al>')]))
    annotations = dict(
        _links=dict(self=annotation, regeling=href('metadata'), documentstructuur=href('structure')),
        regelteksten=[dict(identificatie='test.regeltekst.1', wId='test__art_1')],
        regelsVoorIedereen=[dict(identificatie='test.regel.1', regeltekstRef='test.regeltekst.1',
                                locatieRefs=['test.locatie.1'],
                                idealisatie=dict(code='https://example.invalid/code', waarde='exact'))],
        locaties=[dict(identificatie='test.locatie.1', locatieType='Gebied',
                       geometrieIdentificatie='TESTDATA-geometry-reference')])
    return [metadata, structure, annotations, deepcopy(metadata)]


def response(data, version=VERSION):
    return HttpResponse(200, (('Content-Type', 'application/hal+json'), ('API-Version', version)),
                        canonical(data).encode(), ResponseOrigin.TESTDATA)


class OWRetrievalTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE OW TEST'))
            guard.start()
            self.addCleanup(guard.stop)
        self.discovery = discovery()
        self.transport = Mock()
        self.transport.get.side_effect = [response(d) for d in fixtures()]
        self.service = OWDocumentRetrievalService(self.transport, clock=lambda: AVAILABLE)

    def retrieve(self, data=None, identity=IDENTITY):
        data = self.discovery if data is None else data
        return self.service.retrieve(data, identity, expected_discovery_hash=data['discovery_hash'])

    def test_selected_discovery_binding_raw_sources_determinism_and_hashes(self):
        before = deepcopy(self.discovery)
        output = self.retrieve()
        self.assertEqual(self.discovery, before)
        self.assertEqual(output['discovery_hash'], before['discovery_hash'])
        self.assertEqual(output['evidence_role'], 'SOURCE_EVIDENCE_ONLY')
        for evidence, original in zip(output['source_evidence'], fixtures()):
            self.assertEqual(evidence['source'], original)
            self.assertEqual(evidence['provenance']['response_hash'],
                             hashlib.sha256(evidence['raw_response_utf8'].encode()).hexdigest())
            self.assertEqual(evidence['provenance']['api_version'], VERSION)
            self.assertEqual(evidence['provenance']['retrieval_started_at'], AVAILABLE)
        self.assertEqual(output['derived_structure']['components'][0]['work_id'], 'test__art_1')
        self.assertEqual(output['evidence_hash'], digest({k: v for k, v in output.items() if k != 'evidence_hash'}))
        self.transport.get.side_effect = [response(d) for d in fixtures()]
        self.assertEqual(self.retrieve(), output)
        self.assertEqual(len(self.transport.get.call_args_list), 8)

    def test_discovery_and_retrieval_origins_must_match(self):
        self.transport.get.side_effect = [
            replace(response(d), origin=ResponseOrigin.PROVIDER_RESPONSE) for d in fixtures()]
        with self.assertRaisesRegex(ValueError, 'Mixed OW evidence origins'):
            self.retrieve()
    def test_official_division_annotations_are_preserved_without_interpretation(self):
        data = fixtures()
        link = dict(href=build_request(URI, 'division_annotations', DAY, AVAILABLE).url)
        for row in (data[0], data[1], data[3]):
            row['_links']['annotaties'] = link
        data[2] = dict(_links=dict(self=link, regeling=data[2]['_links']['regeling'],
                                   documentstructuur=data[2]['_links']['documentstructuur']),
                       divisies=[], divisieteksten=[], tekstdelen=[], locaties=[])
        self.transport.get.side_effect = [response(d) for d in data]
        result = self.retrieve()
        self.assertEqual(result['source_evidence'][2]['source'], data[2])

    def test_official_contract_requests_and_no_implicit_availability_rounding(self):
        spec = contract()
        self.assertEqual(spec['info']['version'], '8.2.5')
        for kind in ('metadata', 'structure', 'rule_annotations', 'division_annotations'):
            req = build_request(URI, kind, DAY, AVAILABLE)
            validate_request(req)
            self.assertEqual(dict(req.parameters)['inWerkingOp'], DAY)
            self.assertEqual(dict(req.parameters)['beschikbaarOp'], AVAILABLE)
        with self.assertRaises(ValueError):
            build_request(URI, 'metadata', DAY, '2026-10-02T09:00:00.000000001Z')
        for changed in (replace(build_request(URI, 'metadata', DAY, AVAILABLE), url='https://example.invalid/'),
                        replace(build_request(URI, 'metadata', DAY, AVAILABLE), headers=(('Cookie', 'x'),))):
            with self.assertRaises(ValueError):
                validate_request(changed)

    def test_unselected_imro_draft_and_tampered_discovery_fail_before_fetch(self):
        with self.assertRaises(ValueError):
            self.retrieve(identity='/akn/nl/act/other')
        altered = deepcopy(self.discovery)
        altered['documents'][0]['versie'] = 2
        with self.assertRaises(ValueError):
            self.retrieve(altered)
        altered['discovery_hash'] = digest({k: v for k, v in altered.items() if k != 'discovery_hash'})
        with self.assertRaisesRegex(ValueError, 'replayed'):
            self.retrieve(altered)
        for mode in ('imro', 'draft', 'decision'):
            page = discovery_page()
            if mode == 'imro':
                page['_embedded']['documenten'] = [imro_document()]
            else:
                page['_embedded']['documenten'][0]['omgevingsdocumentMetadata'][
                    'isOntwerp' if mode == 'draft' else 'isBesluit'] = True
            transport = Mock()
            transport.post.return_value = HttpResponse(
                200, (('Content-Type', 'application/hal+json'), ('API-Version', '2.13.1')),
                canonical(page).encode(), ResponseOrigin.TESTDATA)
            data = DSODiscoveryService(transport, clock=lambda: AVAILABLE).discover_point(
                [155000, 463000], peildatum=DAY, beschikbaar_op=AVAILABLE)
            with self.assertRaisesRegex(ValueError, 'Only established OW'):
                self.retrieve(data, data['documents'][0]['identificatie'])
        self.transport.get.assert_not_called()

    def test_identity_expression_version_type_authority_and_drift_fail_closed(self):
        for field in ('identificatie', 'expressionId', 'version', 'type', 'authority', 'time'):
            data = fixtures()
            if field == 'version':
                data[0]['geregistreerdMet']['versie'] = 2
            elif field == 'time':
                data[0]['geregistreerdMet']['beginGeldigheid'] = '2026-02-01'
            elif field == 'type':
                data[0]['type']['waarde'] = 'Programma'
            elif field == 'authority':
                data[0]['aangeleverdDoorEen']['code'] = 'gm9999'
            else:
                data[0][field] = 'conflict'
            self.transport.get.side_effect = [response(d) for d in data]
            with self.assertRaises(ValueError):
                self.retrieve()
        self.transport.get.side_effect = [response(fixtures()[0], '8.2.6')]
        with self.assertRaises(ValueError):
            self.retrieve()

    def test_incomplete_structure_annotations_and_changed_final_metadata_fail_closed(self):
        for mode in ('empty', 'leaf', 'missing', 'ref', 'wid', 'final', 'geometry', 'external', 'wrong_time'):
            data = fixtures()
            if mode == 'empty':
                data[1]['_embedded']['documentComponenten'] = []
            elif mode == 'leaf':
                del data[1]['_embedded']['documentComponenten'][0]['inhoud']
            elif mode == 'missing':
                del data[0]['geregistreerdMet']
            elif mode == 'ref':
                data[2]['regelsVoorIedereen'][0]['locatieRefs'] = ['missing']
            elif mode == 'wid':
                data[2]['regelteksten'][0]['wId'] = 'missing'
            elif mode == 'final':
                data[3]['officieleTitel'] = 'changed'
            elif mode == 'geometry':
                data[2]['locaties'][0]['geometry'] = dict(type='Point', coordinates=[0, 0])
            elif mode == 'external':
                data[0]['_links']['annotaties']['href'] = 'https://example.invalid/regeltekstannotaties'
            else:
                data[1]['_links']['self']['href'] = data[1]['_links']['self']['href'].replace(DAY, '2026-10-01')
            self.transport.get.side_effect = [response(d) for d in data]
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.retrieve()

    def test_malformed_duplicate_json_and_contract_hash_changes_fail_closed(self):
        for body in (b'{}', b'{', b'{"x":1,"x":2}', b'null'):
            self.transport.get.side_effect = [replace(response(fixtures()[0]), body=body)]
            with self.assertRaises(ValueError):
                self.retrieve()
        with patch('bvc_ai.adapters.ow_document.Path.read_bytes', return_value=b'{}'):
            with self.assertRaises(ValueError):
                contract()

    def test_live_secret_boundary_get_only_and_missing_key(self):
        request = build_request(URI, 'metadata', DAY, AVAILABLE)
        live = DSOLiveOWTransport(live_opt_in=True)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'DSO_API_KEY'):
                live.get(request)
        key = secrets.token_urlsafe(32)
        conn, http = Mock(), Mock(status=200)
        conn.getresponse.return_value = http
        http.getheaders.return_value = list(response(fixtures()[0]).headers)
        with patch.dict(os.environ, {'DSO_API_KEY': key}), patch(
                'bvc_ai.adapters.dso_live.http.client.HTTPSConnection', return_value=conn):
            http.read1.side_effect = io.BytesIO(response(fixtures()[0]).body).read1
            result = live.get(request)
            self.assertFalse(key in repr(result) + repr(request))
            self.assertEqual(conn.request.call_args.args[0], 'GET')
            self.assertTrue(conn.request.call_args.kwargs['headers']['X-API-Key'] == key)
            http.read1.side_effect = io.BytesIO(canonical(dict(reflected=key)).encode()).read1
            try:
                live.get(request)
            except OSError as exc:
                self.assertFalse(key in ''.join(traceback.format_exception(exc)))
            else:
                self.fail('Credential reflection accepted')
            conn.connect.side_effect = OSError(key)
            try:
                live.get(request)
            except OSError as exc:
                self.assertFalse(key in ''.join(traceback.format_exception(exc)))
            else:
                self.fail('Credential-bearing error accepted')


class OWReadOnlyTests(unittest.TestCase):
    from test_dso_discovery import A02DiscoveryTests
    setUp = A02DiscoveryTests.setUp

    def test_a02_and_a06_v1_unchanged_after_bound_ow_retrieval(self):
        from bvc_ai.application.planological_context import PlanologicalContextService, input_hash
        from planological_fixtures import planological_fixture
        fixture = planological_fixture(self.spatial)
        v1 = PlanologicalContextService(self.store)
        original = v1.build(self.spatial, fixture, expected_input_hash=input_hash(fixture))
        data = self.service.discover_a02_point(self.store, self.spatial, self.point_ref,
                                               peildatum=DAY, beschikbaar_op=AVAILABLE)
        before = deepcopy(self.spatial), deepcopy(data), self.store.list(), self.store.events()
        transport = Mock()
        transport.get.side_effect = [response(d) for d in fixtures()]
        result = OWDocumentRetrievalService(transport, clock=lambda: AVAILABLE).retrieve(
            data, IDENTITY, expected_discovery_hash=data['discovery_hash'])
        self.assertEqual(result['discovery_hash'], data['discovery_hash'])
        self.assertEqual((self.spatial, data, self.store.list(), self.store.events()), before)
        self.assertEqual(v1.build(self.spatial, fixture, expected_input_hash=input_hash(fixture)), original)
