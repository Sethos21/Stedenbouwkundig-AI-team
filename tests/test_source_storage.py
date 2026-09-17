"""Network-free storage contracts. No source promotion or official-data claims."""
import json
import sqlite3
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from bvc_ai.domain.sources import (
    CRSMetadata, FetchExtent, GeometryRecord, GeometryRole, RawResponse,
    SourceSnapshot, SourceFeature, SourcePage, RevisionBinding,
    ImportStatus, PointInTimeConsistency,
)
from bvc_ai.infrastructure.store import Store
from bvc_ai.infrastructure.source_store import SourceStore
from bvc_ai.infrastructure.source_schema import SCHEMA_VERSION, SOURCE_TABLES, migrate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/source_archive.json").read_text(encoding="utf-8-sig"))


def js(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    # Test-only identity; production geometry canonicalization belongs to Phase 2.
    return sha256(value.encode()).hexdigest()


class SourceStorageTests(unittest.TestCase):
    def setUp(self):
        testroot = ROOT / ".tools/test-runs"
        testroot.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=testroot)
        self.store = Store(self.temp.name)
        self.sources = SourceStore(self.store)
        self.crs = CRSMetadata(FIXTURE["crs"], ("x", "y"), 2, "metre", "TESTDATA fixture declaration")
        provenance = js({"source_status": "TESTDATA", "fixture": "tests/fixtures/source_archive.json"})
        self.geometry = GeometryRecord("test/geometry/1", js(FIXTURE["geometry"]), self.crs,
            digest(js(FIXTURE["geometry"])), "test-only-v1", GeometryRole.SOURCE_GEOMETRY, provenance)
        self.analysis = replace(self.geometry, geometry_ref="test/analysis/1",
            geometry_json=js(FIXTURE["analysis_geometry"]),
            geometry_structural_hash=digest(js(FIXTURE["analysis_geometry"])),
            role=GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY)
        raw = js(FIXTURE["raw_response"]).encode()
        self.raw = RawResponse(sha256(raw).hexdigest(), raw)
        self.snapshot = SourceSnapshot(
            "test/snapshot/1", "TESTDATA", "synthetic", "points", "https://example.invalid/items",
            FetchExtent((-10, -10, 10, 10), FIXTURE["crs"], self.analysis.geometry_ref),
            FIXTURE["crs"], FIXTURE["crs"], '{"limit":1}', "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", ImportStatus.COMPLETE,
            PointInTimeConsistency.NOT_GUARANTEED, "Synthetic fixture, no provider guarantee",
            1, 1, digest("test manifest 1"), "test-only-v1", "test-parser", "test-validator", provenance)
        self.page = SourcePage(self.snapshot.snapshot_id, 1, self.raw.raw_response_hash,
            self.snapshot.endpoint, '{"limit":1}', "2026-01-01T00:00:00Z", "application/json",
            '{"Content-Type":"application/json"}', FIXTURE["crs"], 200)
        self.feature = SourceFeature(self.snapshot.snapshot_id, "test-feature-1", "test-v1",
            self.geometry.geometry_ref, 1, '{"source_status":"TESTDATA"}', provenance)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def archive(self):
        self.sources.add_raw(self.raw)
        self.sources.add_geometry(self.analysis)
        self.sources.add_geometry(self.geometry)
        self.sources.add_snapshot(self.snapshot)
        self.sources.add_page(self.page)
        self.sources.add_feature(self.feature)

    def transaction(self):
        self.store.db.execute("BEGIN IMMEDIATE")

    def task(self, status="READY"):
        self.store._save(dict(task_id="source-test", status=status, outputs=[
            dict(agent_id="A02", revision_id="A02/v1")], human_decisions=[]))

    def test_roundtrip_and_reopen(self):
        with self.store.db:
            self.transaction()
            self.archive()
        self.store.close()
        self.store = Store(self.temp.name)
        self.sources = SourceStore(self.store)
        self.assertEqual(self.sources.geometry(self.geometry.geometry_ref), self.geometry)
        self.assertEqual(self.sources.snapshot(self.snapshot.snapshot_id), self.snapshot)
        self.assertEqual(self.sources.raw(self.raw.raw_response_hash), self.raw)
        self.assertEqual(self.sources.pages(self.snapshot.snapshot_id), [self.page])
        self.assertEqual(self.sources.features(self.snapshot.snapshot_id), [self.feature])
        self.assertEqual(self.store.db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_exact_repeat_does_not_duplicate(self):
        with self.store.db:
            self.transaction()
            self.archive()
            self.archive()
        for table, count in (("geometry_records", 2), ("source_snapshots", 1),
                             ("source_pages", 1), ("source_features", 1), ("raw_responses", 1)):
            self.assertEqual(self.store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], count)

    def test_conflicting_geometry_identity_rejected_old_bytes_unchanged(self):
        with self.store.db:
            self.transaction()
            self.archive()
            with self.assertRaises(ValueError):
                self.sources.add_geometry(replace(self.geometry, geometry_json='{"type":"Point","coordinates":[1,1]}'))
            self.assertEqual(self.sources.geometry(self.geometry.geometry_ref), self.geometry)

    def test_changed_content_uses_new_ref_and_preserves_history(self):
        newer = replace(self.geometry, geometry_ref="test/geometry/2",
                        geometry_json='{"type":"Point","coordinates":[1,1]}',
                        geometry_structural_hash=digest("new geometry"))
        with self.store.db:
            self.transaction()
            self.archive()
            self.sources.add_geometry(newer)
        self.assertEqual(self.sources.geometry(self.geometry.geometry_ref), self.geometry)
        self.assertEqual(self.sources.geometry(newer.geometry_ref), newer)

    def test_conflicting_feature_and_snapshot_identity_rejected(self):
        with self.store.db:
            self.transaction()
            self.archive()
            with self.assertRaises(ValueError):
                self.sources.add_feature(replace(self.feature, properties_json='{"changed":true}'))
            with self.assertRaises(ValueError):
                self.sources.add_snapshot(replace(self.snapshot, feature_count=2))
            with self.assertRaises(sqlite3.IntegrityError):
                self.sources.add_snapshot(replace(self.snapshot, snapshot_id="duplicate-manifest"))

    def test_raw_bytes_verified_and_blob(self):
        with self.assertRaises(ValueError):
            RawResponse(self.raw.raw_response_hash, b"corrupt")
        with self.store.db:
            self.transaction()
            self.sources.add_raw(self.raw)
        self.assertEqual(self.store.db.execute("SELECT typeof(body) FROM raw_responses").fetchone()[0], "blob")

    def test_corrupt_raw_on_read_is_rejected(self):
        # Simulates externally corrupted storage, not an application mutation.
        with self.store.db:
            self.transaction()
            self.store.db.execute("INSERT INTO raw_responses VALUES (?,?)", (self.raw.raw_response_hash, b"corrupt"))
        with self.assertRaises(ValueError):
            self.sources.raw(self.raw.raw_response_hash)

    def test_missing_raw_page_geometry_and_task_foreign_keys(self):
        with self.store.db:
            self.transaction()
            self.sources.add_geometry(self.analysis)
            self.sources.add_geometry(self.geometry)
            self.sources.add_snapshot(self.snapshot)
            with self.assertRaises(sqlite3.IntegrityError):
                self.sources.add_page(self.page)
            with self.assertRaises(sqlite3.IntegrityError):
                self.sources.add_feature(self.feature)
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute("INSERT INTO source_features VALUES (?,?,?,?,?)",
                    (self.snapshot.snapshot_id, "missing", "unknown", 1, "{}"))
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute("INSERT INTO source_revision_bindings VALUES (?,?,?)",
                    ("unknown", "A02/v1", self.snapshot.snapshot_id))

    def test_lineage_roundtrip_and_missing_parent(self):
        derived = replace(self.geometry, geometry_ref="test/derived/1", role=GeometryRole.DERIVED_GEOMETRY,
                          parent_geometry_refs=(self.geometry.geometry_ref,), derivation_json='{"operation":"test-copy"}')
        with self.store.db:
            self.transaction()
            with self.assertRaises(ValueError):
                self.sources.add_geometry(derived)
            self.sources.add_geometry(self.geometry)
            self.sources.add_geometry(derived)
        self.assertEqual(self.sources.geometry(derived.geometry_ref), derived)
        self.assertEqual(self.store.db.execute("SELECT * FROM geometry_lineage").fetchall(),
                         [(derived.geometry_ref, self.geometry.geometry_ref)])

    def test_transaction_required_and_no_implicit_commit(self):
        with self.assertRaises(RuntimeError):
            self.sources.add_raw(self.raw)
        self.transaction()
        self.sources.add_raw(self.raw)
        self.store.db.rollback()
        with self.assertRaises(ValueError):
            self.sources.raw(self.raw.raw_response_hash)

    def test_failure_rolls_back_sources_task_revision_and_audit_together(self):
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with self.store.db:
                self.transaction()
                self.archive()
                self.task()
                self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
                self.store.event("source-test", "A02", "test-only")
                raise RuntimeError("injected")
        for table in (*SOURCE_TABLES, "tasks", "audit"):
            self.assertEqual(self.store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)

    def test_binding_requires_existing_a02_revision(self):
        with self.store.db:
            self.transaction()
            self.archive()
            self.task()
            with self.assertRaises(ValueError):
                self.sources._bind_revision(RevisionBinding("source-test", "A02/v2", self.snapshot.snapshot_id))
            self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
            self.assertNotIn("coordinates", self.store.db.execute("SELECT body FROM tasks").fetchone()[0])

    def test_incomplete_cannot_bind_and_historical_decision_unchanged(self):
        for status in ("STAGING", "VALIDATING", "FAILED", "INCOMPLETE"):
            with self.subTest(status=status):
                self.transaction()
                self.snapshot = replace(self.snapshot, status=status)
                self.archive()
                self.task()
                with self.assertRaises(ValueError):
                    self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
                self.store.db.rollback()
        self.snapshot = replace(self.snapshot, status="COMPLETE")
        for status in ("APPROVED", "REJECTED"):
            self.transaction()
            self.archive()
            self.task(status)
            before = self.store.get("source-test")
            with self.assertRaises(ValueError):
                self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
            self.assertEqual(self.store.get("source-test"), before)
            self.store.db.rollback()

    def test_missing_manifest_members_cannot_bind(self):
        with self.store.db:
            self.transaction()
            self.sources.add_geometry(self.analysis)
            self.sources.add_snapshot(self.snapshot)
            self.task()
            with self.assertRaises(ValueError):
                self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))

    def test_project_geometry_cannot_be_used_as_analysis_scope(self):
        with self.store.db:
            self.transaction()
            self.sources.add_geometry(replace(self.analysis, role=GeometryRole.PROJECT_GEOMETRY))
            with self.assertRaises(ValueError):
                self.sources.add_snapshot(self.snapshot)

    def test_analysis_geometry_cannot_be_source_feature(self):
        with self.store.db:
            self.transaction()
            self.archive()
            with self.assertRaises(ValueError):
                self.sources.add_feature(replace(self.feature, geometry_ref=self.analysis.geometry_ref))

    def test_immutable_sql_guards_including_replace_all_tables(self):
        with self.store.db:
            self.transaction()
            self.archive()
            self.task()
            self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
            derived = replace(self.geometry, geometry_ref="derived", role=GeometryRole.DERIVED_GEOMETRY,
                              parent_geometry_refs=(self.geometry.geometry_ref,), derivation_json='{"operation":"test"}')
            self.sources.add_geometry(derived)
            for table in SOURCE_TABLES:
                with self.subTest(table=table):
                    column = self.store.db.execute(f"PRAGMA table_info({table})").fetchone()[1]
                    for statement in (f"UPDATE {table} SET {column}={column}",
                                      f"DELETE FROM {table}",
                                      f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
                        with self.assertRaises(sqlite3.IntegrityError):
                            self.store.db.execute(statement)

    def test_second_connection_enforces_foreign_keys(self):
        other = Store(self.temp.name)
        try:
            self.assertEqual(other.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with other.db:
                with self.assertRaises(sqlite3.IntegrityError):
                    other.db.execute("INSERT INTO source_pages VALUES ('missing',1,'missing','{}')")
        finally:
            other.close()

    def test_deep_immutability_and_required_provenance(self):
        with self.assertRaises(FrozenInstanceError):
            self.geometry.geometry_ref = "changed"
        with self.assertRaises(ValueError):
            replace(self.geometry, parent_geometry_refs=[])
        for change in ({"provenance_json":"{}"}, {"geometry_structural_hash":"bad"}):
            with self.assertRaises(ValueError):
                replace(self.geometry, **change)
        with self.assertRaises(ValueError):
            replace(self.feature, source_id="")
        with self.assertRaises(ValueError):
            FetchExtent((10, 10, 0, 0), self.crs.crs, "scope")

    def test_consistency_is_independent_from_completeness(self):
        self.assertEqual(self.snapshot.status, ImportStatus.COMPLETE)
        self.assertEqual(self.snapshot.point_in_time_consistency, PointInTimeConsistency.NOT_GUARANTEED)
        self.assertEqual(FIXTURE["source_status"], "TESTDATA")
        self.assertFalse(hasattr(self.analysis, "design_authority"))
        self.assertFalse(hasattr(self.sources, "promote"))



    def test_bound_snapshot_membership_cannot_be_extended(self):
        with self.store.db:
            self.transaction()
            self.archive()
            self.task()
            self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
            with self.assertRaises(ValueError):
                self.sources.add_feature(replace(self.feature, source_id="extra"))
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute("INSERT INTO source_features VALUES (?,?,?,?,?)",
                    (self.snapshot.snapshot_id, "extra", self.geometry.geometry_ref, 1, "{}"))
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute("INSERT INTO source_pages VALUES (?,?,?,?)",
                    (self.snapshot.snapshot_id, 2, self.raw.raw_response_hash, "{}"))

    def test_alternate_unique_identity_cannot_replace_history(self):
        with self.store.db:
            self.transaction()
            self.archive()
            self.task()
            self.sources._bind_revision(RevisionBinding("source-test", "A02/v1", self.snapshot.snapshot_id))
            self.store.db.execute("PRAGMA recursive_triggers=OFF")
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute("""INSERT OR REPLACE INTO source_snapshots
                    SELECT 'other-id',provider,dataset,collection,snapshot_manifest_hash,
                    canonicalization_version,status,analysis_geometry_ref,body FROM source_snapshots""")
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.db.execute("""INSERT OR REPLACE INTO source_revision_bindings
                    SELECT task_id,'A02/v2',snapshot_id FROM source_revision_bindings""")


class SourceMigrationTests(unittest.TestCase):
    def test_legacy_rows_preserved_exactly_and_migration_repeatable(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("CREATE TABLE audit (seq INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            legacy = '{"status": "APPROVED", "human_approval":{"actor":"test-human"}}'
            db.execute("INSERT INTO tasks VALUES ('historical', ?)", (legacy,))
            db.execute("INSERT INTO audit VALUES (17, ?)", ('{"historical": true}',))
            db.commit()
            migrate(db)
            migrate(db)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(db.execute("SELECT * FROM tasks").fetchall(), [("historical", legacy)])
            self.assertEqual(db.execute("SELECT * FROM audit").fetchall(), [(17, '{"historical": true}')])
        finally:
            db.close()

    def test_future_schema_fails_closed(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute("PRAGMA user_version=99")
            with self.assertRaises(ValueError):
                migrate(db)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
        finally:
            db.close()

    def test_failed_migration_rolls_back_schema_and_version(self):
        db = sqlite3.connect(":memory:")
        try:
            with patch("bvc_ai.infrastructure.source_schema.SCHEMA",
                       ("CREATE TABLE partial (id TEXT)", "INVALID SQL")):
                with self.assertRaises(sqlite3.OperationalError):
                    migrate(db)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
            migrate(db)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        finally:
            db.close()
