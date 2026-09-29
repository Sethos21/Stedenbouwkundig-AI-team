"""Synthetic contract evidence only; all network calls blocked."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from pathlib import Path

import test_source_import as base
from test_pdok_bgt_fetch import response, SequenceTransport, Timer
from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter, RD_URI, FetchBudgets
from bvc_ai.adapters.pdok_live import PDOKLiveGetTransport, validate_live_request
from bvc_ai.adapters.source_transport import ResponseOrigin
from bvc_ai.application.source_import import SourceImportService, _A02_SOURCE_IMPORT_CAPABILITY
from bvc_ai.application.source_replay import SourceReplayService
from bvc_ai.application.live_source_validation import mastenbroekweg_analysis
from bvc_ai.domain.source_profiles import BGT_COLLECTIONS, source_profile
from bvc_ai.infrastructure.store import Store
from bvc_ai.infrastructure.source_store import SourceStore


def metadata(key):
    return json.dumps({'id': source_profile(key).collection, 'crs': [RD_URI], 'storageCrs': RD_URI,
                       'title': 'SYNTHETIC CONTRACT TEST'})


def profile_response(key, identity='one', next_link=None, empty=False):
    item = response(identity, next_link)
    document = json.loads(item.body)
    feature = document['features'][0]
    feature['properties']['version'] = 'synthetic-version'
    if source_profile(key).geometry_type == 'MultiPolygon':
        feature['place'] = dict(type='MultiPolygon', coordinates=[feature['place']['coordinates']])
    if empty:
        document.update(features=[], numberReturned=0)
    return replace(item, body=json.dumps(document).encode(), origin=ResponseOrigin.PROVIDER_RESPONSE)


class SourceProfileTests(unittest.TestCase):
    trusted_state = base.SourceImportTests.trusted_state
    assert_failure_unchanged = base.SourceImportTests.assert_failure_unchanged

    def setUp(self):
        base.SourceImportTests.setUp(self)
        self.extent, analysis = mastenbroekweg_analysis()
        with self.store.db:
            self.store.db.execute('BEGIN IMMEDIATE')
            self.sources.add_geometry(analysis)

    def importer(self, key, responses=None):
        timer = Timer()
        self.transport = SequenceTransport(responses or [profile_response(key)], timer)
        return SourceImportService(self.store, self.transport, collection_metadata_json=metadata(key),
                                   capability=_A02_SOURCE_IMPORT_CAPABILITY, source_contract=key,
                                   live_mastenbroekweg=True, monotonic=timer, sleep=timer.sleep)

    def test_all_bgt_contracts_import_replay_reconstruct(self):
        refs = set()
        for collection in BGT_COLLECTIONS:
            key = 'BGT/' + collection
            binding = self.importer(key).import_source(base.TID, key, self.extent)
            replay = SourceReplayService(self.store)
            result = replay.verify(key)
            self.assertEqual(result.snapshot.collection, collection)
            self.assertEqual(result.snapshot.endpoint, source_profile(key).items_url)
            refs.add(result.features[0].geometry_ref)
            with StoreClosing(Path(self.temp.name) / collection) as target:
                rebuilt = replay.reconstruct_into(replay.evidence(key), target)
                self.assertEqual(rebuilt, result)
                self.assertFalse(target.list())
                self.assertEqual(target.db.execute('SELECT count(*) FROM source_revision_bindings').fetchone()[0], 0)
            self.assertEqual(self.store.get(base.TID)['active_revisions']['A02'], binding.revision_id)
        self.assertEqual(len(refs), len(BGT_COLLECTIONS))
        self.assertIsNone(self.store.get(base.TID)['human_approval'])

    def test_empty_complete_collection_is_valid(self):
        key = 'BGT/waterdeel'
        self.importer(key, [profile_response(key, empty=True)]).import_source(base.TID, 'empty', self.extent)
        self.assertEqual(SourceReplayService(self.store).verify('empty').snapshot.feature_count, 0)

    def test_unknown_contract_and_metadata_mismatch(self):
        for key in ('BGT/anything', 'BAG/pand', 'https://evil.example/', {}, 'bgt/pand'):
            with self.assertRaises(ValueError):
                source_profile(key)
        with self.assertRaises(ValueError):
            PDOKBGTAdapter(None, collection_metadata_json=metadata('BGT/pand'), source_contract='BGT/wegdeel')
        with self.assertRaises(PermissionError):
            SourceImportService(self.store, None, collection_metadata_json=metadata('BGT/pand'),
                                source_contract='BGT/pand')

    def test_cross_collection_or_query_change_stops_before_transport(self):
        key = 'BGT/wegdeel'
        importer = self.importer(key)
        url = importer._adapter.build_request(self.extent).url
        for bad in (url.replace('/wegdeel/', '/pand/'), '?cursor=two',
                    url.replace('limit=1000', 'limit=999') + '&cursor=two',
                    url + '&limit=1000&cursor=two', url.replace('api.pdok.nl', 'evil.example')):
            importer = self.importer(key, [profile_response(key, next_link=bad)])
            self.assert_failure_unchanged(lambda: importer.import_source(base.TID, 'bad', self.extent))
            self.assertEqual(len(self.transport.requests), 1)

    def test_all_live_endpoint_allowlists_reject_before_connection(self):
        with patch('bvc_ai.adapters.pdok_live.http.client.HTTPSConnection') as connection:
            for collection in BGT_COLLECTIONS:
                key = 'BGT/' + collection
                request = self.importer(key)._adapter.build_request(self.extent)
                validate_live_request(request, key)
                for bad in (replace(request, url=request.url.replace('api.pdok.nl', 'evil.example')),
                            replace(request, url=request.url.replace('/collections/', '/other/')),
                            replace(request, parameters=())):
                    with self.assertRaises(ValueError):
                        PDOKLiveGetTransport(source_contract=key).get(bad)
            connection.assert_not_called()

    def test_invalid_geometry_version_or_origin_never_promotes(self):
        key = 'BGT/wegdeel'
        for mutation in ('geometry', 'version', 'origin'):
            item = profile_response(key)
            document = json.loads(item.body)
            if mutation == 'geometry':
                document['features'][0]['place'] = dict(type='Point', coordinates=[1, 1])
            if mutation == 'version':
                del document['features'][0]['properties']['version']
            item = replace(item, body=json.dumps(document).encode(),
                           origin=ResponseOrigin.TESTDATA if mutation == 'origin' else item.origin)
            self.assert_failure_unchanged(lambda: self.importer(key, [item]).import_source(base.TID, 'bad', self.extent))

    def test_pagination_retry_budget_and_idempotence(self):
        key = 'BGT/wegdeel'
        url = self.importer(key)._adapter.build_request(self.extent).url
        items = [replace(profile_response(key), status=503),
                 profile_response(key, next_link=url + '&cursor=two'), profile_response(key, 'two')]
        first = self.importer(key, items).import_source(base.TID, 'multi', self.extent)
        result = SourceReplayService(self.store).verify('multi')
        self.assertEqual((len(result.pages), len(result.features), len(result.raw_responses)), (2, 2, 3))
        second = self.importer(key, items).import_source(base.TID, 'multi', self.extent)
        self.assertEqual(first, second)
        self.assert_failure_unchanged(lambda: self.importer(key, items).import_source(
            base.TID, 'budget', self.extent, budgets=FetchBudgets(max_pages=1)))

    def test_publication_failure_rolls_back_and_mapping_tamper_rejected(self):
        key = 'BGT/wegdeel'
        with patch.object(SourceStore, '_bind_revision', side_effect=OSError('Injected')):
            self.assert_failure_unchanged(lambda: self.importer(key).import_source(base.TID, 'rollback', self.extent))
        importer = self.importer(key)
        original = importer._adapter.fetch
        def altered(*args, **kwargs):
            fetched = original(*args, **kwargs)
            return replace(fetched, features=(replace(fetched.features[0], properties_json='{}'),))
        with patch.object(importer._adapter, 'fetch', side_effect=altered):
            self.assert_failure_unchanged(lambda: importer.import_source(base.TID, 'tamper', self.extent))

    def test_replay_rejects_profile_relabel(self):
        key = 'BGT/wegdeel'
        self.importer(key).import_source(base.TID, key, self.extent)
        evidence = SourceReplayService(self.store).evidence(key)
        provenance = json.loads(evidence.snapshot.provenance_json)
        provenance['source_contract'] = 'BGT/pand'
        with self.assertRaises(ValueError):
            SourceReplayService.reconstruct(replace(evidence, snapshot=replace(
                evidence.snapshot, provenance_json=json.dumps(provenance))))


class StoreClosing:
    def __init__(self, path):
        self.store = Store(path)
    def __enter__(self):
        return self.store
    def __exit__(self, *args):
        self.store.close()
