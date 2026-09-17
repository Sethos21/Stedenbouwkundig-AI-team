"""Immutable source contracts, separate from TESTDATA and promotion authority.

JSON payloads are strings to prevent nested mutation. RD geometry JSON is not
RFC7946 GeoJSON. Topology/CRS evidence/canonicalization validation follows in
Phase 2; these contracts only check structure and required provenance.
"""
import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from math import isfinite


class ImportStatus(StrEnum):
    STAGING = "STAGING"
    VALIDATING = "VALIDATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


class PointInTimeConsistency(StrEnum):
    NOT_GUARANTEED = "NOT_GUARANTEED"
    PROVIDER_GUARANTEED = "PROVIDER_GUARANTEED"


class GeometryRole(StrEnum):
    SOURCE_GEOMETRY = "SOURCE_GEOMETRY"
    DERIVED_GEOMETRY = "DERIVED_GEOMETRY"
    PROJECT_GEOMETRY = "PROJECT_GEOMETRY"
    ANALYSIS_GEOMETRY = "ANALYSIS_GEOMETRY"
    TESTCASE_ONLY_ANALYSIS_GEOMETRY = "TESTCASE_ONLY_ANALYSIS_GEOMETRY"
    POLICY_GEOMETRY = "POLICY_GEOMETRY"


def required(*values):
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("Non-empty text required")


def json_object(value):
    def invalid_number(value):
        raise ValueError("Non-finite JSON number")
    required(value)
    result = json.loads(value, parse_constant=invalid_number)
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def hash_value(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Lowercase SHA-256 required")


@dataclass(frozen=True)
class CRSMetadata:
    crs: str
    axis_order: tuple[str, str]
    dimension: int
    units: str
    evidence: str

    def __post_init__(self):
        required(self.crs, self.units, self.evidence)
        if type(self.axis_order) is not tuple or len(self.axis_order) != 2:
            raise ValueError("Explicit two-axis order required")
        required(*self.axis_order)
        if type(self.dimension) is not int or self.dimension != 2:
            raise ValueError("The current contract is explicitly 2D")


@dataclass(frozen=True)
class FetchExtent:
    """Technical bounds, never a project boundary or design permission."""
    bbox: tuple[float, float, float, float]
    crs: str
    analysis_geometry_ref: str

    def __post_init__(self):
        required(self.crs, self.analysis_geometry_ref)
        if (type(self.bbox) is not tuple or len(self.bbox) != 4
                or any(type(v) not in (float, int) or not isfinite(v) for v in self.bbox)
                or self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]):
            raise ValueError("Finite ordered 2D bbox required")


@dataclass(frozen=True)
class GeometryRecord:
    geometry_ref: str
    geometry_json: str
    crs_metadata: CRSMetadata
    geometry_structural_hash: str
    canonicalization_version: str
    role: GeometryRole
    provenance_json: str
    parent_geometry_refs: tuple[str, ...] = ()
    derivation_json: str | None = None

    def __post_init__(self):
        required(self.geometry_ref, self.canonicalization_version)
        hash_value(self.geometry_structural_hash)
        GeometryRole(self.role)
        if not isinstance(self.crs_metadata, CRSMetadata):
            raise ValueError("Explicit CRS metadata required")
        geometry = json_object(self.geometry_json)
        if set(geometry) != {"type", "coordinates"}:
            raise ValueError("Internal geometry requires type and coordinates only")
        required(geometry["type"])
        if not isinstance(geometry["coordinates"], list):
            raise ValueError("Coordinate array required")
        if not json_object(self.provenance_json):
            raise ValueError("Geometry provenance required")
        if type(self.parent_geometry_refs) is not tuple:
            raise ValueError("Immutable lineage required")
        required(*self.parent_geometry_refs)
        if self.geometry_ref in self.parent_geometry_refs or len(set(self.parent_geometry_refs)) != len(self.parent_geometry_refs):
            raise ValueError("Invalid lineage")
        if self.role == GeometryRole.DERIVED_GEOMETRY and not self.parent_geometry_refs:
            raise ValueError("Derived geometry requires parents")
        if self.parent_geometry_refs:
            if self.role == GeometryRole.SOURCE_GEOMETRY or not self.derivation_json or not json_object(self.derivation_json):
                raise ValueError("Derived lineage requires operation provenance")
        elif self.derivation_json is not None:
            raise ValueError("Derivation requires parents")


