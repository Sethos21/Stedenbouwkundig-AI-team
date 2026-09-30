"""Trusted PDOK pand MINIMAL_PROOF import orchestration with explicit live opt-in.

Uses the existing archive, transaction, A02 revision and stale mechanisms.
The capability is never passed to providers, sessions or the read-only adapter.
"""
import json
import time
from dataclasses import replace

from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter, ITEMS_URL, PARSER_VERSION
from bvc_ai.adapters.source_transport import ResponseOrigin
from bvc_ai.application.design_workflow import DesignWorkflow
from bvc_ai.application.source_basis import validated_members
from bvc_ai.application.live_source_validation import (
    LIVE_PROFILE, validate_live_analysis, validate_live_fetch,
)
from bvc_ai.domain.models import now
from bvc_ai.domain.design import current_output
from bvc_ai.domain.policies import K00Policy
from bvc_ai.domain.sources import (
    SourceSnapshot, RevisionBinding, ImportStatus, PointInTimeConsistency, required,
)
from bvc_ai.domain.source_hashing import (
    CANONICALIZATION_VERSION, snapshot_manifest_hash, strict_json, normalize_crs_identifier,
)
from bvc_ai.domain.geometry_validation import VALIDATOR_VERSION, validate_geometry_record
from bvc_ai.domain.source_validation import validate_completeness
from bvc_ai.infrastructure.source_store import SourceStore


_A02_SOURCE_IMPORT_CAPABILITY = object()


class SourceImportError(ValueError):
    """Failure with in-memory capture evidence, even if evidence persistence fails."""
    def __init__(self, phase, fetch_result=None):
        super().__init__('Source import failed during ' + phase)
        self.phase = phase
        self.fetch_result = fetch_result


