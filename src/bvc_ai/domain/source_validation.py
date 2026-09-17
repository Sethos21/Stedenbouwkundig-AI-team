"""Offline query-scope validation. No Store, transport, lifecycle or promotion."""
from dataclasses import dataclass

from bvc_ai.domain.sources import (
    SourceSnapshot, SourcePage, SourceFeature, GeometryRecord, GeometryRole,
    RawResponse, ImportStatus, PointInTimeConsistency,
)
from bvc_ai.domain.geometry_validation import (
    CANONICAL_CRS, VALIDATOR_VERSION, validate_geometry_record,
)
from bvc_ai.domain.source_hashing import (
    CANONICALIZATION_VERSION, normalize_crs_identifier, raw_response_hash,
    snapshot_manifest_hash, strict_json,
)


@dataclass(frozen=True)
class CompletenessValidation:
    query_scope_complete: bool
    point_in_time_consistency: PointInTimeConsistency
    consistency_evidence: str
    snapshot_manifest_hash: str
    page_count: int
    feature_count: int
    validator_version: str = VALIDATOR_VERSION


def _records(records, record_type, key):
    result = {}
    for record in records:
        if not isinstance(record, record_type):
            raise ValueError("Unexpected source record type")
        record.__post_init__()
        identity = key(record)
        if identity in result:
            raise ValueError("Duplicate source identity")
        result[identity] = record
    return result


