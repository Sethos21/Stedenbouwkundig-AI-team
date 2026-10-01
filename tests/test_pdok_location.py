"""Synthetic fixtures only. Socket/DNS access is forbidden in every test."""
import base64
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from bvc_ai.adapters.pdok_location import (
    AddressInput, AddressResolutionError, PDOKLocationTransport, address_request,
    resolve_address, replay_address, MAX_BYTES, ENDPOINT,
)
from bvc_ai.adapters.pdok_live import PDOKLiveGetTransport, BBOX
from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin
from bvc_ai.application.live_source_validation import address_analysis, validate_live_analysis, mastenbroekweg_analysis
from bvc_ai.domain.sources import GeometryRole
from test_source_profiles import profile_response, metadata
from test_pdok_bgt_fetch import SequenceTransport, Timer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import live_mastenbroekweg_2d as proof

ADDRESS = 'Voorbeeldstraat 12\n1234 AB Teststad\nNederland'
DOC = dict(id='adr-synthetic-only', bron='BAG', type='adres',
    weergavenaam='Voorbeeldstraat 12, 1234AB Teststad', straatnaam='Voorbeeldstraat',
    huisnummer=12, postcode='1234AB', woonplaatsnaam='Teststad',
    nummeraanduiding_id='0123200000000001', adresseerbaarobject_id='0123010000000001',
    centroide_rd='POINT(200123.456 520789.123)')


def response(doc=None, **changes):
    result = dict(numFound=1, start=0, numFoundExact=True, docs=[DOC if doc is None else doc])
    result.update(changes)
    return HttpResponse(200, (('Content-Type', 'application/json'),),
                        json.dumps(dict(response=result)).encode(), ResponseOrigin.PROVIDER_RESPONSE)


def resolve(item=None, **kwargs):
    return resolve_address(ADDRESS, SequenceTransport([response() if item is None else item], Timer()),
                           live_opt_in=True, **kwargs)


class AddressTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('SYNTHETIC TEST: NETWORK BLOCKED'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_exact_match_and_networkless_address_replay(self):
        location, evidence = resolve()
        self.assertEqual(location.coordinates, (200123.456, 520789.123))
        self.assertEqual(location.coordinate_crs, 'EPSG:28992')
        self.assertEqual(replay_address(json.loads(json.dumps(evidence))), location)
        self.assertEqual(base64.b64decode(evidence['raw_base64']), response().body)

    def test_normal_address_text_without_location_hardcoding(self):
        for text in ('K.E. Borgerlaan 4\n7942 HC Meppel\nNederland',
                     'Mastenbroekweg 2, 6006 PT Weert, Nederland', ADDRESS,
                     "'s-Gravenweg 3A, 1234 AB Teststad"):
            request = address_request(AddressInput.parse(text))
            self.assertTrue(request.url.startswith(ENDPOINT + '?'))

    def test_no_match_and_ambiguous_even_when_one_result_returned(self):
        for item in (response(numFound=0, docs=[]), response(numFound=2),
                     response(numFound=2, docs=[DOC,DOC]), response(numFoundExact=False),
                     response(numFoundExact=None), response(start=False)):
            with self.subTest(item=item), self.assertRaises(AddressResolutionError):
                resolve(item)

    def test_malformed_and_partial_response(self):
        for body in (b'{}', b'<html>', b'[]', b'{"response":{},"response":{}}',
                     b'{"response": {"numFound": NaN}}',
                     json.dumps(dict(responseHeader=dict(status=0,partialResults=True),
                                     response=dict(numFound=1,start=0,docs=[DOC]))).encode()):
            with self.subTest(body=body), self.assertRaises(AddressResolutionError):
                resolve(replace(response(), body=body))

    def test_missing_invalid_coordinate_and_unexpected_crs(self):
        for change in ({'centroide_rd': None}, {'centroide_rd': ''},
                       {'centroide_rd': 'POINT(5.4 52.6)'}, {'centroide_rd': 'POINT(200000 500000 2)'},
                       {'crs':'EPSG:4326'}, {'centroide_rd':'POINT(NaN 500000)'}):
            with self.subTest(change=change), self.assertRaises(AddressResolutionError):
                resolve(response(dict(DOC, **change)))
        with self.assertRaises(AddressResolutionError):
            resolve(replace(response(), headers=response().headers + (('Content-Crs','EPSG:4326'),)))

    def test_source_and_address_identity_must_match(self):
        for change in ({'bron':'DKK'}, {'type':'perceel'}, {'straatnaam':'Andere straat'},
                       {'huisnummer':13}, {'huisletter':'A'}, {'postcode':'1234AC'},
                       {'woonplaatsnaam':'Elders'}, {'nummeraanduiding_id':None},
                       {'adresseerbaarobject_id':'invalid'}, {'id':''}):
            with self.subTest(change=change), self.assertRaises(AddressResolutionError):
                resolve(response(dict(DOC, **change)))
        with self.assertRaises(AddressResolutionError):
            resolve(replace(response(), origin=ResponseOrigin.TESTDATA))

    def test_failure_evidence_for_network_timeout_and_bytes(self):
        for item in (OSError('offline'), TimeoutError('deadline'),
                     replace(response(), body=b' ' * (MAX_BYTES + 1)),
                     replace(response(), status=302),
                     replace(response(), headers=(('Content-Type','text/html'),))):
            with self.subTest(item=type(item)), self.assertRaises(AddressResolutionError) as caught:
                resolve(item)
            self.assertEqual(caught.exception.evidence['status'], 'BLOCKED')
            self.assertTrue(caught.exception.evidence['reason'])
        with patch('bvc_ai.adapters.pdok_location.time.monotonic', side_effect=[0,21]):
            with self.assertRaises(AddressResolutionError):
                resolve()

    def test_opt_in_and_invalid_input_before_transport(self):
        transport = Mock()
        for text, opt in ((ADDRESS, False), ('somewhere', True), ('https://evil.example', True),
                          ('Bad:* 12, 1234 AB Teststad',True)):
            with self.assertRaises(AddressResolutionError):
                resolve_address(text, transport, live_opt_in=opt)
        transport.get.assert_not_called()

    def test_allowlist_rejects_mutated_requests_before_connection(self):
        request = address_request(AddressInput.parse(ADDRESS))
        changes = [dict(url=request.url.replace('https:', 'http:')),
            dict(url=request.url.replace('api.pdok.nl','evil.example')),
            dict(url=request.url.replace('/free?', '/lookup?')),
            dict(url=request.url+'#fragment'), dict(url=request.url+'&rows=99'),
            dict(parameters=()), dict(headers=(('Cookie','secret'),)),
            dict(max_response_bytes=MAX_BYTES+1), dict(timeout_seconds=float('inf'))]
        with patch('bvc_ai.adapters.pdok_live.http.client.HTTPSConnection') as factory:
            for change in changes:
                with self.subTest(change=change), self.assertRaises(ValueError):
                    PDOKLocationTransport().get(replace(request, **change))
            factory.assert_not_called()

    def test_transport_uses_only_fixed_host_and_json_accept(self):
        request = address_request(AddressInput.parse(ADDRESS))
        wire = Mock(status=200)
        wire.getheaders.return_value = response().headers
        wire.read1.side_effect = io.BytesIO(response().body).read1
        conn = Mock()
        conn.getresponse.return_value = wire
        with patch('bvc_ai.adapters.pdok_live.http.client.HTTPSConnection', return_value=conn) as factory:
            self.assertEqual(PDOKLocationTransport().get(request).body, response().body)
        self.assertEqual(factory.call_args.args, ('api.pdok.nl',))
        self.assertEqual(conn.request.call_args.kwargs['headers'],
                         {'Accept':'application/json','Accept-Encoding':'identity'})

    def test_deterministic_analysis_and_tamper_rejection(self):
        _, evidence = resolve()
        extent, analysis = address_analysis(evidence)
        self.assertEqual(extent.bbox, (199873.456, 520539.123, 200373.456, 521039.123))
        self.assertEqual(address_analysis(copy.deepcopy(evidence)), (extent, analysis))
        validate_live_analysis(analysis, extent)
        for changed in (replace(analysis, role=GeometryRole.PROJECT_GEOMETRY),
                        replace(analysis, geometry_json='{"type":"Point","coordinates":[1,2]}')):
            with self.assertRaises(ValueError):
                validate_live_analysis(changed, extent)
        for key, value in (('raw_sha256','0'*64), ('request_url','https://evil.example'),
                           ('resolved', {}), ('origin', 'TESTDATA')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                address_analysis(dict(evidence, **{key:value}))

    def test_live_bag_bgt_transport_is_bound_to_validated_bbox(self):
        _, evidence = resolve()
        extent, analysis = address_analysis(evidence)
        request = PDOKBGTAdapter(None, collection_metadata_json=metadata('BAG/pand'),
                                 source_contract='BAG/pand').build_request(extent)
        transport = PDOKLiveGetTransport(source_contract='BAG/pand', analysis_scope=(extent,analysis))
        transport._validate_request(request)
        with self.assertRaises(ValueError):
            PDOKLiveGetTransport(source_contract='BAG/pand')._validate_request(request)
        with self.assertRaises(ValueError):
            PDOKLiveGetTransport(source_contract='BAG/pand',
                analysis_scope=(replace(extent,bbox=(1,2,3,4)),analysis))

    def test_mastenbroekweg_regression_scope_unchanged(self):
        extent, analysis = mastenbroekweg_analysis()
        self.assertEqual(','.join(str(n) for n in extent.bbox), BBOX)
        validate_live_analysis(analysis, extent)

    def test_generic_eight_collection_import_replay_and_reconstruction(self):
        (ROOT/'runtime/2d-live').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/2d-live') as temp:
            def transport(*, source_contract, analysis_scope):
                validate_live_analysis(analysis_scope[1], analysis_scope[0])
                self.assertNotEqual(','.join(map(str,analysis_scope[0].bbox)), BBOX)
                return SequenceTransport([profile_response(source_contract)], Timer())
            with patch.object(proof, 'PDOKLocationTransport', return_value=SequenceTransport([response()],Timer())), \
                 patch.object(proof, 'PDOKLiveGetTransport', side_effect=transport):
                result = proof.run_proof(Path(temp)/'proof', 'synthetic', live_opt_in=True, address_text=ADDRESS, address_backend='locatieserver')
            self.assertEqual(result['result'], 'PASS_WITH_FINDINGS', result)
            self.assertEqual(result['records'], 8)
            self.assertEqual(result['address_resolution'], 'PASS')
            self.assertEqual(result['replay'], 'PASS')
            self.assertTrue(result['complete'])
            self.assertIsNone(result['human_approval'])
            from verify_address_proof import verify
            self.assertEqual(verify(Path(temp)/'proof')['result'], 'PASS')

    def test_failed_resolution_never_starts_bag_bgt(self):
        (ROOT/'runtime/2d-live').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/2d-live') as temp:
            with patch.object(proof, 'PDOKLocationTransport', return_value=SequenceTransport([response(numFound=0,docs=[])],Timer())), \
                 patch.object(proof, 'PDOKLiveGetTransport') as transport:
                result = proof.run_proof(Path(temp)/'proof', 'synthetic', live_opt_in=True, address_text=ADDRESS, address_backend='locatieserver')
            self.assertEqual(result['result'], 'BLOCKED')
            transport.assert_not_called()
            self.assertTrue((Path(temp)/'proof/address-evidence.json').exists())