class SourceImportService:
    def __init__(self, store, transport, *, collection_metadata_json, capability=None,
                 clock=now, monotonic=time.monotonic, sleep=time.sleep, live_mastenbroekweg=False,
                 source_contract=None, live_opt_in=False):
        if capability is not _A02_SOURCE_IMPORT_CAPABILITY:
            raise PermissionError('Trusted A02 source-import capability required')
        if type(live_mastenbroekweg) is not bool or type(live_opt_in) is not bool:
            raise ValueError('Explicit boolean live opt-in required')
        self._live = live_mastenbroekweg or live_opt_in
        self._origin = ResponseOrigin.PROVIDER_RESPONSE if self._live else ResponseOrigin.TESTDATA
        self._store = store
        self._sources = SourceStore(store)
        self._adapter = PDOKBGTAdapter(transport, collection_metadata_json=collection_metadata_json,
                                      clock=clock, source_contract=source_contract)
        self._profile = self._adapter.profile
        # Only internal gate/apply helpers are used; no provider is constructed or called.
        self._workflow = DesignWorkflow(store, None, None)
        self._monotonic, self._sleep = monotonic, sleep

    def import_source(self, task_id, snapshot_id, extent, *, limit=1000, budgets=None):
        # Never commit or roll back a transaction owned by a caller.
        if self._store.db.in_transaction:
            raise RuntimeError('Source import requires its own transaction')
        phase, fetched = 'gate', None
        try:
            required(task_id, snapshot_id)
            before = self._store.get(task_id)
            self._workflow._gate(before, 'A02', 'A02', None)
            if before.get('source_status') != 'TESTDATA':
                raise ValueError('Phase 4 MINIMAL_PROOF requires explicit TESTDATA context')
            analysis = self._sources.geometry(extent.analysis_geometry_ref)
            validate_geometry_record(analysis, source_crs=extent.crs)
            if self._live:
                validate_live_analysis(analysis, extent)
            elif strict_json(analysis.provenance_json).get('source_status') != 'TESTDATA':
                raise ValueError('Explicit TESTDATA analysis provenance required')
            phase = 'fetch'
            fetched = self._adapter.fetch(snapshot_id, extent, limit=limit, budgets=budgets,
                                          monotonic=self._monotonic, sleep=self._sleep)
            phase = 'evidence'
            self._stage(task_id, snapshot_id, fetched)
            phase = 'validation'
            if (fetched.status != ImportStatus.VALIDATING
                    or fetched.pagination_exhausted is not True or fetched.failure_reason is not None):
                raise ValueError('Incomplete fetch cannot be promoted')
            self._validate_provenance(fetched)
            if self._live:
                validate_live_fetch(fetched, self._adapter, extent, analysis, limit)
            geometries = (analysis,) + fetched.geometries
            page_hashes = {page.raw_response_hash for page in fetched.pages}
            raw = {c.raw.raw_response_hash: c.raw for c in fetched.captures}
            page_raw = tuple(raw[h] for h in page_hashes)
            request = self._adapter.build_request(extent, limit=limit)
            snapshot = SourceSnapshot(
                snapshot_id, 'PDOK', self._profile.dataset, self._profile.collection, self._profile.items_url, extent,
                'EPSG:28992', 'EPSG:28992', json.dumps(dict(request.parameters)),
                'CURRENT_QUERY_NO_POINT_IN_TIME_GUARANTEE',
                fetched.captures[0].retrieval_started_at, fetched.captures[-1].retrieval_finished_at,
                ImportStatus.VALIDATING, PointInTimeConsistency.NOT_GUARANTEED,
                'Pagination exhaustion does not establish point-in-time consistency',
                len(fetched.pages), len(fetched.features), '0' * 64,
                CANONICALIZATION_VERSION, self._profile.parser_version, VALIDATOR_VERSION,
                json.dumps({'source_status': self._origin.value,
                            'profile': (('PDOK_2D_LIVE' if self._live else 'PDOK_2D_TESTDATA') if self._profile.key
                                        else (LIVE_PROFILE if self._live else 'PDOK_PAND_MINIMAL_PROOF')),
                            **({'source_contract': self._profile.key} if self._profile.key else {}),
                            'collection_metadata': json.loads(self._adapter.collection_metadata_json)}))
            snapshot = replace(snapshot, snapshot_manifest_hash=snapshot_manifest_hash(
                snapshot, fetched.pages, fetched.features, geometries))
            phase = 'transaction'
            with self._store.db:
                self._store.db.execute('BEGIN IMMEDIATE')
                task = self._store.get(task_id)
                if task != before:
                    raise ValueError('Task changed during fetch; retry against current revisions')
                self._workflow._gate(task, 'A02', 'A02', None)
                phase = 'completeness'
                proof = validate_completeness(snapshot, fetched.pages, fetched.features,
                                              geometries, page_raw)
                if proof.query_scope_complete is not True:
                    raise ValueError('Query completeness not established')
                self._store.event(task_id, 'A02', 'source_import_validated',
                                  snapshot_id=snapshot_id, previous=ImportStatus.STAGING,
                                  target=ImportStatus.VALIDATING, query_scope_complete=True)
                phase = 'persistence'
                archived = self._existing(snapshot)
                for geometry in geometries:
                    self._sources.add_geometry(geometry)
                if archived is None:
                    archived = replace(snapshot, status=ImportStatus.COMPLETE)
                    self._sources.add_snapshot(archived)
                    for page in fetched.pages:
                        self._sources.add_page(page)
                    for feature in fetched.features:
                        self._sources.add_feature(feature)
                # Read back and validate the exact immutable archive before promotion,
                # including reused manifests. COMPLETE alone is never trusted.
                self._validate_archive(archived, fetched)
                binding = self._store.db.execute(
                    'SELECT revision_id FROM source_revision_bindings WHERE task_id=? AND snapshot_id=?',
                    (task_id, archived.snapshot_id)).fetchone()
                if binding:
                    if self._profile.key:
                        active = current_output(task, 'A02')
                        members = active['output'].get('source_set', {})
                        expected = dict(snapshot_id=archived.snapshot_id,
                                        manifest_hash=archived.snapshot_manifest_hash, import_revision_id=binding[0])
                        if members.get(self._profile.key) == expected:
                            validated_members(self._store, task, members, self._origin.value, extent)
                            self._store.event(task_id, 'A02', 'source_import_noop',
                                              snapshot_id=archived.snapshot_id, revision_id=binding[0],
                                              active_revision_id=active['revision_id'],
                                              snapshot_manifest_hash=archived.snapshot_manifest_hash)
                            return RevisionBinding(task_id, binding[0], archived.snapshot_id)
                    if task['active_revisions'].get('A02') != binding[0]:
                        raise ValueError('Historical binding cannot be silently reactivated')
                    output = current_output(task, 'A02')['output']
                    key = 'source-import/' + archived.snapshot_id
                    if (output.get('source_snapshot_id') != archived.snapshot_id
                            or output.get('snapshot_manifest_hash') != archived.snapshot_manifest_hash
                            or task['idempotency'].get(key, {}).get('fingerprint')
                            != archived.snapshot_manifest_hash):
                        raise ValueError('Binding lacks trusted source publication evidence')
                    self._store.event(task_id, 'A02', 'source_import_noop',
                                      snapshot_id=archived.snapshot_id, revision_id=binding[0],
                                      snapshot_manifest_hash=archived.snapshot_manifest_hash)
                    return RevisionBinding(task_id, binding[0], archived.snapshot_id)
                phase = 'promotion'
                features = self._sources.features(archived.snapshot_id)
                members, carried = {}, {}
                if self._profile.key and 'A02' in task['active_revisions']:
                    active = current_output(task, 'A02')
                    members = dict(active['output'].get('source_set', {}))
                    # Replacement removes exactly this collection, preserving every other
                    # source only after trusted publication and offline evidence readback.
                    members.pop(self._profile.key, None)
                    carried = validated_members(self._store, task, members, self._origin.value, extent)
                proposal = dict(summary='Validated ' + self._origin.value + ' PDOK ' + self._profile.dataset + ' ' + self._profile.collection + ' MINIMAL_PROOF',
                                objects=[], findings=[], conditions=[], variants=[], responses=[],
                                review=None, hypothesis_variant_id=None)
                bundles = [(self._profile.key, archived.snapshot_id, features)]
                bundles.extend((key, result.snapshot.snapshot_id, result.features)
                               for key, result in sorted(carried.items()))
                for contract, sid, bundle_features in bundles:
                    for feature in bundle_features:
                        local_id = 'source/' + ((contract + '/') if contract else '') + feature.source_id
                        K00Policy.authorize(local_id, 'write', origin='derived', classification='derived')
                        proposal['objects'].append(dict(
                            local_id=local_id, object_type='EXISTING_FEATURE',
                            geometry_ref=feature.geometry_ref, geometry_status='EXISTING_VALIDATED',
                            source_basis=[feature.geometry_ref],
                            properties={'description': 'Validated ' + self._origin.value + ' ' + (contract or 'pand'),
                                        'source_id': feature.source_id, 'snapshot_id': sid}))
                key = 'source-import/' + archived.snapshot_id
                if key in task['idempotency']:
                    raise ValueError('Conflicting source-import idempotency identity')
                self._workflow._apply(task, 'A02', 'A02', self._workflow.inputs(task, 'A02'),
                                      proposal, key, archived.snapshot_manifest_hash,
                                      source_status=self._origin.value)
                revision = task['active_revisions']['A02']
                output = task['outputs'][-1]['output']
                output.update(source_snapshot_id=archived.snapshot_id,
                              snapshot_manifest_hash=archived.snapshot_manifest_hash)
                if self._profile.key:
                    members[self._profile.key] = dict(snapshot_id=archived.snapshot_id,
                        manifest_hash=archived.snapshot_manifest_hash, import_revision_id=revision)
                    output['source_set'] = members
                task['updated_at'] = now()
                self._store._save(task)
                phase = 'binding'
                result = RevisionBinding(task_id, revision, archived.snapshot_id)
                self._sources._bind_revision(result)
                phase = 'audit'
                self._store.event(task_id, 'A02', 'source_import_completed',
                                  snapshot_id=archived.snapshot_id, revision_id=revision,
                                  snapshot_manifest_hash=archived.snapshot_manifest_hash,
                                  previous=ImportStatus.VALIDATING, target=ImportStatus.COMPLETE,
                                  geometry_status='EXISTING_VALIDATED', source_status=self._origin.value,
                                  query_scope_complete=proof.query_scope_complete,
                                  point_in_time_consistency=proof.point_in_time_consistency,
                                  **({'source_set': members} if self._profile.key else {}))
            return result
        except Exception as exc:
            # Publication transaction has rolled back before failure audit.
            # Staged raw bytes are untrusted evidence, not a partial snapshot.
            error = SourceImportError(phase, fetched)
            try:
                with self._store.db:
                    self._store.db.execute('BEGIN IMMEDIATE')
                    self._store.event(task_id, 'A02', 'source_import_failed', snapshot_id=snapshot_id,
                                      failure_phase=phase, error_type=type(exc).__name__,
                                      target=ImportStatus.INCOMPLETE,
                                      reason='Import not published; trusted state unchanged')
            except Exception as audit_error:
                raise error from audit_error
            raise error from exc

    def _stage(self, task_id, snapshot_id, fetched):
        with self._store.db:
            self._store.db.execute('BEGIN IMMEDIATE')
            for capture in fetched.captures:
                self._sources.add_raw(capture.raw)
            self._store.event(task_id, 'A02', 'source_import_staged', snapshot_id=snapshot_id,
                              target=ImportStatus.STAGING, fetch_status=fetched.status,
                              manifest=json.loads(fetched.manifest_json), captures=[
                                  dict(raw_response_hash=c.raw.raw_response_hash,
                                       request_url=c.request.url, request_parameters=c.request.parameters,
                                       response_status=c.response.status, response_headers=c.response.headers,
                                       origin=c.response.origin, started=c.retrieval_started_at,
                                       finished=c.retrieval_finished_at) for c in fetched.captures])

    def _validate_provenance(self, fetched, *, archived=False):
        if not fetched.pages or not fetched.captures:
            raise ValueError('Page/capture evidence required')
        captures = {(c.request.url, c.raw.raw_response_hash): c for c in fetched.captures
                    if c.response.status == 200}
        pages = {p.page_number: p for p in fetched.pages}
        for capture in fetched.captures:
            if capture.response.origin != self._origin:
                raise ValueError('Response origin does not match explicit import profile')
        for page in fetched.pages:
            capture = captures.get((page.request_url, page.raw_response_hash))
            relevant = {'content-type', 'content-crs', 'etag', 'last-modified'}
            page_headers = {k: v for k, v in strict_json(page.response_headers_json).items()
                            if not archived or k in relevant}
            capture_headers = ({k.lower(): v for k, v in capture.response.headers
                                if not archived or k.lower() in relevant} if capture else {})
            if (capture is None or page.http_status != capture.response.status
                    or strict_json(page.request_parameters_json) != dict(capture.request.parameters)
                    or page_headers != capture_headers):
                raise ValueError('Page/capture provenance mismatch')
        geometry_map = {g.geometry_ref: g for g in fetched.geometries}
        for feature in fetched.features:
            page = pages[feature.page_number]
            provenance = strict_json(feature.provenance_json)
            expected = dict(provider='PDOK', dataset=self._profile.dataset, collection=self._profile.collection, source_status=self._origin.value,
                            feature_id=feature.source_id, request_url=page.request_url,
                            raw_response_hash=page.raw_response_hash,
                            collection_metadata=strict_json(self._adapter.collection_metadata_json),
                            request_parameters=strict_json(page.request_parameters_json),
                            content_type=page.media_type,
                            content_crs=strict_json(page.response_headers_json)['content-crs'])
            if any(provenance.get(key) != value for key, value in expected.items()):
                raise ValueError('Insufficient or conflicting feature provenance')
            geometry = geometry_map[feature.geometry_ref]
            if strict_json(geometry.provenance_json) != provenance:
                raise ValueError('Geometry/feature provenance mismatch')
            evidence = strict_json(geometry.crs_metadata.evidence)
            expected_evidence = {
                'source_status': self._origin.value, 'Content-Crs': provenance['content_crs'],
                'coordRefSys': provenance.get('coordRefSys'),
                'collection_metadata': expected['collection_metadata'],
            }
            if (any(evidence.get(k) != v for k, v in expected_evidence.items())
                    or normalize_crs_identifier(provenance.get('coordRefSys')) != 'EPSG:28992'
                    or normalize_crs_identifier(evidence.get('request_crs')) != 'EPSG:28992'
                    or normalize_crs_identifier(evidence.get('bbox_crs')) != 'EPSG:28992'):
                raise ValueError('Explicit consistent geometry CRS/origin evidence required')

    def _existing(self, snapshot):
        same_id = self._store.db.execute(
            'SELECT snapshot_manifest_hash FROM source_snapshots WHERE snapshot_id=?',
            (snapshot.snapshot_id,)).fetchone()
        if same_id and same_id[0] != snapshot.snapshot_manifest_hash:
            raise ValueError('Conflicting immutable snapshot identity')
        match = self._store.db.execute(
            'SELECT snapshot_id FROM source_snapshots WHERE provider=? AND dataset=? AND collection=? '
            'AND canonicalization_version=? AND snapshot_manifest_hash=?',
            (snapshot.provider, snapshot.dataset, snapshot.collection,
             snapshot.canonicalization_version, snapshot.snapshot_manifest_hash)).fetchone()
        return self._sources.snapshot(match[0]) if match else None

    def _validate_archive(self, snapshot, fetched):
        if snapshot.status != ImportStatus.COMPLETE:
            raise ValueError('Existing archive is not complete')
        pages, features = self._sources.pages(snapshot.snapshot_id), self._sources.features(snapshot.snapshot_id)
        self._validate_provenance(replace(
            fetched, pages=tuple(pages), features=tuple(features),
            geometries=tuple(self._sources.geometry(ref) for ref in {f.geometry_ref for f in features})),
            archived=True)
        refs = {snapshot.fetch_extent.analysis_geometry_ref} | {f.geometry_ref for f in features}
        proof = validate_completeness(
            snapshot, pages, features, [self._sources.geometry(ref) for ref in refs],
            [self._sources.raw(h) for h in {p.raw_response_hash for p in pages}])
        if proof.query_scope_complete is not True:
            raise ValueError('Persisted completeness not established')
