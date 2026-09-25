"""Explicit Phase 6 live proof. Never executed by test discovery."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bvc_ai.adapters.pdok_bgt import RD_URI
from bvc_ai.adapters.pdok_live import PDOKLiveGetTransport, BBOX
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.application.design_workflow import DesignWorkflow
from bvc_ai.application.live_source_validation import mastenbroekweg_analysis, PURPOSE
from bvc_ai.application.source_import import SourceImportService, SourceImportError, _A02_SOURCE_IMPORT_CAPABILITY
from bvc_ai.application.source_replay import SourceReplayService
from bvc_ai.infrastructure.source_store import SourceStore
from bvc_ai.infrastructure.store import Store


def capture_report(capture):
    document = json.loads(capture.raw.body)
    headers = {k.lower(): v for k, v in capture.response.headers}
    return dict(request_url=capture.request.url, http_status=capture.response.status,
                content_type=headers.get('content-type'), content_crs=headers.get('content-crs'),
                coordRefSys=document.get('coordRefSys'), type=document.get('type'),
                feature_count=len(document.get('features', [])), numberReturned=document.get('numberReturned'),
                next_link_present=any(x.get('rel') == 'next' for x in document.get('links', [])),
                received_bytes=len(capture.raw.body), raw_hash=capture.raw.raw_response_hash,
                origin=capture.response.origin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live-mastenbroekweg', action='store_true', required=True)
    parser.parse_args()
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime('%Y%m%dT%H%M%S%fZ')
    directory = ROOT / 'runtime/phase6-live' / run_id
    extent, analysis = mastenbroekweg_analysis()
    report = dict(timestamp=stamp.isoformat(), purpose=PURPOSE, bbox=BBOX, crs=extent.crs,
                  geometry_role=analysis.role, address='Mastenbroekweg 2, 6006 PT Weert, Nederland',
                  bag_centroid_rd=[176742.301,360855.561],
                  task_context='TESTDATA workflow scaffolding; A02 evidence is live provider data',
                  collection_metadata_basis='Caller-declared RD contract expectation; not live-fetched metadata',
                  replay='NOT_RUN')
    store = Store(directory / 'archive')
    try:
        # Only fixture scaffolding and A01 startup; no downstream agent/approval.
        workflow = DesignWorkflow(store, DeterministicTestProvider(), ROOT)
        workflow.create()
        workflow.step('DESIGN-TEST-001', 'A01_START', 'phase6/start')
        sources = SourceStore(store)
        with store.db:
            store.db.execute('BEGIN IMMEDIATE')
            sources.add_geometry(analysis)
        importer = SourceImportService(store, PDOKLiveGetTransport(),
            collection_metadata_json=json.dumps({'id':'pand', 'crs':[RD_URI]}),
            capability=_A02_SOURCE_IMPORT_CAPABILITY, live_mastenbroekweg=True)
        binding = importer.import_source('DESIGN-TEST-001', 'phase6/mastenbroekweg/' + run_id, extent)
        snapshot = sources.snapshot(binding.snapshot_id)
        replay = SourceReplayService(store)
        with ExitStack() as guards:
            for target in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
                guards.enter_context(patch(target, side_effect=AssertionError('OFFLINE REPLAY: NETWORK BLOCKED')))
            evidence = replay.evidence(binding.snapshot_id)
            verified = replay.verify(binding.snapshot_id)
            target = Store(directory / 'offline-reconstruction')
            try:
                rebuilt = replay.reconstruct_into(evidence, target)
                target_sources = SourceStore(target)
                assert rebuilt == verified
                assert target_sources.snapshot(binding.snapshot_id) == snapshot
                assert tuple(target_sources.pages(binding.snapshot_id)) == verified.pages
                assert tuple(target_sources.features(binding.snapshot_id)) == verified.features
                for geometry in verified.geometries:
                    assert target_sources.geometry(geometry.geometry_ref) == geometry
                for raw in verified.raw_responses:
                    assert target_sources.raw(raw.raw_response_hash) == raw
                assert not target.list()
                assert target.db.execute('SELECT count(*) FROM source_revision_bindings').fetchone()[0] == 0
            finally:
                target.close()
        task = store.get('DESIGN-TEST-001')
        objects = [o for o in task['objects'] if o['revision_id'] == binding.revision_id]
        assert len(objects) == snapshot.feature_count
        assert all(o['geometry_status'] == 'EXISTING_VALIDATED' and
                   o['source_status'] == 'UNVALIDATED_PROVIDER_RESPONSE' for o in objects)
        assert task['human_approval'] is None
        assert task['active_revisions'] == {'A01_START':'A01_START/v1', 'A02':binding.revision_id}
        report.update(result='PASS', page_count=snapshot.page_count, feature_count=snapshot.feature_count,
                      snapshot_id=binding.snapshot_id, revision_id=binding.revision_id,
                      snapshot_manifest_hash=snapshot.snapshot_manifest_hash,
                      captures=[capture_report(c) for c in evidence.captures],
                      replay='PASS', replay_network='socket/socket.create_connection/DNS blocked',
                      trusted_promotion=store.events('DESIGN-TEST-001')[-1],
                      raw_geometry_provenance_manifest_equal=True,
                      point_in_time_consistency=snapshot.point_in_time_consistency)
    except SourceImportError as exc:
        report.update(result='BLOCKED', failure_phase=exc.phase,
                      reason=str(exc.__cause__),
                      captures=[capture_report(c) for c in exc.fetch_result.captures] if exc.fetch_result else [])
        if exc.fetch_result:
            report['fetch_failure'] = exc.fetch_result.failure_reason
    finally:
        store.close()
    (directory / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('Local evidence directory: ' + str(directory))
    return int(report.get('result') != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
