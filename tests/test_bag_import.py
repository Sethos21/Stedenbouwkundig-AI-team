"""Synthetic BAG evidence only; inherited setup blocks socket/DNS."""
import json
import unittest
from dataclasses import replace
import test_source_profiles as helpers
from test_source_profiles import profile_response, StoreClosing
from test_source_import import TID
from bvc_ai.application.source_replay import SourceReplayService
from bvc_ai.adapters.pdok_live import PDOKLiveGetTransport, validate_live_request
from bvc_ai.domain.source_profiles import source_profile
from unittest.mock import patch
from pathlib import Path


class BAGImportTests(unittest.TestCase):
    setUp = helpers.SourceProfileTests.setUp
    importer = helpers.SourceProfileTests.importer
    trusted_state = helpers.SourceProfileTests.trusted_state
    assert_failure_unchanged = helpers.SourceProfileTests.assert_failure_unchanged

    def test_both_collections_preserve_records_properties_and_replay(self):
        for key in ('BAG/pand', 'BAG/verblijfsobject'):
            binding = self.importer(key).import_source(TID, key, self.extent)
            replay = SourceReplayService(self.store)
            result = replay.verify(binding.snapshot_id)
            self.assertEqual(result.snapshot.dataset, 'BAG')
            expected = json.loads(profile_response(key).body)['features'][0]['properties']
            self.assertEqual(json.loads(result.features[0].properties_json), expected)
            self.assertEqual(json.loads(result.geometries[-1].provenance_json)['dataset'], 'BAG')
            with StoreClosing(Path(self.temp.name) / key.replace('/', '-')) as target:
                self.assertEqual(replay.reconstruct_into(replay.evidence(key), target), result)
                self.assertFalse(target.list())

    def test_bag_never_overwrites_bgt_with_same_feature_id(self):
        self.importer('BGT/pand').import_source(TID, 'bgt', self.extent)
        bgt = self.sources.features('bgt')[0]
        old = self.sources.geometry(bgt.geometry_ref)
        self.importer('BAG/pand').import_source(TID, 'bag', self.extent)
        bag = self.sources.features('bag')[0]
        self.assertEqual(bgt.source_id, bag.source_id)
        self.assertNotEqual(bgt.geometry_ref, bag.geometry_ref)
        self.assertEqual(self.sources.geometry(bgt.geometry_ref), old)

    def test_identity_geometry_properties_and_relation_types_fail_closed(self):
        key = 'BAG/verblijfsobject'
        for prop, value in (('identificatie', None), ('oppervlakte', True), ('oppervlakte', -1), ('oppervlakte', 1.5),
                            ('pand', 'guessed'), ('pand', [None]), ('gebruiksdoel', [])):
            item = profile_response(key)
            document = json.loads(item.body)
            document['features'][0]['properties'][prop] = value
            changed = replace(item, body=json.dumps(document).encode())
            self.assert_failure_unchanged(lambda: self.importer(key, [changed]).import_source(TID, 'bad', self.extent))
        wrong = profile_response('BAG/pand')
        self.assert_failure_unchanged(lambda: self.importer(key, [wrong]).import_source(TID, 'bad', self.extent))

    def test_bag_allowlist_and_next_cannot_cross_collection(self):
        for key in ('BAG/pand', 'BAG/verblijfsobject'):
            importer = self.importer(key)
            request = importer._adapter.build_request(self.extent)
            validate_live_request(request, key)
            with patch('bvc_ai.adapters.pdok_live.http.client.HTTPSConnection') as conn:
                with self.assertRaises(ValueError):
                    PDOKLiveGetTransport(source_contract=key).get(replace(request, url=request.url.replace('/v2/', '/v1/')))
                conn.assert_not_called()
            bad = profile_response(key, next_link=source_profile('BGT/pand').items_url)
            self.assert_failure_unchanged(lambda: self.importer(key, [bad]).import_source(TID, 'bad', self.extent))
            self.assertEqual(len(self.transport.requests), 1)

    def test_bag_empty_collection_and_reimport(self):
        for key in ('BAG/pand', 'BAG/verblijfsobject'):
            item = profile_response(key, empty=True)
            first = self.importer(key, [item]).import_source(TID, key, self.extent)
            self.assertEqual(self.importer(key, [item]).import_source(TID, key, self.extent), first)
            self.assertEqual(SourceReplayService(self.store).verify(key).features, ())
