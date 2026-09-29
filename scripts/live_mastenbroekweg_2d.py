"""Milestone 2D bounded live proof; explicit CLI opt-in, isolated local archive."""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bvc_ai.adapters.pdok_bgt import RD_URI, FetchBudgets
from bvc_ai.adapters.pdok_live import PDOKLiveGetTransport, BBOX
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.application.design_workflow import DesignWorkflow
from bvc_ai.application.live_source_validation import mastenbroekweg_analysis
from bvc_ai.application.source_import import SourceImportService, SourceImportError, _A02_SOURCE_IMPORT_CAPABILITY
from bvc_ai.application.source_replay import SourceReplayService
from bvc_ai.application.source_basis import SourceBasisService, REQUIRED_CONTRACTS
from bvc_ai.domain.source_profiles import source_profile
from bvc_ai.infrastructure.source_store import SourceStore
from bvc_ai.infrastructure.store import Store

TID = 'DESIGN-TEST-001'
# Parsing large official polygons shares the request deadline; keep total cap unchanged.
PROOF_BUDGETS = FetchBudgets(request_timeout=60.0)


def capture_report(capture):
    headers = {k.lower(): v for k, v in capture.response.headers}
    return dict(request_url=capture.request.url, http_status=capture.response.status,
                content_type=headers.get('content-type'), content_crs=headers.get('content-crs'),
                received_bytes=len(capture.raw.body), raw_hash=capture.raw.raw_response_hash,
                origin=capture.response.origin,
                retrieval_started_at=capture.retrieval_started_at,
                retrieval_finished_at=capture.retrieval_finished_at)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def offline_proof(store, directory, snapshot_ids):
    """Rebuild archived source records, never workflow revisions or promotion."""
    with ExitStack() as guards:
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guards.enter_context(patch(name, side_effect=AssertionError('OFFLINE: NETWORK BLOCKED')))
        basis = SourceBasisService(store).build(TID)
        require(SourceBasisService(store).verify(basis) == basis, 'Basis verification failed')
        target = Store(directory / 'offline-reconstruction')
        try:
            replay, sources = SourceReplayService(store), SourceStore(target)
            for snapshot_id in snapshot_ids:
                evidence = replay.evidence(snapshot_id)
                verified = replay.verify(snapshot_id)
                rebuilt = replay.reconstruct_into(evidence, target)
                require(rebuilt == verified, 'Reconstruction differs')
                require(sources.snapshot(snapshot_id) == verified.snapshot, 'Snapshot differs')
                require(tuple(sources.pages(snapshot_id)) == verified.pages, 'Pages differ')
                require(tuple(sources.features(snapshot_id)) == verified.features, 'Features differ')
                for geometry in verified.geometries:
                    require(sources.geometry(geometry.geometry_ref) == geometry, 'Geometry differs')
                for raw in verified.raw_responses:
                    require(sources.raw(raw.raw_response_hash) == raw, 'Raw bytes differ')
            require(not target.list(), 'Replay created workflow tasks')
            require(target.db.execute('SELECT count(*) FROM source_revision_bindings').fetchone()[0] == 0,
                    'Replay created trusted bindings')
        finally:
            target.close()
        require(SourceBasisService(store).build(TID) == basis, 'Replay mutated source basis')
        task = store.get(TID)
        require(task['human_approval'] is None, 'Unexpected human approval')
        require(set(task['active_revisions']) == {'A01_START', 'A02'}, 'Unexpected active agent')
        require(all(o['agent_id'] in ('A01', 'A02') for o in task['outputs']), 'Unexpected downstream output')
        return basis


def run_proof(directory, run_id, *, live_opt_in=False):
    if live_opt_in is not True:
        raise ValueError('Explicit live opt-in required')
    directory = Path(directory).resolve()
    require(directory.is_relative_to((ROOT / 'runtime/2d-live').resolve()), 'Proof must stay under runtime/2d-live')
    directory.mkdir(parents=True, exist_ok=False)
    extent, analysis = mastenbroekweg_analysis()
    report = dict(timestamp=datetime.now(timezone.utc).isoformat(), run_id=run_id,
                  address='Mastenbroekweg 2, 6006 PT Weert, Nederland', bbox=BBOX, crs=extent.crs,
                  task_context='TESTDATA scaffolding; source captures are live provider responses',
                  collection_metadata_basis='Declared RD contract from accepted 2D-1; not freshly fetched metadata',
                  collections=[], replay='NOT_RUN', result='BLOCKED',
                  fetch_budgets=vars(PROOF_BUDGETS))
    store = Store(directory / 'archive')
    try:
        workflow = DesignWorkflow(store, DeterministicTestProvider(), ROOT)
        workflow.create()
        workflow.step(TID, 'A01_START', '2d/start')
        with store.db:
            store.db.execute('BEGIN IMMEDIATE')
            SourceStore(store).add_geometry(analysis)
        for key in sorted(REQUIRED_CONTRACTS):
            profile = source_profile(key)
            report['current_collection'] = key
            importer = SourceImportService(store, PDOKLiveGetTransport(source_contract=key),
                collection_metadata_json=json.dumps({'id': profile.collection, 'crs': [RD_URI]}),
                capability=_A02_SOURCE_IMPORT_CAPABILITY, source_contract=key, live_mastenbroekweg=True)
            binding = importer.import_source(TID, '2d/' + run_id + '/' + key, extent, budgets=PROOF_BUDGETS)
            evidence = SourceReplayService(store).evidence(binding.snapshot_id)
            snapshot = evidence.snapshot
            report['collections'].append(dict(source_contract=key, snapshot_id=binding.snapshot_id,
                import_revision_id=binding.revision_id, feature_count=snapshot.feature_count,
                page_count=snapshot.page_count, snapshot_manifest_hash=snapshot.snapshot_manifest_hash,
                captures=[capture_report(c) for c in evidence.captures]))
        basis = offline_proof(store, directory, [c['snapshot_id'] for c in report['collections']])
        (directory / 'source-basis.json').write_text(json.dumps(basis, indent=2), encoding='utf-8')
        report.update(result='PASS', replay='PASS', replay_network='socket/connect/DNS blocked',
            basis_hash=basis['basis_hash'], revision_id=basis['revision_id'], complete=basis['complete'],
            records=len(basis['records']), relations=dict(Counter(r['status'] for r in basis['relations'])),
            uncertainties=dict(Counter(u['reason'] for u in basis['uncertainties'])),
            point_in_time_consistency=basis['point_in_time_consistency'],
            reconstruction='Exact raw/geometry/features/pages/snapshots; no tasks or trusted bindings',
            human_approval=None, active_agents=['A01', 'A02'])
        report.pop('current_collection')
    except Exception as exc:
        report.update(reason=str(exc), error_type=type(exc).__name__)
        if isinstance(exc, SourceImportError):
            report.update(failure_phase=exc.phase, reason=str(exc.__cause__))
            if exc.fetch_result:
                report['fetch_failure'] = exc.fetch_result.failure_reason
                report['failed_captures'] = [capture_report(c) for c in exc.fetch_result.captures]
    finally:
        store.close()
        (directory / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-mastenbroekweg', action='store_true', required=True)
    parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = ROOT / 'runtime/2d-live' / run_id
    report = run_proof(directory, run_id, live_opt_in=True)
    print(json.dumps(report, indent=2))
    print('Local evidence directory: ' + str(directory))
    return int(report['result'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