def validate_completeness(snapshot, pages, features, geometries, raw_responses,
                          *, failure_markers=()):
    """Check an exact, already parsed archive bundle against declared counts.

    SourcePage.cursor denotes an outgoing continuation token. It must equal the
    following page's request_parameters_json["cursor"]; a next_url must equal
    the following request_url. Both, when present, must resolve. The final page
    must have neither. Parsing/trusting provider payloads remains adapter work.
    """
    if not isinstance(snapshot, SourceSnapshot):
        raise ValueError("SourceSnapshot required")
    snapshot.__post_init__()
    snapshot.fetch_extent.__post_init__()
    if type(failure_markers) is not tuple or failure_markers:
        raise ValueError("Failure/incomplete markers prevent completeness")
    if snapshot.status in (ImportStatus.FAILED, ImportStatus.INCOMPLETE):
        raise ValueError("Failed/incomplete snapshot")
    if snapshot.canonicalization_version != CANONICALIZATION_VERSION:
        raise ValueError("Unsupported snapshot canonicalization version")
    if snapshot.validator_version != VALIDATOR_VERSION:
        raise ValueError("Unsupported snapshot validator version")
    for crs in (snapshot.request_crs, snapshot.response_crs, snapshot.fetch_extent.crs):
        if normalize_crs_identifier(crs) != CANONICAL_CRS:
            raise ValueError("Query scope and response require native RD")

    page_map = _records(pages, SourcePage, lambda p: p.page_number)
    feature_map = _records(features, SourceFeature, lambda f: f.source_id)
    geometry_map = _records(geometries, GeometryRecord, lambda g: g.geometry_ref)
    raw_map = _records(raw_responses, RawResponse, lambda r: r.raw_response_hash)
    if snapshot.page_count < 1 or set(page_map) != set(range(1, snapshot.page_count + 1)):
        raise ValueError("All declared pages, including an empty result page, required")
    if len(feature_map) != snapshot.feature_count:
        raise ValueError("Feature count differs from declared manifest")
    if any(p.snapshot_id != snapshot.snapshot_id for p in page_map.values()):
        raise ValueError("Page belongs to another snapshot")
    if any(f.snapshot_id != snapshot.snapshot_id for f in feature_map.values()):
        raise ValueError("Feature belongs to another snapshot")

    used_raw = set()
    seen_requests = set()
    seen_cursors = set()
    for number in range(1, snapshot.page_count + 1):
        page = page_map[number]
        if not 200 <= page.http_status < 300:
            raise ValueError("Unsuccessful response page")
        if normalize_crs_identifier(page.response_crs) != CANONICAL_CRS:
            raise ValueError("Page response CRS is not native RD")
        headers = strict_json(page.response_headers_json)
        if not isinstance(headers, dict):
            raise ValueError("Response headers object required")
        for name, value in headers.items():
            if name.lower() == "content-crs":
                if not isinstance(value, str):
                    raise ValueError("Invalid Content-Crs header")
                if normalize_crs_identifier(value.strip().removeprefix("<").removesuffix(">")) != CANONICAL_CRS:
                    raise ValueError("Response header contradicts RD label")
        if page.raw_response_hash not in raw_map:
            raise ValueError("Missing raw page")
        raw = raw_map[page.raw_response_hash]
        if raw_response_hash(raw.body) != page.raw_response_hash:
            raise ValueError("Raw page hash mismatch")
        used_raw.add(page.raw_response_hash)
        params = strict_json(page.request_parameters_json)
        if not isinstance(params, dict):
            raise ValueError("Request parameter object required")
        # URL and parameters jointly identify requests (cursor may be separate).
        from bvc_ai.domain.source_hashing import canonical_bytes
        request_identity = (page.request_url, canonical_bytes(params))
        if request_identity in seen_requests:
            raise ValueError("Repeated page request / pagination cycle")
        seen_requests.add(request_identity)
        for continuation in (page.next_url, page.cursor):
            if continuation is not None and (not isinstance(continuation, str) or not continuation.strip()):
                raise ValueError("Invalid continuation marker")
        if number == snapshot.page_count:
            if page.next_url is not None or page.cursor is not None:
                raise ValueError("Unresolved next/cursor")
        else:
            next_page = page_map[number + 1]
            if page.next_url is None and page.cursor is None:
                raise ValueError("Unproven page chain")
            if page.next_url is not None and page.next_url != next_page.request_url:
                raise ValueError("Unresolved next link")
            if page.cursor is not None:
                next_params = strict_json(next_page.request_parameters_json)
                if not isinstance(next_params, dict) or next_params.get("cursor") != page.cursor:
                    raise ValueError("Unresolved cursor")
                if page.cursor in seen_cursors:
                    raise ValueError("Cursor cycle")
                seen_cursors.add(page.cursor)
    if used_raw != set(raw_map):
        raise ValueError("Raw bundle differs from page references")

    scope_ref = snapshot.fetch_extent.analysis_geometry_ref
    if scope_ref not in geometry_map:
        raise ValueError("Missing analysis geometry")
    if geometry_map[scope_ref].role not in (
        GeometryRole.ANALYSIS_GEOMETRY, GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY,
    ):
        raise ValueError("Scope requires analysis geometry")
    used_geometry = {scope_ref}
    for feature in feature_map.values():
        if feature.page_number not in page_map:
            raise ValueError("Missing feature/page reference")
        if feature.geometry_ref not in geometry_map:
            raise ValueError("Missing feature/geometry reference")
        if geometry_map[feature.geometry_ref].role != GeometryRole.SOURCE_GEOMETRY:
            raise ValueError("Feature requires source geometry")
        used_geometry.add(feature.geometry_ref)
    if used_geometry != set(geometry_map):
        raise ValueError("Geometry bundle differs from declared references")
    for geometry in geometry_map.values():
        validate_geometry_record(geometry, source_crs=snapshot.response_crs)
    computed = snapshot_manifest_hash(
        snapshot, page_map.values(), feature_map.values(), geometry_map.values())
    if computed != snapshot.snapshot_manifest_hash:
        raise ValueError("Snapshot manifest hash mismatch")
    # Preserve provider guarantee verbatim; query completion never creates one.
    return CompletenessValidation(
        True, PointInTimeConsistency(snapshot.point_in_time_consistency),
        snapshot.consistency_evidence, computed, len(page_map), len(feature_map),
    )
