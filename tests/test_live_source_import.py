"""Synthetic provider-origin evidence only; sockets blocked in every test."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import test_source_import as base_tests
TID = base_tests.TID
from test_pdok_bgt import METADATA
from test_pdok_bgt_fetch import response, SequenceTransport, Timer
from bvc_ai.adapters.pdok_bgt import RD_URI
from bvc_ai.adapters.pdok_live import BBOX
from bvc_ai.adapters.source_transport import ResponseOrigin
from bvc_ai.application.source_import import SourceImportService, _A02_SOURCE_IMPORT_CAPABILITY
from bvc_ai.application.source_replay import SourceReplayService
from bvc_ai.application.live_source_validation import PURPOSE, ANALYSIS_ORIGIN
from bvc_ai.domain.sources import FetchExtent, CRSMetadata, GeometryRecord, GeometryRole
from bvc_ai.domain.source_hashing import geometry_structural_hash, CANONICALIZATION_VERSION


from bvc_ai.application.live_source_validation import mastenbroekweg_analysis


class LiveImportTests(unittest.TestCase):
    trusted_state = base_tests.SourceImportTests.trusted_state
    assert_failure_unchanged = base_tests.SourceImportTests.assert_failure_unchanged

    def setUp(self):
        base_tests.SourceImportTests.setUp(self)
        self.extent, self.live_analysis = mastenbroekweg_analysis()
        with self.store.db:
            self.store.db.execute('BEGIN IMMEDIATE')
            self.sources.add_geometry(self.live_analysis)
        self.provider = replace(response(), origin=ResponseOrigin.PROVIDER_RESPONSE)

    def importer(self, responses=None, live=True):
        timer = Timer()
        return SourceImportService(self.store, SequenceTransport(
            [self.provider] if responses is None else responses, timer),
            collection_metadata_json=json.dumps(METADATA), capability=_A02_SOURCE_IMPORT_CAPABILITY,
            live_mastenbroekweg=live, monotonic=timer, sleep=timer.sleep)

    def test_explicit_live_origin_import_and_offline_replay(self):
        binding = self.importer().import_source(TID, 'synthetic/live-origin', self.extent)
        result = SourceReplayService(self.store).verify(binding.snapshot_id)
        self.assertEqual(json.loads(result.snapshot.provenance_json)['source_status'],
                         ResponseOrigin.PROVIDER_RESPONSE)
        task = self.store.get(TID)
        self.assertEqual(task['objects'][-1]['source_status'], ResponseOrigin.PROVIDER_RESPONSE)
        self.assertEqual(task['objects'][-1]['geometry_status'], 'EXISTING_VALIDATED')
        self.assertEqual(task['outputs'][-1]['source_status'], ResponseOrigin.PROVIDER_RESPONSE)
        self.assertIsNone(task['human_approval'])
        event = self.store.events(TID)[-1]
        self.assertEqual(event['details']['source_status'], ResponseOrigin.PROVIDER_RESPONSE)

    def test_default_gate_rejects_provider_origin(self):
        # Old TESTDATA extent passes old gate, provider evidence must still fail.
        from test_pdok_bgt import EXTENT
        self.assert_failure_unchanged(lambda: self.importer(live=False).import_source(TID, 'blocked', EXTENT))

    def test_live_gate_rejects_testdata_origin(self):
        self.assert_failure_unchanged(lambda: self.importer([response()]).import_source(TID, 'blocked', self.extent))

    def test_live_gate_rejects_other_bbox_and_project_geometry(self):
        self.assert_failure_unchanged(lambda: self.importer().import_source(
            TID, 'blocked', replace(self.extent, bbox=(0,0,10,10))))
        with patch.object(self.sources.__class__, 'geometry', return_value=replace(
                self.live_analysis, role=GeometryRole.PROJECT_GEOMETRY)):
            self.assert_failure_unchanged(lambda: self.importer().import_source(TID, 'blocked', self.extent))

    def test_provider_contract_failures_do_not_promote(self):
        document = json.loads(self.provider.body)
        for changes in ({'coordRefSys': None}, {'numberReturned': 99}, {'numberMatched': 99},
                        {'type': 'Other'}, {'links': [{'rel':'next','href':'https://evil.example/'}]}):
            with self.subTest(changes=changes):
                candidate = replace(self.provider, body=json.dumps(dict(document, **changes)).encode())
                self.assert_failure_unchanged(lambda: self.importer([candidate]).import_source(TID, 'blocked', self.extent))

    def test_changed_capture_metadata_or_raw_rejected(self):
        importer = self.importer()
        original = importer._adapter.fetch
        for mutation in ('url', 'parameters', 'bytes', 'origin'):
            def altered(*args, **kwargs):
                fetched = original(*args, **kwargs)
                capture = fetched.captures[0]
                if mutation == 'url':
                    capture = replace(capture, request=replace(capture.request, url=capture.request.url.replace('api.pdok.nl','evil.example')))
                elif mutation == 'parameters':
                    capture = replace(capture, request=replace(capture.request, parameters=()))
                elif mutation == 'bytes':
                    capture = replace(capture, response=replace(capture.response, body=b'{}'))
                else:
                    capture = replace(capture, response=replace(capture.response, origin=ResponseOrigin.TESTDATA))
                return replace(fetched, captures=(capture,))
            with self.subTest(mutation=mutation):
                importer = self.importer()
                original = importer._adapter.fetch
                with patch.object(importer._adapter, 'fetch', side_effect=altered):
                    self.assert_failure_unchanged(lambda: importer.import_source(TID, 'blocked', self.extent))

    def test_replay_rejects_origin_relabel_and_bytes(self):
        self.importer().import_source(TID, 'synthetic/live-origin', self.extent)
        evidence = SourceReplayService(self.store).evidence('synthetic/live-origin')
        capture = evidence.captures[0]
        for changed in (replace(capture.response, origin=ResponseOrigin.TESTDATA),
                        replace(capture.response, body=b'{}')):
            with self.assertRaises(ValueError):
                SourceReplayService.reconstruct(replace(evidence, captures=(replace(capture, response=changed),)))

    def test_live_multipage_and_retry_replay(self):
        importer = self.importer()
        initial = importer._adapter.build_request(self.extent).url
        pages = [replace(response(status=503), origin=ResponseOrigin.PROVIDER_RESPONSE),
                 replace(response(next_link=initial + '&cursor=two'), origin=ResponseOrigin.PROVIDER_RESPONSE),
                 replace(response('two'), origin=ResponseOrigin.PROVIDER_RESPONSE)]
        binding = self.importer(pages).import_source(TID, 'synthetic/multipage', self.extent)
        replay = SourceReplayService(self.store).verify(binding.snapshot_id)
        self.assertEqual(replay.snapshot.page_count, 2)
        self.assertEqual(replay.snapshot.feature_count, 2)
        self.assertEqual(len(replay.raw_responses), 3)

    def test_live_continuation_must_preserve_query_scope(self):
        candidate = replace(response(next_link='?cursor=two'), origin=ResponseOrigin.PROVIDER_RESPONSE)
        self.assert_failure_unchanged(lambda: self.importer([candidate, self.provider]).import_source(
            TID, 'blocked', self.extent))

    def test_live_reparse_rejects_changed_mapping(self):
        importer = self.importer()
        original = importer._adapter.fetch
        def altered(*args, **kwargs):
            fetched = original(*args, **kwargs)
            return replace(fetched, features=(replace(fetched.features[0], properties_json='{}'),))
        with patch.object(importer._adapter, 'fetch', side_effect=altered):
            self.assert_failure_unchanged(lambda: importer.import_source(TID, 'blocked', self.extent))

    def test_live_reimport_noop_and_archive_immutable(self):
        binding = self.importer().import_source(TID, 'synthetic/live-origin', self.extent)
        second = self.importer().import_source(TID, 'synthetic/live-origin', self.extent)
        self.assertEqual(binding, second)
        snapshot = self.sources.snapshot(binding.snapshot_id)
        with self.assertRaises(ValueError), self.store.db:
            self.store.db.execute('BEGIN IMMEDIATE')
            self.sources.add_snapshot(replace(snapshot, provenance_json='{"tampered":true}'))
