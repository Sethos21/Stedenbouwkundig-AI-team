"""Phase 5: replay stored Phase 4 TESTDATA with socket/DNS blocked."""
import json
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import test_source_import as phase4
from test_pdok_bgt_fetch import response
from bvc_ai.application.source_replay import SourceReplayService
from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter
from bvc_ai.domain.source_hashing import raw_response_hash, geometry_structural_hash
from bvc_ai.domain.sources import RawResponse
from bvc_ai.infrastructure.store import Store
from bvc_ai.infrastructure.source_store import SourceStore


class SourceReplayTests(unittest.TestCase):
    service = phase4.SourceImportTests.service
    run_import = phase4.SourceImportTests.run_import

    def setUp(self):
        phase4.SourceImportTests.setUp(self)
        self.run_import([replace(response(status=503), body=b'TESTDATA retry error'),
                         response(next_link='?cursor=two&opaque=a&opaque=b'), response('two')])
        self.replay = SourceReplayService(self.store)
        self.evidence = self.replay.evidence('test/snapshot')
        self.original = self.dump(self.store)

    def tearDown(self):
        self.assertEqual(self.dump(self.store), self.original)

    @staticmethod
    def dump(store):
        return tuple(store.db.iterdump())

    def target(self):
        directory = tempfile.TemporaryDirectory(dir=phase4.ROOT / '.tools/test-runs')
        self.addCleanup(directory.cleanup)
        store = Store(directory.name)
        self.addCleanup(store.close)
        return store

    def test_successful_offline_replay_uses_existing_parser_no_fetch(self):
        original = PDOKBGTAdapter._parse
        with patch.object(PDOKBGTAdapter, 'fetch', side_effect=AssertionError('No fetch')), \
                patch.object(PDOKBGTAdapter, 'fetch_page', side_effect=AssertionError('No fetch')), \
                patch.object(PDOKBGTAdapter, '_parse', autospec=True, side_effect=original) as parser:
            result = self.replay.verify('test/snapshot')
        self.assertEqual(parser.call_count, 2)
        self.assertEqual(len(result.pages), 2)
        self.assertEqual(len(result.raw_responses), 3)

    def test_exact_raw_bytes_and_deterministic_hashes(self):
        first = self.replay.verify('test/snapshot')
        second = self.replay.verify('test/snapshot')
        self.assertEqual(first, second)
        self.assertEqual(first.snapshot.snapshot_manifest_hash, self.evidence.snapshot.snapshot_manifest_hash)
        for raw in first.raw_responses:
            self.assertEqual(raw.body, self.sources.raw(raw.raw_response_hash).body)
            self.assertEqual(raw_response_hash(raw.body), raw.raw_response_hash)
        for geometry in first.geometries:
            self.assertEqual(geometry_structural_hash(geometry.geometry_json, geometry.crs_metadata),
                             geometry.geometry_structural_hash)

    def test_pages_features_geometries_and_provenance_equal(self):
        result = self.replay.verify('test/snapshot')
        self.assertEqual(result.pages, tuple(self.sources.pages('test/snapshot')))
        self.assertEqual(result.features, tuple(self.sources.features('test/snapshot')))
        for geometry in result.geometries:
            self.assertEqual(geometry, self.sources.geometry(geometry.geometry_ref))
        provenance = json.loads(result.features[0].provenance_json)
        self.assertEqual((provenance['provider'], provenance['dataset'], provenance['collection']),
                         ('PDOK', 'BGT', 'pand'))
        self.assertEqual(provenance['source_status'], 'TESTDATA')

    def test_empty_storage_reconstruction_and_idempotent_repeat(self):
        target = self.target()
        self.assertEqual(target.db.execute('SELECT * FROM source_snapshots').fetchall(), [])
        result = SourceReplayService.reconstruct_into(self.evidence, target)
        baseline = self.dump(target)
        self.assertEqual(SourceReplayService.reconstruct_into(self.evidence, target), result)
        self.assertEqual(self.dump(target), baseline)
        archive = SourceStore(target)
        self.assertEqual(archive.snapshot('test/snapshot'), self.evidence.snapshot)
        self.assertEqual(archive.pages('test/snapshot'), self.sources.pages('test/snapshot'))
        self.assertEqual(archive.features('test/snapshot'), self.sources.features('test/snapshot'))
        self.assertEqual(target.db.execute('SELECT * FROM tasks').fetchall(), [])
        self.assertEqual(target.db.execute('SELECT * FROM source_revision_bindings').fetchall(), [])
        self.assertEqual(target.events(), [])

    def test_reconstruction_does_not_read_original_storage(self):
        evidence = self.evidence
        target = self.target()
        with patch.object(self.store, 'events', side_effect=AssertionError('No original read')), \
                patch.object(SourceStore, 'raw', side_effect=AssertionError('No original read')):
            result = SourceReplayService.reconstruct_into(evidence, target)
        self.assertEqual(result.snapshot, evidence.snapshot)

    def test_original_cannot_be_used_as_replay_target(self):
        with self.assertRaises(ValueError):
            self.replay.reconstruct_into(self.evidence, self.store)

    def test_missing_raw_fails_closed(self):
        with patch.object(SourceStore, 'raw', side_effect=ValueError('Missing raw')), self.assertRaises(ValueError):
            self.replay.verify('test/snapshot')

    def test_corrupt_raw_and_raw_hash_mismatch(self):
        for change in ({'body': b'corrupt'}, {'raw_response_hash': '0' * 64}):
            with self.subTest(change=change):
                raw = RawResponse(self.evidence.captures[1].raw.raw_response_hash,
                                  self.evidence.captures[1].raw.body)
                for key, value in change.items():
                    object.__setattr__(raw, key, value)
                captures = list(self.evidence.captures)
                captures[1] = replace(captures[1], raw=raw)
                with self.assertRaises(ValueError):
                    self.replay.reconstruct(replace(self.evidence, captures=tuple(captures)))

    def test_response_body_differs_from_raw(self):
        captures = list(self.evidence.captures)
        captures[1] = replace(captures[1], response=replace(captures[1].response, body=b'other'))
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=tuple(captures)))

    def test_snapshot_manifest_mismatch(self):
        snapshot = replace(self.evidence.snapshot, snapshot_manifest_hash='0' * 64)
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, snapshot=snapshot))

    def test_geometry_hash_mismatch(self):
        analysis = replace(self.evidence.analysis, geometry_structural_hash='0' * 64)
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, analysis=analysis))

    def test_stored_feature_geometry_hash_or_provenance_mismatch(self):
        original = SourceStore.geometry
        for changes in ({'geometry_structural_hash': '0' * 64}, {'provenance_json': '{"tampered":true}'}):
            with self.subTest(changes=changes):
                def altered(store, ref):
                    value = original(store, ref)
                    return value if ref == self.evidence.analysis.geometry_ref else replace(value, **changes)
                with patch.object(SourceStore, 'geometry', altered), self.assertRaises(ValueError):
                    self.replay.verify('test/snapshot')

    def test_crs_mismatch(self):
        captures = list(self.evidence.captures)
        response = captures[1].response
        captures[1] = replace(captures[1], response=replace(response, headers=(
            ('Content-Type', 'application/vnd.ogc.fg+json'), ('Content-Crs', 'EPSG:4326'))))
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=tuple(captures)))

    def test_provenance_profile_mismatch(self):
        for change in ({'provider': 'invented'}, {'collection': 'wegdeel'},
                       {'parser_version': 'unknown'}, {'provenance_json': '{"source_status":"REAL"}'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.replay.reconstruct(replace(self.evidence, snapshot=replace(self.evidence.snapshot, **change)))

    def test_missing_capture_evidence(self):
        with patch.object(self.store, 'events', return_value=[]), self.assertRaises(ValueError):
            self.replay.verify('test/snapshot')

    def test_missing_capture_fields_not_invented(self):
        events = self.store.events()
        staged = next(e for e in events if e['action'] == 'source_import_staged')
        del staged['details']['captures'][0]['request_parameters']
        with patch.object(self.store, 'events', return_value=events), self.assertRaises(KeyError):
            self.replay.verify('test/snapshot')

    def test_incomplete_evidence_missing_terminal_page(self):
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=self.evidence.captures[:-1]))

    def test_empty_capture_set(self):
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=()))

    def test_wrong_request_url_or_parameters(self):
        for change in ({'url': 'https://evil.invalid/'}, {'parameters': (('invented', '1'),)}):
            with self.subTest(change=change):
                captures = list(self.evidence.captures)
                captures[1] = replace(captures[1], request=replace(captures[1].request, **change))
                with self.assertRaises(ValueError):
                    self.replay.reconstruct(replace(self.evidence, captures=tuple(captures)))

    def test_reordered_pages_fail(self):
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=tuple(reversed(self.evidence.captures))))

    def test_stored_feature_content_mismatch(self):
        original = self.sources.features('test/snapshot')
        altered = [replace(original[0], properties_json='{"tampered":true}'), original[1]]
        with patch.object(SourceStore, 'features', return_value=altered), self.assertRaises(ValueError):
            self.replay.verify('test/snapshot')

    def test_empty_query_replay(self):
        self.run_import([response(features=[], numberReturned=0)], snapshot='test/empty')
        self.original = self.dump(self.store)
        result = self.replay.verify('test/empty')
        self.assertEqual(result.features, ())
        self.assertEqual(len(result.pages), 1)

    def test_target_failure_rolls_back(self):
        target = self.target()
        original = self.dump(target)
        write = SourceStore.add_page

        def fail(store, page):
            write(store, page)
            raise RuntimeError('TESTDATA persistence failure')

        with patch.object(SourceStore, 'add_page', fail), self.assertRaises(RuntimeError):
            self.replay.reconstruct_into(self.evidence, target)
        self.assertEqual(self.dump(target), original)

    def test_corrupt_input_leaves_empty_target_empty(self):
        target = self.target()
        before = self.dump(target)
        bad = replace(self.evidence, snapshot=replace(self.evidence.snapshot, snapshot_manifest_hash='0' * 64))
        with self.assertRaises(ValueError):
            self.replay.reconstruct_into(bad, target)
        self.assertEqual(self.dump(target), before)


    def test_malformed_json_with_matching_raw_hash_still_fails(self):
        raw = RawResponse(raw_response_hash(b'broken JSON'), b'broken JSON')
        captures = list(self.evidence.captures)
        captures[1] = replace(captures[1], raw=raw,
                              response=replace(captures[1].response, body=raw.body))
        manifest = json.loads(self.evidence.fetch_manifest_json)
        manifest['received_bytes'] += len(raw.body) - len(self.evidence.captures[1].raw.body)
        manifest['attempts'][1].update(raw_response_hash=raw.raw_response_hash, response_bytes=len(raw.body))
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=tuple(captures),
                                            fetch_manifest_json=json.dumps(manifest)))

    def test_origin_mismatch(self):
        captures = list(self.evidence.captures)
        captures[1] = replace(captures[1], response=replace(
            captures[1].response, origin='UNVALIDATED_PROVIDER_RESPONSE'))
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=tuple(captures)))

    def test_snapshot_crs_mismatch(self):
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, snapshot=replace(
                self.evidence.snapshot, response_crs='EPSG:4326')))

    def test_target_conflict_preserves_existing_target(self):
        target = self.target()
        sources = SourceStore(target)
        with target.db:
            target.db.execute('BEGIN IMMEDIATE')
            sources.add_geometry(replace(self.evidence.analysis, provenance_json='{"conflict":true}'))
        before = self.dump(target)
        with self.assertRaises(ValueError):
            self.replay.reconstruct_into(self.evidence, target)
        self.assertEqual(self.dump(target), before)


    def test_missing_retry_capture_fails_even_when_all_pages_exist(self):
        with self.assertRaises(ValueError):
            self.replay.reconstruct(replace(self.evidence, captures=self.evidence.captures[1:]))


if __name__ == '__main__':
    unittest.main()
