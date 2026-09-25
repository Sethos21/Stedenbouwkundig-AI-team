"""Phase 4: synthetic PDOK pand proof with real isolated SQLite, no network."""
import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from test_pdok_bgt import METADATA, EXTENT
from test_pdok_bgt_fetch import response, SequenceTransport, Timer
from test_source_validation import geometry, SQUARE
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.application.design_workflow import DesignWorkflow
from bvc_ai.application.source_import import (
    SourceImportService, SourceImportError, _A02_SOURCE_IMPORT_CAPABILITY,
)
from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter
from bvc_ai.adapters.source_transport import ResponseOrigin
from bvc_ai.domain.sources import GeometryRole, ImportStatus
from bvc_ai.domain.design import current_output
from bvc_ai.domain.source_validation import validate_completeness
from bvc_ai.infrastructure.source_store import SourceStore
from bvc_ai.infrastructure.source_schema import SOURCE_TABLES
from bvc_ai.infrastructure.store import Store

ROOT = Path(__file__).resolve().parents[1]
TID = 'DESIGN-TEST-001'


class SourceImportTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(target, side_effect=AssertionError('NETWORKLESS'))
            guard.start()
            self.addCleanup(guard.stop)
        directory = ROOT / '.tools/test-runs'
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.addCleanup(self.store.close)
        self.sources = SourceStore(self.store)
        self.workflow = DesignWorkflow(self.store, DeterministicTestProvider(), ROOT)
        self.workflow.create()
        self.workflow.step(TID, 'A01_START', 'test/start')
        self.analysis = replace(geometry('Polygon', [SQUARE], ref=EXTENT.analysis_geometry_ref),
                                role=GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY)
        with self.store.db:
            self.store.db.execute('BEGIN IMMEDIATE')
            self.sources.add_geometry(self.analysis)
        self.run_number = 0

    def service(self, items):
        self.run_number += 1
        timer = Timer()
        self.transport = SequenceTransport(items, timer)
        self.importer = SourceImportService(
            self.store, self.transport, collection_metadata_json=json.dumps(METADATA),
            capability=_A02_SOURCE_IMPORT_CAPABILITY,
            clock=lambda: '2026-09-25T00:00:%02dZ' % self.run_number,
            monotonic=timer, sleep=timer.sleep)
        return self.importer

    def run_import(self, items=None, snapshot='test/snapshot', **kwargs):
        return self.service([response()] if items is None else items).import_source(
            TID, snapshot, EXTENT, **kwargs)

    def trusted_state(self):
        return (self.store.get(TID), {table: self.store.db.execute(
            'SELECT * FROM ' + table + ' ORDER BY 1').fetchall()
            for table in SOURCE_TABLES if table != 'raw_responses'})

    def assert_failure_unchanged(self, call, before=None):
        before = before or self.trusted_state()
        with self.assertRaises(SourceImportError) as caught:
            call()
        self.assertEqual(self.trusted_state(), before)
        self.assertEqual(self.store.events(TID)[-1]['action'], 'source_import_failed')
        self.assertEqual(self.store.db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertFalse(self.store.db.in_transaction)
        return caught.exception

    def test_successful_minimal_import_and_binding(self):
        result = self.run_import()
        self.assertEqual(result.revision_id, 'A02/v1')
        self.assertEqual(result.snapshot_id, 'test/snapshot')
        snapshot = self.sources.snapshot(result.snapshot_id)
        self.assertEqual(snapshot.status, ImportStatus.COMPLETE)
        self.assertEqual(snapshot.point_in_time_consistency, 'NOT_GUARANTEED')
        self.assertEqual(json.loads(snapshot.provenance_json)['source_status'], 'TESTDATA')
        self.assertEqual(len(self.sources.pages(result.snapshot_id)), 1)
        features = self.sources.features(result.snapshot_id)
        self.assertEqual(len(features), 1)
        task = self.store.get(TID)
        output = current_output(task, 'A02')
        self.assertEqual(output['output']['source_snapshot_id'], result.snapshot_id)
        self.assertEqual(output['output']['snapshot_manifest_hash'], snapshot.snapshot_manifest_hash)
        obj = task['objects'][-1]
        self.assertEqual(obj['geometry_ref'], features[0].geometry_ref)
        self.assertEqual(obj['geometry_status'], 'EXISTING_VALIDATED')
        self.assertEqual(obj['source_status'], 'TESTDATA')
        self.assertEqual(task['human_approval'], None)
        self.assertEqual(task['status'], 'READY')
        self.assertEqual(self.store.db.execute('SELECT * FROM source_revision_bindings').fetchall(),
                         [(TID, result.revision_id, result.snapshot_id)])
        self.assertEqual(self.store.events(TID)[-1]['action'], 'source_import_completed')
        self.assertEqual(self.store.events(TID)[-1]['details']['point_in_time_consistency'], 'NOT_GUARANTEED')

    def test_successful_multipage_with_retry_evidence(self):
        error = replace(response(status=503), body=b'TESTDATA transient error')
        self.run_import([error, response(next_link='?cursor=two'), response('two')])
        self.assertEqual(len(self.sources.pages('test/snapshot')), 2)
        self.assertEqual(len(self.sources.features('test/snapshot')), 2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM raw_responses').fetchone()[0], 3)
        staged = next(e for e in self.store.events(TID) if e['action'] == 'source_import_staged')
        self.assertEqual(len(staged['details']['captures']), 3)
        self.assertEqual(staged['details']['captures'][0]['response_status'], 503)
        self.assertEqual(staged['details']['target'], 'STAGING')

    def test_empty_complete_query_binds_without_inventing_geometry(self):
        result = self.run_import([response(features=[], numberReturned=0)])
        self.assertEqual(self.sources.features(result.snapshot_id), [])
        self.assertEqual(self.store.get(TID)['objects'], [])
        self.assertEqual(result.revision_id, 'A02/v1')

    def test_identical_reimport_reuses_immutable_records_and_revision(self):
        first = self.run_import()
        before = self.trusted_state()
        snapshot = self.sources.snapshot(first.snapshot_id)
        second = self.run_import()
        self.assertEqual(first, second)
        self.assertEqual(self.trusted_state(), before)
        self.assertEqual(self.sources.snapshot(first.snapshot_id).retrieval_started_at,
                         snapshot.retrieval_started_at)
        self.assertEqual(self.store.events(TID)[-1]['action'], 'source_import_noop')

    def test_identical_manifest_under_new_id_reuses_existing_snapshot(self):
        first = self.run_import()
        before = self.trusted_state()
        second = self.run_import(snapshot='test/new-requested-id')
        self.assertEqual(second, first)
        self.assertEqual(self.trusted_state(), before)

    def test_conflicting_reimport_fails_without_overwriting_history(self):
        self.run_import()
        self.assert_failure_unchanged(lambda: self.run_import([response('changed')]))

    def test_failure_before_promotion_keeps_only_raw_evidence(self):
        with patch.object(SourceImportService, '_validate_provenance', side_effect=ValueError('TESTDATA fail')):
            error = self.assert_failure_unchanged(self.run_import)
        self.assertEqual(error.phase, 'validation')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM raw_responses').fetchone()[0], 1)
        self.assertEqual(len(error.fetch_result.captures), 1)
        self.assertFalse(any(e['action'] == 'source_import_completed' for e in self.store.events(TID)))

    def test_failure_during_each_persistence_stage_rolls_back(self):
        for method in ('add_geometry', 'add_snapshot', 'add_page', 'add_feature'):
            with self.subTest(method=method):
                original = getattr(SourceStore, method)

                def write_then_fail(store, record):
                    original(store, record)
                    raise RuntimeError('TESTDATA injected persistence failure')

                with patch.object(SourceStore, method, write_then_fail):
                    self.assert_failure_unchanged(self.run_import)

    def test_failure_after_binding_rolls_back_promotion_revision_and_binding(self):
        original = SourceStore._bind_revision

        def bind_then_fail(store, record):
            original(store, record)
            raise RuntimeError('TESTDATA after binding')

        with patch.object(SourceStore, '_bind_revision', bind_then_fail):
            self.assert_failure_unchanged(self.run_import)
        self.assertFalse(any(e['action'] in ('source_import_completed', 'design_object_registered')
                             for e in self.store.events(TID)))

    def test_success_audit_failure_rolls_back_every_trusted_write(self):
        original = self.store.event

        def audit_then_fail(task_id, actor, action, **details):
            original(task_id, actor, action, **details)
            if action == 'source_import_completed':
                raise RuntimeError('TESTDATA after success audit')

        with patch.object(self.store, 'event', audit_then_fail):
            error = self.assert_failure_unchanged(self.run_import)
        self.assertEqual(error.phase, 'audit')
        self.assertFalse(any(e['action'] == 'source_import_completed' for e in self.store.events(TID)))

    def test_incomplete_fetch_never_promotes_and_retains_partial_evidence(self):
        first = response(next_link='?cursor=two')
        error = self.assert_failure_unchanged(lambda: self.run_import([first, TimeoutError()]))
        self.assertEqual(error.fetch_result.status, ImportStatus.INCOMPLETE)
        self.assertEqual(error.fetch_result.features, ())
        self.assertEqual(error.fetch_result.geometries, ())
        self.assertEqual(self.store.db.execute('SELECT body FROM raw_responses').fetchall(), [(first.body,)])
        staged = next(e for e in self.store.events(TID) if e['action'] == 'source_import_staged')
        self.assertEqual(len(staged['details']['captures']), 1)

    def test_false_pagination_exhaustion_and_failure_marker_are_rejected(self):
        original = PDOKBGTAdapter.fetch
        for changes in ({'pagination_exhausted': False}, {'failure_reason': 'TESTDATA failure'},
                        {'status': ImportStatus.COMPLETE}):
            with self.subTest(changes=changes):
                def alter(adapter, *args, **kwargs):
                    return replace(original(adapter, *args, **kwargs), **changes)
                with patch.object(PDOKBGTAdapter, 'fetch', alter):
                    self.assert_failure_unchanged(self.run_import)

    def test_invalid_completeness_rejected(self):
        original = PDOKBGTAdapter.fetch

        def alter(adapter, *args, **kwargs):
            result = original(adapter, *args, **kwargs)
            return replace(result, pages=(replace(result.pages[0], next_url='?unresolved'),))

        with patch.object(PDOKBGTAdapter, 'fetch', alter):
            self.assert_failure_unchanged(self.run_import)

    def test_negative_completeness_result_cannot_promote(self):
        def negative(*args, **kwargs):
            return replace(validate_completeness(*args, **kwargs), query_scope_complete=False)
        with patch('bvc_ai.application.source_import.validate_completeness', negative):
            self.assert_failure_unchanged(self.run_import)

    def test_invalid_response_crs_and_geometry_fail_closed(self):
        for item in (response(coordRefSys='EPSG:4326'),
                     response(features=[{'type': 'Feature', 'id': 'bad', 'properties': {},
                                         'place': {'type': 'Polygon', 'coordinates': []}}])):
            with self.subTest(body=item.body):
                self.assert_failure_unchanged(lambda: self.run_import([item]))

    def test_invalid_mapped_geometry_revalidated_before_persistence(self):
        original = PDOKBGTAdapter.fetch

        def alter(adapter, *args, **kwargs):
            result = original(adapter, *args, **kwargs)
            bad = replace(result.geometries[0], geometry_structural_hash='0' * 64)
            return replace(result, geometries=(bad,))

        with patch.object(PDOKBGTAdapter, 'fetch', alter):
            self.assert_failure_unchanged(self.run_import)

    def test_invalid_feature_and_geometry_provenance_rejected(self):
        original = PDOKBGTAdapter.fetch
        for field in ('features', 'geometries'):
            with self.subTest(field=field):
                def alter(adapter, *args, **kwargs):
                    result = original(adapter, *args, **kwargs)
                    record = replace(getattr(result, field)[0], provenance_json='{"unproven":true}')
                    return replace(result, **{field: (record,)})
                with patch.object(PDOKBGTAdapter, 'fetch', alter):
                    self.assert_failure_unchanged(self.run_import)

    def test_non_testdata_origin_is_not_silently_reclassified(self):
        item = replace(response(), origin=ResponseOrigin.PROVIDER_RESPONSE)
        self.assert_failure_unchanged(lambda: self.run_import([item]))

    def test_only_trusted_capability_can_construct_service(self):
        for capability in (None, object(), 'A02', 'trusted', {'actor': 'A02'}):
            with self.subTest(capability=repr(capability)), self.assertRaises(PermissionError):
                SourceImportService(self.store, None, collection_metadata_json=json.dumps(METADATA),
                                    capability=capability)
        self.assertFalse(hasattr(self.workflow.agent('A02'), 'import_source'))
        self.assertFalse(hasattr(PDOKBGTAdapter, 'promote'))
        self.assertFalse(hasattr(PDOKBGTAdapter, 'store'))

    def test_provider_cannot_promote_imported_geometry(self):
        result = self.run_import()
        ref = self.sources.features(result.snapshot_id)[0].geometry_ref
        provider = self.workflow.provider
        original = provider.design_step

        def proposal(step, context, inputs):
            value = original(step, context, inputs)
            value['objects'][0].update(geometry_ref=ref, source_basis=[ref])
            return value

        before = self.trusted_state()
        with patch.object(provider, 'design_step', proposal), self.assertRaises(ValueError):
            self.workflow.step(TID, 'A02', 'provider/imported-ref')
        self.assertEqual(self.trusted_state(), before)

    def test_new_snapshot_reuses_stale_propagation_and_preserves_history(self):
        first = self.run_import()
        with self.store.db:
            task = self.store.get(TID)
            task['outputs'].append(dict(agent_id='A07', step='A07', revision_id='A07/v1',
                                        input_revisions={'A02': first.revision_id}, output={}))
            task['active_revisions']['A07'] = 'A07/v1'
            task['reviews'].append(dict(review_id='A07/v1'))
            task['findings'].append(dict(finding_id='TESTDATA/finding', status='RESOLVED',
                                         created_by='A07', severity='MINOR'))
            task['finding_history'].append(dict(finding_id='TESTDATA/finding', target='RESOLVED',
                                                review_id='A07/v1'))
            self.store._save(task)
        old = copy.deepcopy(self.store.get(TID)['outputs'])
        second = self.run_import([response('changed')], snapshot='test/second')
        task = self.store.get(TID)
        self.assertEqual(second.revision_id, 'A02/v2')
        self.assertEqual(task['outputs'][:len(old)], old)
        self.assertIn(first.revision_id, task['stale_revisions'])
        self.assertIn('A07/v1', task['stale_revisions'])
        self.assertIn('A07/v1', task['stale_reviews'])
        self.assertNotIn('A07', task['active_revisions'])
        self.assertEqual(task['findings'][0]['status'], 'OPEN')
        self.assertEqual(task['finding_history'][-1]['stale_review'], 'A07/v1')
        self.assertTrue(any(e['action'] == 'finding_reopened' for e in self.store.events(TID)))
        self.assertEqual(len(self.store.db.execute('SELECT * FROM source_revision_bindings').fetchall()), 2)
        self.assertTrue(any(e['action'] == 'dependencies_invalidated' for e in self.store.events(TID)))
        self.assertEqual(self.sources.features(first.snapshot_id)[0].source_id, 'one')

    def test_failed_replacement_rolls_back_stale_and_previous_active_revision(self):
        self.run_import()
        original = self.store.event

        def fail(task_id, actor, action, **details):
            original(task_id, actor, action, **details)
            if action == 'source_import_completed':
                raise RuntimeError('TESTDATA injected audit failure')

        with patch.object(self.store, 'event', fail):
            self.assert_failure_unchanged(lambda: self.run_import([response('new')], snapshot='test/second'))

    def test_historical_binding_cannot_be_reactivated_by_reimport(self):
        self.run_import()
        self.run_import([response('new')], snapshot='test/second')
        self.assert_failure_unchanged(self.run_import)

    def test_concurrent_task_change_during_fetch_blocks_publication(self):
        service = self.service([response()])
        original = self.transport.get
        expected = []

        def change(request):
            with self.store.db:
                task = self.store.get(TID)
                task['updated_at'] = 'TESTDATA concurrent update'
                self.store._save(task)
            expected.append(self.trusted_state())
            return original(request)

        with patch.object(self.transport, 'get', change), self.assertRaises(SourceImportError):
            service.import_source(TID, 'test/snapshot', EXTENT)
        self.assertEqual(self.trusted_state(), expected[0])
        self.assertEqual(self.store.events(TID)[-1]['action'], 'source_import_failed')

    def test_closed_task_blocks_before_fetch(self):
        for status in ('APPROVED', 'REJECTED', 'REQUIRES_HUMAN_DECISION'):
            with self.subTest(status=status):
                # Isolated gate fixture only; no HumanApprovalService invocation.
                with self.store.db:
                    task = self.store.get(TID)
                    task['status'] = status
                    self.store._save(task)
                self.assert_failure_unchanged(self.run_import)
                self.assertEqual(self.transport.requests, [])

    def test_caller_transaction_is_not_committed_or_rolled_back(self):
        service = self.service([response()])
        self.store.db.execute('BEGIN IMMEDIATE')
        with self.assertRaises(RuntimeError):
            service.import_source(TID, 'test/snapshot', EXTENT)
        self.assertTrue(self.store.db.in_transaction)
        self.store.db.rollback()
        self.assertEqual(self.transport.requests, [])

    def test_evidence_failure_never_starts_publication(self):
        with patch.object(SourceStore, 'add_raw', side_effect=RuntimeError('TESTDATA disk failure')):
            error = self.assert_failure_unchanged(self.run_import)
        self.assertEqual(error.phase, 'evidence')
        self.assertEqual(len(error.fetch_result.captures), 1)
        self.assertEqual(self.store.db.execute('SELECT * FROM raw_responses').fetchall(), [])

    def test_failure_audit_unavailable_still_rolls_back_trusted_state(self):
        before = self.trusted_state()
        original = self.store.event

        def fail(task_id, actor, action, **details):
            if action in ('source_import_completed', 'source_import_failed'):
                raise RuntimeError('TESTDATA audit unavailable')
            original(task_id, actor, action, **details)

        with patch.object(self.store, 'event', fail), self.assertRaises(SourceImportError):
            self.run_import()
        self.assertEqual(self.trusted_state(), before)
        self.assertFalse(self.store.db.in_transaction)


    def test_identical_reimport_with_new_http_date_remains_noop(self):
        item = response()
        first = self.run_import([replace(item, headers=item.headers + (('Date', 'first retrieval'),))])
        before = self.trusted_state()
        second = self.run_import([replace(item, headers=item.headers + (('Date', 'later retrieval'),))])
        self.assertEqual(first, second)
        self.assertEqual(self.trusted_state(), before)

    def test_immutable_geometry_conflict_blocks_promotion(self):
        service = self.service([response()])
        fetched = service._adapter.fetch('test/snapshot', EXTENT)
        conflict = replace(fetched.geometries[0], provenance_json='{"source_status":"TESTDATA","conflict":true}')
        with self.store.db:
            self.store.db.execute('BEGIN IMMEDIATE')
            self.sources.add_geometry(conflict)
        error = self.assert_failure_unchanged(self.run_import)
        self.assertEqual(error.phase, 'persistence')

    def test_reused_archive_is_revalidated_not_trusted_by_complete_label(self):
        self.run_import()
        original = SourceStore.features

        def incomplete(store, snapshot_id):
            return []

        with patch.object(SourceStore, 'features', incomplete):
            self.assert_failure_unchanged(self.run_import)
        self.assertEqual(len(original(self.sources, 'test/snapshot')), 1)

    def test_reused_archive_invalid_geometry_provenance_is_rejected(self):
        self.run_import()
        original = SourceStore.geometry

        def invalid(store, ref):
            record = original(store, ref)
            if record.role == GeometryRole.SOURCE_GEOMETRY:
                return replace(record, provenance_json='{"unproven":true}')
            return record

        with patch.object(SourceStore, 'geometry', invalid):
            self.assert_failure_unchanged(self.run_import)

    def test_binding_without_publication_evidence_is_not_a_noop(self):
        self.run_import()
        with self.store.db:
            task = self.store.get(TID)
            del task['outputs'][-1]['output']['source_snapshot_id']
            self.store._save(task)
        self.assert_failure_unchanged(self.run_import)

    def test_page_capture_provenance_mismatch_fails(self):
        original = PDOKBGTAdapter.fetch
        for changes in ({'request_parameters_json': '{"invented":true}'},
                        {'response_headers_json': '{"content-crs":"EPSG:28992"}'}):
            with self.subTest(changes=changes):
                def alter(adapter, *args, **kwargs):
                    result = original(adapter, *args, **kwargs)
                    return replace(result, pages=(replace(result.pages[0], **changes),))
                with patch.object(PDOKBGTAdapter, 'fetch', alter):
                    self.assert_failure_unchanged(self.run_import)

    def test_insufficient_crs_evidence_fails(self):
        original = PDOKBGTAdapter.fetch

        def alter(adapter, *args, **kwargs):
            result = original(adapter, *args, **kwargs)
            record = result.geometries[0]
            crs = replace(record.crs_metadata, evidence='{"source_status":"TESTDATA"}')
            return replace(result, geometries=(replace(record, crs_metadata=crs),))

        with patch.object(PDOKBGTAdapter, 'fetch', alter):
            self.assert_failure_unchanged(self.run_import)

    def test_success_audit_transition_chain_is_explicit(self):
        self.run_import()
        events = [e for e in self.store.events(TID) if e['action'].startswith('source_import_')]
        self.assertEqual([e['action'] for e in events],
                         ['source_import_staged', 'source_import_validated', 'source_import_completed'])
        self.assertEqual([e['details']['target'] for e in events], ['STAGING', 'VALIDATING', 'COMPLETE'])
        self.assertTrue(all(e['actor'] == 'A02' for e in events))

    def test_failure_keeps_prior_immutable_history_byte_for_byte(self):
        self.run_import()
        before = self.trusted_state()
        original = SourceStore.add_page

        def fail(store, page):
            original(store, page)
            raise RuntimeError('TESTDATA persistence interruption')

        with patch.object(SourceStore, 'add_page', fail):
            self.assert_failure_unchanged(
                lambda: self.run_import([response('next')], snapshot='test/next'), before)

    def test_archive_and_binding_survive_reopen(self):
        result = self.run_import()
        other = Store(self.temp.name)
        try:
            self.assertEqual(other.get(TID), self.store.get(TID))
            self.assertEqual(SourceStore(other).snapshot(result.snapshot_id),
                             self.sources.snapshot(result.snapshot_id))
            self.assertEqual(other.db.execute('SELECT * FROM source_revision_bindings').fetchall(),
                             [(TID, result.revision_id, result.snapshot_id)])
            self.assertEqual(other.events(TID)[-1]['action'], 'source_import_completed')
        finally:
            other.close()


if __name__ == '__main__':
    unittest.main()
