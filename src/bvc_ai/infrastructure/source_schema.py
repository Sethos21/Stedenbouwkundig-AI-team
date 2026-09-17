"""Versioned, additive SQLite migrations. No domain state or audit rewrites."""
SCHEMA_VERSION = 1

SOURCE_TABLES = {
    "geometry_records": "geometry_ref",
    "geometry_lineage": "geometry_ref,parent_geometry_ref",
    "raw_responses": "raw_response_hash",
    "source_snapshots": "snapshot_id",
    "source_pages": "snapshot_id,page_number",
    "source_features": "snapshot_id,source_id",
    "source_revision_bindings": "task_id,revision_id",
}

SCHEMA = (
    """CREATE TABLE geometry_records (
        geometry_ref TEXT PRIMARY KEY NOT NULL,
        geometry_structural_hash TEXT NOT NULL,
        canonicalization_version TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('SOURCE_GEOMETRY','DERIVED_GEOMETRY',
          'PROJECT_GEOMETRY','ANALYSIS_GEOMETRY','TESTCASE_ONLY_ANALYSIS_GEOMETRY','POLICY_GEOMETRY')),
        body TEXT NOT NULL
    )""",
    """CREATE TABLE geometry_lineage (
        geometry_ref TEXT NOT NULL REFERENCES geometry_records(geometry_ref),
        parent_geometry_ref TEXT NOT NULL REFERENCES geometry_records(geometry_ref),
        PRIMARY KEY(geometry_ref,parent_geometry_ref),
        CHECK(geometry_ref != parent_geometry_ref)
    )""",
    """CREATE TABLE raw_responses (
        raw_response_hash TEXT PRIMARY KEY NOT NULL,
        body BLOB NOT NULL CHECK(typeof(body) = 'blob')
    )""",
    """CREATE TABLE source_snapshots (
        snapshot_id TEXT PRIMARY KEY NOT NULL,
        provider TEXT NOT NULL, dataset TEXT NOT NULL, collection TEXT NOT NULL,
        snapshot_manifest_hash TEXT NOT NULL, canonicalization_version TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('STAGING','VALIDATING','COMPLETE','FAILED','INCOMPLETE')),
        analysis_geometry_ref TEXT NOT NULL REFERENCES geometry_records(geometry_ref),
        body TEXT NOT NULL,
        UNIQUE(provider,dataset,collection,canonicalization_version,snapshot_manifest_hash)
    )""",
    """CREATE TABLE source_pages (
        snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
        page_number INTEGER NOT NULL CHECK(page_number > 0),
        raw_response_hash TEXT NOT NULL REFERENCES raw_responses(raw_response_hash),
        body TEXT NOT NULL,
        PRIMARY KEY(snapshot_id,page_number)
    )""",
    """CREATE TABLE source_features (
        snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
        source_id TEXT NOT NULL,
        geometry_ref TEXT NOT NULL REFERENCES geometry_records(geometry_ref),
        page_number INTEGER NOT NULL,
        body TEXT NOT NULL,
        PRIMARY KEY(snapshot_id,source_id),
        FOREIGN KEY(snapshot_id,page_number) REFERENCES source_pages(snapshot_id,page_number)
    )""",
    """CREATE TABLE source_revision_bindings (
        task_id TEXT NOT NULL REFERENCES tasks(id),
        revision_id TEXT NOT NULL,
        snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
        PRIMARY KEY(task_id,revision_id),
        UNIQUE(task_id,snapshot_id)
    )""",
    "CREATE INDEX source_features_geometry ON source_features(geometry_ref)",
    "CREATE INDEX source_pages_raw ON source_pages(raw_response_hash)",
    "CREATE INDEX geometry_lineage_parent ON geometry_lineage(parent_geometry_ref)",
    "CREATE INDEX source_bindings_snapshot ON source_revision_bindings(snapshot_id)",
)


def migrate(db):
    if db.in_transaction:
        raise RuntimeError("Migration requires a separate startup transaction")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA recursive_triggers=ON")
    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("Foreign keys required")
    with db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            raise ValueError(f"Unsupported schema version: {version}")
        if version == SCHEMA_VERSION:
            return
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, body TEXT NOT NULL)")
        for statement in SCHEMA:
            db.execute(statement)
        for table, keys in SOURCE_TABLES.items():
            for operation in ("UPDATE", "DELETE"):
                db.execute(f"""CREATE TRIGGER {table}_no_{operation.lower()}
                    BEFORE {operation} ON {table}
                    BEGIN SELECT RAISE(ABORT, 'Immutable source record'); END""")
            # Explicitly reject REPLACE too, even on a connection with recursive
            # triggers disabled. Identical insertion is handled by SourceStore.
            predicate = " AND ".join(f"{key}=NEW.{key}" for key in keys.split(","))
            db.execute(f"""CREATE TRIGGER {table}_no_replace
                BEFORE INSERT ON {table}
                WHEN EXISTS(SELECT 1 FROM {table} WHERE {predicate})
                BEGIN SELECT RAISE(ABORT, 'Existing source identity'); END""")

        # Unique alternate identities must also resist INSERT OR REPLACE.
        db.execute("""CREATE TRIGGER snapshots_no_manifest_replace
            BEFORE INSERT ON source_snapshots
            WHEN EXISTS(SELECT 1 FROM source_snapshots WHERE provider=NEW.provider
              AND dataset=NEW.dataset AND collection=NEW.collection
              AND canonicalization_version=NEW.canonicalization_version
              AND snapshot_manifest_hash=NEW.snapshot_manifest_hash)
            BEGIN SELECT RAISE(ABORT, 'Existing snapshot manifest'); END""")
        db.execute("""CREATE TRIGGER bindings_no_snapshot_replace
            BEFORE INSERT ON source_revision_bindings
            WHEN EXISTS(SELECT 1 FROM source_revision_bindings
              WHERE task_id=NEW.task_id AND snapshot_id=NEW.snapshot_id)
            BEGIN SELECT RAISE(ABORT, 'Existing revision binding'); END""")
        for table in ("source_pages", "source_features"):
            db.execute(f"""CREATE TRIGGER {table}_sealed
                BEFORE INSERT ON {table}
                WHEN EXISTS(SELECT 1 FROM source_revision_bindings
                  WHERE snapshot_id=NEW.snapshot_id)
                BEGIN SELECT RAISE(ABORT, 'Revision-bound snapshot is sealed'); END""")

        db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