@dataclass(frozen=True)
class RawResponse:
    raw_response_hash: str
    body: bytes

    def __post_init__(self):
        hash_value(self.raw_response_hash)
        if type(self.body) is not bytes or sha256(self.body).hexdigest() != self.raw_response_hash:
            raise ValueError("Raw response bytes/hash mismatch")


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_id: str
    provider: str
    dataset: str
    collection: str
    endpoint: str
    fetch_extent: FetchExtent
    request_crs: str
    response_crs: str
    request_parameters_json: str
    temporal_query: str
    retrieval_started_at: str
    retrieval_finished_at: str
    status: ImportStatus
    point_in_time_consistency: PointInTimeConsistency
    consistency_evidence: str
    page_count: int
    feature_count: int
    snapshot_manifest_hash: str
    canonicalization_version: str
    parser_version: str
    validator_version: str
    provenance_json: str

    def __post_init__(self):
        required(self.snapshot_id, self.provider, self.dataset, self.collection, self.endpoint,
                 self.request_crs, self.response_crs, self.temporal_query,
                 self.retrieval_started_at, self.retrieval_finished_at, self.consistency_evidence,
                 self.canonicalization_version, self.parser_version, self.validator_version)
        if not isinstance(self.fetch_extent, FetchExtent):
            raise ValueError("FetchExtent required")
        ImportStatus(self.status)
        PointInTimeConsistency(self.point_in_time_consistency)
        hash_value(self.snapshot_manifest_hash)
        json_object(self.request_parameters_json)
        if not json_object(self.provenance_json):
            raise ValueError("Snapshot provenance required")
        if any(type(n) is not int or n < 0 for n in (self.page_count, self.feature_count)):
            raise ValueError("Nonnegative counts required")


@dataclass(frozen=True)
class SourcePage:
    snapshot_id: str
    page_number: int
    raw_response_hash: str
    request_url: str
    request_parameters_json: str
    retrieved_at: str
    media_type: str
    response_headers_json: str
    response_crs: str
    http_status: int
    cursor: str | None = None
    next_url: str | None = None

    def __post_init__(self):
        required(self.snapshot_id, self.request_url, self.retrieved_at, self.media_type, self.response_crs)
        hash_value(self.raw_response_hash)
        json_object(self.request_parameters_json)
        json_object(self.response_headers_json)
        if type(self.page_number) is not int or self.page_number < 1:
            raise ValueError("Positive page number required")
        if type(self.http_status) is not int or not 100 <= self.http_status <= 599:
            raise ValueError("HTTP status required")


@dataclass(frozen=True)
class SourceFeature:
    snapshot_id: str
    source_id: str
    source_version: str | None
    geometry_ref: str
    page_number: int
    properties_json: str
    provenance_json: str

    def __post_init__(self):
        required(self.snapshot_id, self.source_id, self.geometry_ref)
        if self.source_version is not None:
            required(self.source_version)
        if type(self.page_number) is not int or self.page_number < 1:
            raise ValueError("Positive page number required")
        json_object(self.properties_json)
        if not json_object(self.provenance_json):
            raise ValueError("Feature provenance required")


@dataclass(frozen=True)
class RevisionBinding:
    task_id: str
    revision_id: str
    snapshot_id: str

    def __post_init__(self):
        required(self.task_id, self.revision_id, self.snapshot_id)
        if not self.revision_id.startswith("A02/v") or not self.revision_id[5:].isdigit() or int(self.revision_id[5:]) < 1:
            raise ValueError("A02 revision required")
