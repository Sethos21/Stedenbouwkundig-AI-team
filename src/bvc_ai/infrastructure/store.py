import json
import sqlite3
from pathlib import Path
from dataclasses import asdict
from bvc_ai.domain.models import AuditEvent, now
from bvc_ai.infrastructure.source_schema import migrate

class Store:
    """Single-host storage. State and canonical audit commit atomically."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "state.sqlite3", timeout=10)
        self.db.execute("PRAGMA journal_mode=DELETE")
        try:
            migrate(self.db)
        except Exception:
            self.db.close()
            raise

    def get(self, task_id):
        row = self.db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Onbekende taak: {task_id}")
        return json.loads(row[0])

    def list(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM tasks ORDER BY id")]

    def _save(self, task):
        self.db.execute("INSERT INTO tasks VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                        (task["task_id"], json.dumps(task, ensure_ascii=False)))

    def event(self, task_id, actor, action, **details):
        event = asdict(AuditEvent(task_id, actor, action, now(), details))
        self.db.execute("INSERT INTO audit(body) VALUES (?)", (json.dumps(event, ensure_ascii=False),))

    def events(self, task_id=None):
        events = [json.loads(r[0]) for r in self.db.execute("SELECT body FROM audit ORDER BY seq")]
        return [e for e in events if task_id is None or e["task_id"] == task_id]

    def export_audit(self):
        # Regenerable readable projection; SQLite is the transactional source.
        path = self.directory / "audit.jsonl"
        path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in self.events()), encoding="utf-8")

    def close(self):
        self.db.close()
