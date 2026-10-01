"""Synthetic BAG API fixtures; never reads a real credential or network."""
import copy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from bvc_ai.adapters import bag_individual as bag
from bvc_ai.adapters.pdok_location import AddressResolutionError
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin
from bvc_ai.application.live_source_validation import address_analysis, compare_address_evidence
from test_pdok_location import ADDRESS, ROOT, proof, resolve as legacy_resolve
from test_source_profiles import profile_response
from test_pdok_bgt_fetch import SequenceTransport, Timer

DOC = dict(openbareRuimteNaam='Voorbeeldstraat', huisnummer=12, postcode='1234AB',
    woonplaatsNaam='Teststad', nummeraanduidingIdentificatie='0123200000000001',
    adresseerbaarObjectIdentificatie='0123010000000001', openbareRuimteIdentificatie='0123300000000001',
    woonplaatsIdentificatie='1234', pandIdentificaties=['0123100000000001'],
    typeAdresseerbaarObject='Verblijfsobject',
    adresseerbaarObjectGeometrie={'punt':{'type':'Point','coordinates':[200123.456,520789.123,0]}})


def response(doc=None, docs=None, **changes):
    data = {'_embedded':{'adressen':docs if docs is not None else [DOC if doc is None else doc]}}
    data.update(changes)
    return HttpResponse(200,(('Content-Type','application/hal+json'),),json.dumps(data).encode(),ResponseOrigin.PROVIDER_RESPONSE)


def resolve(item=None):
    return bag.resolve_address(ADDRESS,SequenceTransport([response() if item is None else item],Timer()),live_opt_in=True)


class BAGBootstrapTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket','socket.create_connection','socket.getaddrinfo'):
            guard=patch(name,side_effect=AssertionError('SYNTHETIC: NETWORK BLOCKED'))
            guard.start(); self.addCleanup(guard.stop)

    def test_official_identity_geometry_and_offline_evidence(self):
        location,evidence=resolve()
        self.assertEqual(location.pand_ids,('0123100000000001',))
        self.assertEqual(location.source_coordinates,(200123.456,520789.123,0))
        self.assertEqual(bag.replay_address(evidence),location)
        extent,analysis=address_analysis(evidence)
        self.assertEqual(extent.bbox,(199873.456,520539.123,200373.456,521039.123))
        self.assertEqual(address_analysis(json.loads(json.dumps(evidence))),(extent,analysis))
        self.assertEqual(json.loads(analysis.provenance_json)['source_coordinates_full'],list(location.source_coordinates))
        for field,value in [('resolved',{}),('raw_sha256','0'*64),('request_url','https://example.org'),('origin','TESTDATA')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                bag.replay_address(dict(evidence,**{field:value}))

    def test_ambiguous_absent_incomplete_and_malformed_fail_closed(self):
        for item in [response(docs=[]),response(docs=[DOC,DOC]),response(_links={'next':{'href':'anything'}}),
                     replace(response(),body=b'{}'),replace(response(),body=b'{"x":1,"x":2}'),
                     replace(response(),status=401),replace(response(),status=302),
                     replace(response(),body=b' '* (bag.MAX_BYTES+1)),
                     replace(response(),headers=(('Content-Type','application/hal+json'),('Content-Crs','epsg:4326')))]:
            with self.subTest(item=item.status),self.assertRaises(AddressResolutionError): resolve(item)

    def test_mismatch_missing_ids_uncertainty_and_nonpoint_fail_closed(self):
        for change in [{'openbareRuimteNaam':'Other'},{'huisnummer':13},{'huisletter':'A'},
                       {'pandIdentificaties':[]},{'pandIdentificaties':['0123010000000001']},
                       {'nummeraanduidingIdentificatie':'invalid'},{'inonderzoek':{'huisnummer':True}},
                       {'typeAdresseerbaarObject':'Ligplaats'},{'adresseerbaarObjectGeometrie':{}},
                       {'adresseerbaarObjectGeometrie':{'punt':{'type':'Point','coordinates':[5,52]}}}]:
            with self.subTest(change=change),self.assertRaises(AddressResolutionError): resolve(response(dict(DOC,**change)))

    def test_allowlist_before_secret_access(self):
        request=bag.request_for(bag.AddressInput.parse(ADDRESS))
        bag.validate_request(request)
        with patch.object(bag.os.environ,'get',side_effect=AssertionError('NO KEY READ')):
            for change in [{'url':request.url.replace('https:','http:')},{'url':request.url.replace(bag.HOST,'evil.example')},
                           {'url':request.url.replace('adressenuitgebreid','panden')},{'parameters':()},
                           {'headers':(('X-Api-Key','synthetic'),)},{'max_response_bytes':bag.MAX_BYTES+1}]:
                with self.subTest(change=change),self.assertRaises(ValueError): bag.BAGLiveTransport().get(replace(request,**change))

    def test_auth_header_only_and_credential_echo_discarded(self):
        request=bag.request_for(bag.AddressInput.parse(ADDRESS))
        secret='SYNTHETIC-NOT-A-REAL-KEY'
        for echoed in (False,True):
            wire=Mock(status=200)
            wire.getheaders.return_value=response().headers
            wire.read1.side_effect=io.BytesIO(secret.encode() if echoed else response().body).read1
            conn=Mock(); conn.getresponse.return_value=wire
            with patch.dict(bag.os.environ,{'BAG_API_KEY':secret}),patch.object(bag.http.client,'HTTPSConnection',return_value=conn):
                if echoed:
                    with self.assertRaises(bag.BAGTransportError) as caught: bag.BAGLiveTransport().get(request)
                    self.assertNotIn(secret,str(caught.exception))
                else:
                    self.assertEqual(bag.BAGLiveTransport().get(request).body,response().body)
            self.assertEqual(conn.request.call_args.kwargs['headers']['X-Api-Key'],secret)
            self.assertNotIn(secret,repr(request))

    def test_transport_deadline_bytes_and_upstream_failure_are_closed(self):
        request=bag.request_for(bag.AddressInput.parse(ADDRESS))
        for failure in ('bytes','network','deadline'):
            wire=Mock(status=200); wire.getheaders.return_value=response().headers
            wire.read1.side_effect=io.BytesIO(b' '*(bag.MAX_BYTES+1)).read1
            conn=Mock(); conn.getresponse.return_value=wire
            if failure=='network': conn.connect.side_effect=OSError('SYNTHETIC-SECRET')
            with patch.dict(bag.os.environ,{'BAG_API_KEY':'SYNTHETIC-SECRET'}),patch.object(bag.http.client,'HTTPSConnection',return_value=conn):
                if failure=='deadline':
                    with patch.object(bag.queue.Queue,'get',side_effect=bag.queue.Empty):
                        with self.assertRaises(bag.BAGTransportError) as caught: bag.BAGLiveTransport().get(request)
                else:
                    with self.assertRaises(bag.BAGTransportError) as caught: bag.BAGLiveTransport().get(request)
            self.assertNotIn('SYNTHETIC-SECRET',str(caught.exception))

    def test_missing_key_opt_in_and_transport_errors_safe(self):
        with patch.dict(bag.os.environ,{},clear=True),patch.object(bag.http.client,'HTTPSConnection') as conn:
            with self.assertRaises(bag.BAGTransportError): bag.BAGLiveTransport().get(bag.request_for(bag.AddressInput.parse(ADDRESS)))
            conn.assert_not_called()
        for error in (TimeoutError('SYNTHETIC-SECRET'),bag.BAGTransportError('SYNTHETIC-SECRET')):
            with self.assertRaises(AddressResolutionError) as caught: resolve(error)
            self.assertNotIn('SYNTHETIC-SECRET',json.dumps(caught.exception.evidence))
        transport=Mock()
        with self.assertRaises(AddressResolutionError): bag.resolve_address(ADDRESS,transport)
        transport.get.assert_not_called()

    def test_comparison_prevents_import_without_fallback(self):
        _,baseline=legacy_resolve()
        _,current=resolve()
        self.assertEqual(compare_address_evidence(current,baseline)['result'],'PASS')
        changed=copy.deepcopy(DOC); changed['adresseerbaarObjectGeometrie']['punt']['coordinates'][0]+=1
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/2d-live') as temp:
            with patch.object(bag,'BAGLiveTransport',return_value=SequenceTransport([response(changed)],Timer())),patch.object(proof,'PDOKLiveGetTransport') as ogc,patch.object(proof,'PDOKLocationTransport') as fallback:
                result=proof.run_proof(Path(temp)/'proof','synthetic',live_opt_in=True,address_text=ADDRESS,comparison_evidence=baseline)
            self.assertEqual(result['result'],'BLOCKED'); ogc.assert_not_called(); fallback.assert_not_called()

    def test_default_bag_eight_collection_import_and_offline_reconstruction(self):
        _,baseline=legacy_resolve()
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/2d-live') as temp:
            with patch.object(bag,'BAGLiveTransport',return_value=SequenceTransport([response()],Timer())),patch.object(proof,'PDOKLiveGetTransport',side_effect=lambda **kw: SequenceTransport([profile_response(kw['source_contract'])],Timer())),patch.object(proof,'PDOKLocationTransport') as fallback:
                result=proof.run_proof(Path(temp)/'proof','synthetic',live_opt_in=True,address_text=ADDRESS,comparison_evidence=baseline)
            fallback.assert_not_called()
            self.assertEqual(result['result'],'PASS_WITH_FINDINGS',result)
            self.assertEqual(result['records'],8); self.assertEqual(result['replay'],'PASS')
            from verify_address_proof import verify
            self.assertEqual(verify(Path(temp)/'proof')['result'],'PASS')
