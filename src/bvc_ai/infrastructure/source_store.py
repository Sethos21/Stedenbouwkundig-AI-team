"""Internal source archive on Store.db; never supplied to agents/providers.

No commit, promotion, active snapshot selection or EXISTING_VALIDATED assignment.
The caller owns the transaction. In Phase 4 only the trusted A02 service will
combine validated archives, revision binding, stale propagation and audit.
"""
import json
from dataclasses import asdict
from bvc_ai.domain.sources import (
    CRSMetadata, FetchExtent, GeometryRecord, GeometryRole, RawResponse,
    SourceSnapshot, SourcePage, SourceFeature, RevisionBinding, ImportStatus,
)


def encode(record):
    return json.dumps(asdict(record), sort_keys=True, separators=(",", ":"), allow_nan=False)


class SourceStore:
    def __init__(self, store):
        self.store = store
        self.db = store.db

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Caller must open an explicit source transaction")
        if self.db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("Foreign keys required")

    def _insert(self, table, columns, values, keys):
        self._transaction()
        where = " AND ".join(f"{key}=?" for key in keys)
        row = self.db.execute(
            f"SELECT {','.join(columns)} FROM {table} WHERE {where}",
            tuple(values[columns.index(k)] for k in keys)).fetchone()
        if row is not None:
            if tuple(values) != row:
                raise ValueError("Conflicting immutable source identity")
            return False
        self.db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in values)})", values)
        return True

    def add_raw(self, record: RawResponse):
        record.__post_init__()
        return self._insert("raw_responses", ("raw_response_hash", "body"),
                            (record.raw_response_hash, record.body), ("raw_response_hash",))

    def add_geometry(self, record: GeometryRecord):
        record.__post_init__()
        self._transaction()
        # Parents must already exist. Append-only insertion prevents cycles.
        for parent in record.parent_geometry_refs:
            self.geometry(parent)
        inserted = self._insert("geometry_records",
            ("geometry_ref", "geometry_structural_hash", "canonicalization_version", "role", "body"),
            (record.geometry_ref, record.geometry_structural_hash, record.canonicalization_version,
             record.role, encode(record)), ("geometry_ref",))
        if inserted:
            for parent in record.parent_geometry_refs:
                self.db.execute("INSERT INTO geometry_lineage VALUES (?,?)", (record.geometry_ref, parent))
        return inserted

    def add_snapshot(self, record: SourceSnapshot):
        """Archive metadata only; COMPLETE here does not confer validated status."""
        record.__post_init__()
        self._transaction()
        scope = self.geometry(record.fetch_extent.analysis_geometry_ref)
        if scope.role not in {GeometryRole.ANALYSIS_GEOMETRY, GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY}:
            raise ValueError("Fetch scope requires an AnalysisGeometry reference")
        if scope.crs_metadata.crs != record.fetch_extent.crs:
            raise ValueError("FetchExtent and analysis CRS differ")
        return self._insert("source_snapshots",
            ("snapshot_id", "provider", "dataset", "collection", "snapshot_manifest_hash",
             "canonicalization_version", "status", "analysis_geometry_ref", "body"),
            (record.snapshot_id, record.provider, record.dataset, record.collection,
             record.snapshot_manifest_hash, record.canonicalization_version, record.status,
             record.fetch_extent.analysis_geometry_ref, encode(record)), ("snapshot_id",))

    def add_page(self, record: SourcePage):
        record.__post_init__()
        self._transaction()
        snapshot = self.snapshot(record.snapshot_id)
        if record.page_number > snapshot.page_count:
            raise ValueError("Page outside declared manifest")
        return self._insert("source_pages", ("snapshot_id", "page_number", "raw_response_hash", "body"),
            (record.snapshot_id, record.page_number, record.raw_response_hash, encode(record)),
            ("snapshot_id", "page_number"))

    def add_feature(self, record: SourceFeature):
        record.__post_init__()
        self._transaction()
        # A source feature cannot silently refer to a project/analysis/derived geometry.
        if self.geometry(record.geometry_ref).role != GeometryRole.SOURCE_GEOMETRY:
            raise ValueError("Source feature requires intact source geometry")
        snapshot = self.snapshot(record.snapshot_id)
        exists = self.db.execute(
            "SELECT 1 FROM source_features WHERE snapshot_id=? AND source_id=?",
            (record.snapshot_id, record.source_id)).fetchone()
        count = self.db.execute("SELECT count(*) FROM source_features WHERE snapshot_id=?",
                                (record.snapshot_id,)).fetchone()[0]
        if exists is None and count >= snapshot.feature_count:
            raise ValueError("Feature outside declared manifest")

        return self._insert("source_features",
            ("snapshot_id", "source_id", "geometry_ref", "page_number", "body"),
            (record.snapshot_id, record.source_id, record.geometry_ref, record.page_number, encode(record)),
            ("snapshot_id", "source_id"))

    def _bind_revision(self, record: RevisionBinding):
        """Internal binding, not promotion. No public/downstream source API yet."""
        record.__post_init__()
        self._transaction()
        task = self.store.get(record.task_id)
        if task["status"] in {"APPROVED", "REJECTED"}:
            raise ValueError("Historical human decision is immutable")
        if not any(o.get("revision_id") == record.revision_id and o.get("agent_id") == "A02"
                   for o in task.get("outputs", [])):
            raise ValueError("Existing A02 revision required")
        snapshot = self.snapshot(record.snapshot_id)
        if snapshot.status != ImportStatus.COMPLETE:
            raise ValueError("Incomplete snapshot cannot bind a revision")
        pages = self.pages(record.snapshot_id)
        if (len(pages) != snapshot.page_count or not pages
                or pages[-1].next_url is not None
                or len(self.features(record.snapshot_id)) != snapshot.feature_count):
            raise ValueError("Archive does not match declared counts")
        return self._insert("source_revision_bindings", ("task_id", "revision_id", "snapshot_id"),
            (record.task_id, record.revision_id, record.snapshot_id), ("task_id", "revision_id"))

    def _body(self, table, key, value):
        row = self.db.execute(f"SELECT body FROM {table} WHERE {key}=?", (value,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown {table} reference")
        return json.loads(row[0])

    def geometry(self, geometry_ref):
        data = self._body("geometry_records", "geometry_ref", geometry_ref)
        crs = data["crs_metadata"]
        crs["axis_order"] = tuple(crs["axis_order"])
        data["crs_metadata"] = CRSMetadata(**crs)
        data["parent_geometry_refs"] = tuple(data["parent_geometry_refs"])
        return GeometryRecord(**data)

    def raw(self, raw_response_hash):
        row = self.db.execute("SELECT body FROM raw_responses WHERE raw_response_hash=?", (raw_response_hash,)).fetchone()
        if row is None:
            raise ValueError("Unknown raw response")
        return RawResponse(raw_response_hash, row[0])

    def snapshot(self, snapshot_id):
        data = self._body("source_snapshots", "snapshot_id", snapshot_id)
        extent = data["fetch_extent"]
        extent["bbox"] = tuple(extent["bbox"])
        data["fetch_extent"] = FetchExtent(**extent)
        return SourceSnapshot(**data)

    def pages(self, snapshot_id):
        return [SourcePage(**json.loads(r[0])) for r in self.db.execute(
            "SELECT body FROM source_pages WHERE snapshot_id=? ORDER BY page_number", (snapshot_id,))]

    def features(self, snapshot_id):
        return [SourceFeature(**json.loads(r[0])) for r in self.db.execute(
            "SELECT body FROM source_features WHERE snapshot_id=? ORDER BY source_id", (snapshot_id,))]
