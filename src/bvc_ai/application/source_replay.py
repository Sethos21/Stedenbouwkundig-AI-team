"""Offline reconstruction from Phase 4 evidence; no transport or promotion."""
import json
from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlsplit

from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter, ITEMS_URL, PARSER_VERSION, _continuation
from bvc_ai.adapters.source_transport import CapturedResponse, GetRequest, HttpResponse, ResponseOrigin
from bvc_ai.domain.source_profiles import source_profile
from bvc_ai.domain.sources import SourceSnapshot, GeometryRecord, ImportStatus
from bvc_ai.domain.source_hashing import snapshot_manifest_hash
from bvc_ai.domain.source_validation import validate_completeness
from bvc_ai.infrastructure.source_store import SourceStore
from bvc_ai.application.live_source_validation import (
    LIVE_PROFILE, validate_live_analysis, validate_live_capture,
)


@dataclass(frozen=True)
class ReplayEvidence:
    snapshot: SourceSnapshot
    analysis: GeometryRecord
    captures: tuple[CapturedResponse, ...]
    fetch_manifest_json: str


@dataclass(frozen=True)
class ReplayResult:
    snapshot: SourceSnapshot
    pages: tuple
    features: tuple
    geometries: tuple
    raw_responses: tuple


class SourceReplayService:
    def __init__(self, store):
        self._store = store
        self._sources = SourceStore(store)

    def evidence(self, snapshot_id):
        """Read the original successful capture set, never a later reimport attempt."""
        snapshot = self._sources.snapshot(snapshot_id)
        for event in self._store.events():
            if event['action'] != 'source_import_staged':
                continue
            details = event['details']
            if details.get('snapshot_id') != snapshot_id:
                continue
            records = details.get('captures', [])
            if (not records or records[0]['started'] != snapshot.retrieval_started_at
                    or records[-1]['finished'] != snapshot.retrieval_finished_at):
                continue
            manifest = details.get('manifest', {})
            if (details.get('fetch_status') != ImportStatus.VALIDATING
                    or manifest.get('pagination_exhausted') is not True
                    or manifest.get('failure_reason') is not None):
                continue
            captures = []
            for record in records:
                raw = self._sources.raw(record['raw_response_hash'])
                # Outgoing headers/timeouts are not parser input and are not invented.
                request = GetRequest(record['request_url'],
                                     tuple(tuple(p) for p in record['request_parameters']), ())
                response = HttpResponse(record['response_status'],
                                        tuple(tuple(p) for p in record['response_headers']),
                                        raw.body, ResponseOrigin(record['origin']))
                captures.append(CapturedResponse(request, response, raw,
                                                 record['started'], record['finished']))
            return ReplayEvidence(snapshot, self._sources.geometry(snapshot.fetch_extent.analysis_geometry_ref),
                                  tuple(captures), json.dumps(manifest))
        raise ValueError('Original successful capture evidence missing')

    @staticmethod
    def reconstruct(evidence):
        """Reparse captured successful pages; compare against the archived manifest."""
        if not isinstance(evidence, ReplayEvidence):
            raise ValueError('ReplayEvidence required')
        snapshot, analysis = evidence.snapshot, evidence.analysis
        snapshot.__post_init__()
        provenance = json.loads(snapshot.provenance_json)
        profile = source_profile(provenance.get('source_contract'))
        live = provenance.get('profile') in (LIVE_PROFILE, 'PDOK_2D_LIVE')
        expected_profile = (('PDOK_2D_LIVE' if live else 'PDOK_2D_TESTDATA') if profile.key
                            else (LIVE_PROFILE if live else 'PDOK_PAND_MINIMAL_PROOF'))
        origin = ResponseOrigin.PROVIDER_RESPONSE if live else ResponseOrigin.TESTDATA
        if live:
            validate_live_analysis(analysis, snapshot.fetch_extent)
        if (snapshot.status != ImportStatus.COMPLETE or snapshot.provider != 'PDOK'
                or snapshot.dataset != profile.dataset or snapshot.collection != profile.collection
                or snapshot.endpoint != profile.items_url or snapshot.parser_version != profile.parser_version
                or provenance.get('source_status') != origin
                or provenance.get('profile') != expected_profile
                or analysis.geometry_ref != snapshot.fetch_extent.analysis_geometry_ref
                or (not live and json.loads(analysis.provenance_json).get('source_status') != 'TESTDATA')):
            raise ValueError('Unsupported or inconsistent replay profile')
        adapter = PDOKBGTAdapter(None, collection_metadata_json=json.dumps(provenance['collection_metadata']), source_contract=profile.key)
        parameters = json.loads(snapshot.request_parameters_json)
        limit = int(parameters['limit'])
        initial = adapter.build_request(snapshot.fetch_extent, limit=limit)
        if parameters != dict(initial.parameters):
            raise ValueError('Snapshot request scope mismatch')
        if (not evidence.captures
                or evidence.captures[0].retrieval_started_at != snapshot.retrieval_started_at
                or evidence.captures[-1].retrieval_finished_at != snapshot.retrieval_finished_at):
            raise ValueError('Capture interval missing or mismatched')
        manifest = json.loads(evidence.fetch_manifest_json)
        attempts = manifest.get('attempts', [])
        if (manifest.get('pagination_exhausted') is not True
                or manifest.get('failure_reason') is not None
                or manifest.get('pending_continuation') is not None
                or manifest.get('page_count') != snapshot.page_count
                or manifest.get('feature_count') != snapshot.feature_count
                or len(attempts) != len(evidence.captures)
                or manifest.get('received_bytes') != sum(len(c.raw.body) for c in evidence.captures)):
            raise ValueError('Incomplete or mismatched fetch evidence')
        for attempt, capture in zip(attempts, evidence.captures):
            if (attempt.get('request_url') != capture.request.url
                    or attempt.get('raw_response_hash') != capture.raw.raw_response_hash
                    or attempt.get('http_status') != capture.response.status
                    or attempt.get('response_bytes') != len(capture.raw.body)):
                raise ValueError('Capture differs from stored fetch attempt')
        expected_url = initial.url
        pages, features, geometries, raw = [], [], [analysis], {}
        for capture in evidence.captures:
            if live:
                validate_live_capture(capture, expected_url, replay=True, source_contract=profile.key,
                                      extent=snapshot.fetch_extent)
            capture.raw.__post_init__()
            capture.response.__post_init__()
            if (capture.response.origin != origin
                    or capture.response.body != capture.raw.body
                    or capture.request.url != expected_url
                    or capture.request.parameters != tuple(parse_qsl(
                        urlsplit(capture.request.url).query, keep_blank_values=True))):
                raise ValueError('Capture bytes/origin/request mismatch')
            raw[capture.raw.raw_response_hash] = capture.raw
            if capture.response.status == 429 or 500 <= capture.response.status <= 599:
                continue  # Retain error evidence; no retry or transport is executed.
            parsed = adapter._parse(capture, snapshot.snapshot_id, limit)
            number = len(pages) + 1
            outgoing = parsed.page.next_url
            expected_url = adapter.continuation(outgoing, capture.request.url, snapshot.fetch_extent, limit) if outgoing is not None else None
            pages.append(replace(parsed.page, page_number=number, next_url=expected_url))
            features.extend(replace(f, page_number=number) for f in parsed.features)
            geometries.extend(parsed.geometries)
        if expected_url is not None or not pages:
            raise ValueError('Incomplete replay pagination')
        page_raw = tuple(raw[h] for h in sorted({p.raw_response_hash for p in pages}))
        proof = validate_completeness(snapshot, pages, features, geometries, page_raw)
        if not proof.query_scope_complete:
            raise ValueError('Replay completeness not established')
        computed = snapshot_manifest_hash(snapshot, pages, features, geometries)
        if computed != snapshot.snapshot_manifest_hash:
            raise ValueError('Replay manifest mismatch')
        return ReplayResult(replace(snapshot, snapshot_manifest_hash=computed), tuple(pages),
                            tuple(sorted(features, key=lambda f: f.source_id)),
                            tuple(sorted(geometries, key=lambda g: g.geometry_ref)),
                            tuple(raw[h] for h in sorted(raw)))

    def verify(self, snapshot_id):
        result = self.reconstruct(self.evidence(snapshot_id))
        stored_features = tuple(self._sources.features(snapshot_id))
        refs = {result.snapshot.fetch_extent.analysis_geometry_ref} | {f.geometry_ref for f in stored_features}
        stored_geometry = tuple(self._sources.geometry(ref) for ref in sorted(refs))
        if (result.pages != tuple(self._sources.pages(snapshot_id))
                or result.features != stored_features or result.geometries != stored_geometry):
            raise ValueError('Reconstructed records/provenance differ from archive')
        return result

    @staticmethod
    def reconstruct_into(evidence, target):
        """Build only an archive in a separate task-free replay target, atomically.

        COMPLETE is copied archive metadata, never a new trusted publication.
        No task, object, revision, binding, audit or capability is created.
        """
        if target.db.in_transaction:
            raise ValueError('Replay requires its own target transaction')
        result = SourceReplayService.reconstruct(evidence)
        sources = SourceStore(target)
        with target.db:
            target.db.execute('BEGIN IMMEDIATE')
            if (target.db.execute('SELECT 1 FROM tasks LIMIT 1').fetchone()
                    or target.db.execute('SELECT 1 FROM source_revision_bindings LIMIT 1').fetchone()):
                raise ValueError('Replay target must be separate from task/trusted state')
            for raw in result.raw_responses:
                sources.add_raw(raw)
            for geometry in result.geometries:
                sources.add_geometry(geometry)
            sources.add_snapshot(result.snapshot)
            for page in result.pages:
                sources.add_page(page)
            for feature in result.features:
                sources.add_feature(feature)
        return result
