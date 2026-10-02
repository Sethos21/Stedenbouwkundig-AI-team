"""Offline DSO discovery and secret-boundary tests; never perform a live proof."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
import os
import secrets
import threading
import traceback
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from dso_fixtures import discovery_page, imro_document
from bvc_ai.adapters.dso_contract import CONTRACT_SHA256, CONTRACT_VERSION, canonical, contract, digest
from bvc_ai.adapters.dso_discovery import (
    build_request, parse_response, validate_request, DSODiscoveryAdapter, ENDPOINT, HOST, CRS,
)
from bvc_ai.adapters.dso_live import DSOLivePostTransport
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin
from bvc_ai.application.dso_discovery import DSODiscoveryService

POINT = [155000, 463000]
DAY = '2026-10-02'
AVAILABLE = '2026-10-02T10:30:00+02:00'
RETRIEVED = '2026-10-02T09:00:00Z'


def response(data=None):
    return HttpResponse(200, (('Content-Type', 'application/hal+json'),
                              ('API-Version', CONTRACT_VERSION)),
                        canonical(discovery_page() if data is None else data).encode(),
                        ResponseOrigin.TESTDATA)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE DSO TEST'))
            guard.start()
            self.addCleanup(guard.stop)
        self.request = build_request(POINT, DAY, AVAILABLE)
        self.transport = Mock()
        self.transport.post.return_value = response()
        self.service = DSODiscoveryService(self.transport, clock=lambda: RETRIEVED)

    def test_official_contract_and_exact_request_dates_crs(self):
        spec = contract()
        self.assertEqual(spec['info']['version'], CONTRACT_VERSION)
        self.assertIn('/documenten/_zoek', spec['paths'])
        self.assertEqual(spec['components']['securitySchemes']['apiKey']['name'].lower(), 'x-api-key')
        request = self.request
        validate_request(request)
        self.assertEqual(request.method, 'POST')
        self.assertEqual(request.url.split('?')[0], ENDPOINT)
        params = parse_qs(urlsplit(request.url).query)
        self.assertEqual(params['geldigOp'], [DAY])
        self.assertEqual(params['beschikbaarOp'], [AVAILABLE])
        self.assertEqual(params['inclusiefToekomstigGeldig'], ['false'])
        self.assertEqual(dict(request.headers)['Content-Crs'], CRS)
        self.assertEqual(json.loads(request.body), {'geometrie': {'type': 'Point', 'coordinates': POINT}})
        self.assertNotIn('_find', params)

    def test_invalid_dates_points_precision_and_allowlist(self):
        for point, day, available in [
            (POINT, '2026-02-30', AVAILABLE), (POINT, DAY, '2026-10-02'),
            (POINT, DAY, '2026-10-02T12:00:00'), ([True, 463000], DAY, AVAILABLE),
            ([155000.0001, 463000], DAY, AVAILABLE), ([5, 5], DAY, AVAILABLE),
            ([float('inf'), 463000], DAY, AVAILABLE),
        ]:
            with self.assertRaises(ValueError):
                build_request(point, day, available)
        for changed in [
            replace(self.request, url=self.request.url.replace('https:', 'http:')),
            replace(self.request, url=self.request.url.replace(HOST, 'example.invalid')),
            replace(self.request, url=self.request.url.replace('_zoek', '_suggereer')),
            replace(self.request, url=self.request.url + '#fragment'),
            replace(self.request, parameters=()),
            replace(self.request, headers=(('X-API-Key', 'forbidden-header'),)),
            replace(self.request, body=b'{}'),
            replace(self.request, timeout_seconds=float('nan')),
            replace(self.request, max_response_bytes=99999999),
        ]:
            with self.assertRaises(ValueError):
                validate_request(changed)

    def test_deterministic_parsing_all_candidates_and_provenance(self):
        data = discovery_page()
        data['_embedded']['documenten'].append(imro_document())
        data['page']['totalElements'] = 2
        parsed = parse_response(response(data), self.request)
        data['_embedded']['documenten'].reverse()
        self.assertEqual(parsed, parse_response(response(data), self.request))
        self.transport.post.return_value = response(data)
        output = self.service.discover_point(POINT, peildatum=DAY, beschikbaar_op=AVAILABLE)
        again = self.service.discover_point(POINT, peildatum=DAY, beschikbaar_op=AVAILABLE)
        self.assertEqual(output, again)
        self.assertEqual(output['documents'], parsed)
        self.assertEqual(output['source_status'], 'TESTDATA')
        p = output['provenance']
        self.assertEqual(p['contract_sha256'], CONTRACT_SHA256)
        self.assertEqual(p['retrieval_finished_at'], RETRIEVED)
        self.assertEqual(p['query_parameters']['beschikbaarOp'], AVAILABLE)
        self.assertEqual(p['raw_response_sha256'],
                         hashlib.sha256(output['raw_response_utf8'].encode()).hexdigest())
        self.assertEqual(output['discovery_hash'], digest({k: v for k, v in output.items() if k != 'discovery_hash'}))
        self.assertEqual(parse_response(response(json.loads(output['raw_response_utf8'])), self.request), parsed)
        self.assertNotIn('classification', output)

    def test_empty_complete_search_is_not_suitability_or_missing_source_fallback(self):
        data = discovery_page()
        data['_embedded']['documenten'] = []
        data['page'].update(totalElements=0, totalPages=0)
        self.assertEqual(parse_response(response(data), self.request), [])

    def test_missing_fields_malformed_metadata_and_ambiguity_fail_closed(self):
        cases = []
        for field in ('identificatie', 'uriIdentificatie', 'versie', 'type', 'beschikbaarVanaf'):
            data = discovery_page()
            del data['_embedded']['documenten'][0][field]
            cases.append(data)
        for field, value in [('identificatie', ''), ('versie', True), ('unexpected', 'x'),
                             ('aangeleverdDoorEen', {}), ('beschikbaarVanaf', 'not-a-date')]:
            data = discovery_page()
            data['_embedded']['documenten'][0][field] = value
            cases.append(data)
        for mutation in ('duplicate', 'two_families', 'no_family', 'bad_expression', 'wrong_uri'):
            data = discovery_page()
            doc = data['_embedded']['documenten'][0]
            if mutation == 'duplicate':
                data['_embedded']['documenten'].append(deepcopy(doc))
                data['page']['totalElements'] = 2
            elif mutation == 'two_families':
                doc['imroDocumentMetadata'] = imro_document()['imroDocumentMetadata']
            elif mutation == 'no_family':
                del doc['omgevingsdocumentMetadata']
            elif mutation == 'bad_expression':
                doc['omgevingsdocumentMetadata']['expressionId'] = '/akn/nl/other/nld@1'
            else:
                doc['uriIdentificatie'] = 'another-identity'
            cases.append(data)
        for data in cases:
            with self.assertRaises(ValueError):
                parse_response(response(data), self.request)

    def test_contradictory_intervals_and_changed_contract_fail_closed(self):
        data = discovery_page()
        data['_embedded']['documenten'][0]['geldigTot'] = '2025-01-01'
        with self.assertRaisesRegex(ValueError, 'temporal interval'):
            parse_response(response(data), self.request)
        with patch('bvc_ai.adapters.dso_contract.Path.read_bytes', return_value=b'{}'):
            with self.assertRaisesRegex(ValueError, 'Changed pinned DSO contract'):
                parse_response(response(), self.request)

    def test_pagination_truncation_duplicate_json_and_contract_drift_fail_closed(self):
        for changes in (dict(totalElements=201, totalPages=2), dict(number=1), dict(size=20),
                        dict(totalElements=2), dict(totalPages=2)):
            data = discovery_page()
            data['page'].update(changes)
            with self.assertRaises(ValueError):
                parse_response(response(data), self.request)
        data = discovery_page()
        data['_links']['next'] = {'href': 'https://example.invalid/steal'}
        with self.assertRaises(ValueError):
            parse_response(response(data), self.request)
        for body in (b'{', b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b'null'):
            with self.assertRaises(ValueError):
                parse_response(replace(response(), body=body), self.request)
        for changed in (replace(response(), status=302),
                        replace(response(), headers=(('Content-Type', 'application/json'),)),
                        replace(response(), headers=response().headers + (('API-Version', '2.0'),))):
            with self.assertRaises(ValueError):
                parse_response(changed, self.request)


class LiveBoundaryTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE DSO TEST'))
            guard.start()
            self.addCleanup(guard.stop)
        self.request = build_request(POINT, DAY, AVAILABLE)
        # Ephemeral dummy credential, generated in memory; never a stored key.
        self.secret = secrets.token_urlsafe(32)
        env = patch.dict(os.environ, {'DSO_API_KEY': self.secret})
        env.start()
        self.addCleanup(env.stop)
        self.conn = Mock()
        self.http = Mock(status=200)
        self.http.getheaders.return_value = list(response().headers)
        self.http.read1.side_effect = io.BytesIO(response().body).read1
        self.conn.getresponse.return_value = self.http
        factory = patch('bvc_ai.adapters.dso_live.http.client.HTTPSConnection', return_value=self.conn)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.live = DSOLivePostTransport(live_opt_in=True)

    def test_missing_key_and_missing_opt_in_fail_before_network(self):
        with self.assertRaises(PermissionError):
            DSOLivePostTransport().post(self.request)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'DSO_API_KEY is required'):
                self.live.post(self.request)
        self.factory.assert_not_called()

    def test_runtime_header_only_no_secret_in_request_evidence_hashes_or_repr(self):
        with patch('sys.stdout', new_callable=io.StringIO) as stdout:
            result = DSODiscoveryService(self.live, clock=lambda: RETRIEVED).discover_point(
                POINT, peildatum=DAY, beschikbaar_op=AVAILABLE)
        self.assertFalse(self.secret in repr(self.request) + repr(result) + repr(self.live) + stdout.getvalue())
        self.assertTrue(self.conn.request.call_args.kwargs['headers']['X-API-Key'] == self.secret)
        self.assertEqual(self.conn.request.call_args.args[0], 'POST')
        self.assertEqual(self.factory.call_args.args, (HOST,))
        self.conn.set_debuglevel.assert_called_once_with(0)
        self.assertEqual(result['source_status'], ResponseOrigin.PROVIDER_RESPONSE.value)

    def test_secret_reflection_and_exception_text_are_suppressed(self):
        for mode in ('exception', 'body', 'escaped_body', 'header', 'error_response'):
            with self.subTest(mode=mode):
                self.conn.connect.side_effect = None
                self.http.status = 200
                self.http.getheaders.return_value = list(response().headers)
                data = discovery_page()
                if mode == 'exception':
                    self.conn.connect.side_effect = OSError(self.secret)
                elif mode == 'header':
                    self.http.getheaders.return_value.append(('diagnostic', self.secret))
                elif mode == 'error_response':
                    self.http.status = 401
                else:
                    data['_embedded']['documenten'][0]['titel'] = self.secret
                body = canonical(data).encode()
                if mode == 'escaped_body':
                    body = body.replace(self.secret.encode(),
                                        ''.join('\\u%04x' % ord(c) for c in self.secret).encode())
                self.http.read1.side_effect = io.BytesIO(body).read1
                with patch('sys.stdout', new_callable=io.StringIO) as stdout:
                    try:
                        self.live.post(self.request)
                    except OSError as exc:
                        error_text = ''.join(traceback.format_exception(exc))
                    else:
                        self.fail('Unsafe response accepted')
                self.assertFalse(self.secret in error_text + stdout.getvalue())

    def test_bounds_length_encoding_and_redirects(self):
        for mode in ('cap', 'length', 'compression', 'redirect'):
            self.http.status = 302 if mode == 'redirect' else 200
            headers = list(response().headers)
            if mode == 'length':
                headers.append(('Content-Length', '999999'))
            if mode == 'compression':
                headers.append(('Content-Encoding', 'gzip'))
            self.http.getheaders.return_value = headers
            self.http.read1.side_effect = io.BytesIO(response().body).read1
            request = replace(self.request, max_response_bytes=10) if mode == 'cap' else self.request
            with self.assertRaises(OSError):
                self.live.post(request)

    def test_total_deadline_and_no_send_after_cancelled_connect(self):
        for phase in ('connect', 'read1'):
            released, finished = threading.Event(), threading.Event()
            def block(*args):
                released.wait(2)
                finished.set()
                return b''
            target = self.conn.connect if phase == 'connect' else self.http.read1
            self.conn.request.reset_mock()
            target.side_effect = block
            try:
                with self.assertRaises(TimeoutError):
                    self.live.post(replace(self.request, timeout_seconds=0.02))
            finally:
                released.set()
                self.assertTrue(finished.wait(2))
                target.side_effect = None
            if phase == 'connect':
                self.conn.request.assert_not_called()

    def test_arbitrary_endpoint_rejected_before_connection(self):
        with self.assertRaises(ValueError):
            self.live.post(replace(self.request, url='https://example.invalid/'))
        self.factory.assert_not_called()


class A02DiscoveryTests(unittest.TestCase):
    def setUp(self):
        import test_source_profiles as helpers
        from test_source_import import TID
        from bvc_ai.application.source_basis import REQUIRED_CONTRACTS
        from bvc_ai.application.spatial_context import SpatialContextService
        helpers.SourceProfileTests.setUp(self)
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE DSO TEST'))
            guard.start()
            self.addCleanup(guard.stop)
        for key in sorted(REQUIRED_CONTRACTS):
            item = helpers.profile_response(key)
            if key == 'BAG/verblijfsobject':
                data = json.loads(item.body)
                data['features'][0]['place']['coordinates'] = POINT
                item = replace(item, body=json.dumps(data).encode())
            helpers.SourceProfileTests.importer(self, key, [item]).import_source(TID, key, self.extent)
        self.spatial = SpatialContextService(self.store).build(TID)
        self.point_ref = next(o['record_ref'] for o in self.spatial['objects']
                              if o['record_ref'][0] == 'BAG/verblijfsobject')
        self.transport = Mock()
        self.transport.post.return_value = response()
        self.service = DSODiscoveryService(self.transport, clock=lambda: RETRIEVED)

    def test_validated_point_binding_read_only_and_a06_v1_unchanged(self):
        from bvc_ai.application.planological_context import PlanologicalContextService, input_hash
        from planological_fixtures import planological_fixture
        data = planological_fixture(self.spatial)
        a06 = PlanologicalContextService(self.store)
        before_v1 = a06.build(self.spatial, data, expected_input_hash=input_hash(data))
        before = deepcopy(self.spatial), self.store.list(), self.store.events()
        output = self.service.discover_a02_point(self.store, self.spatial, self.point_ref,
                                                 peildatum=DAY, beschikbaar_op=AVAILABLE)
        self.assertEqual(output['a02_binding']['context_hash'], self.spatial['context_hash'])
        self.assertEqual(output['a02_binding']['record_ref'], self.point_ref)
        self.assertEqual(output['provenance']['request_body']['geometrie']['coordinates'], POINT)
        self.assertEqual((self.spatial, self.store.list(), self.store.events()), before)
        self.assertEqual(a06.build(self.spatial, data, expected_input_hash=input_hash(data)), before_v1)

    def test_nonpoint_tampered_and_stale_a02_never_calls_transport(self):
        from test_source_import import TID
        import test_source_profiles as helpers
        polygon = next(o['record_ref'] for o in self.spatial['objects'] if o['record_ref'][0] == 'BAG/pand')
        with self.assertRaisesRegex(ValueError, 'source point'):
            self.service.discover_a02_point(self.store, self.spatial, polygon,
                                           peildatum=DAY, beschikbaar_op=AVAILABLE)
        changed = deepcopy(self.spatial)
        changed['context_hash'] = 'tampered'
        with self.assertRaises(ValueError):
            self.service.discover_a02_point(self.store, changed, self.point_ref,
                                           peildatum=DAY, beschikbaar_op=AVAILABLE)
        discovery_transport = self.transport
        helpers.SourceProfileTests.importer(self, 'BGT/wegdeel', [
            helpers.profile_response('BGT/wegdeel', 'new')]).import_source(TID, 'new', self.extent)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.service.discover_a02_point(self.store, self.spatial, self.point_ref,
                                           peildatum=DAY, beschikbaar_op=AVAILABLE)
        discovery_transport.post.assert_not_called()
