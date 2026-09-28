"""Project records separate from task/source state; same Store transaction."""
import json
from bvc_ai.domain.projects import Project
from bvc_ai.domain.models import now


class ProjectRepository:
    def __init__(self, store):
        self.store = store
        if store.db.in_transaction:
            raise RuntimeError("Project repository requires an independent transaction")
        with store.db:
            store.db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            store.db.execute("CREATE TABLE IF NOT EXISTS project_audit (seq INTEGER PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL)")
            for operation in ("UPDATE", "DELETE"):
                store.db.execute(f"""CREATE TRIGGER IF NOT EXISTS project_audit_no_{operation.lower()}
                    BEFORE {operation} ON project_audit
                    BEGIN SELECT RAISE(ABORT, 'Immutable project audit'); END""")
            store.db.execute("""CREATE TRIGGER IF NOT EXISTS project_audit_no_replace
                BEFORE INSERT ON project_audit WHEN EXISTS (SELECT 1 FROM project_audit WHERE seq=NEW.seq)
                BEGIN SELECT RAISE(ABORT, 'Immutable project audit'); END""")

    def get(self, project_id):
        row = self.store.db.execute("SELECT body FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise ValueError(f"Onbekend project: {project_id}")
        project = Project(**json.loads(row[0]))
        if project.project_id != project_id:
            raise ValueError("Project identity mismatch")
        return project

    def _insert(self, project):
        self.store.db.execute("INSERT INTO projects VALUES (?, ?)",
                              (project.project_id, json.dumps(project.to_dict(), ensure_ascii=False)))

    def _update(self, project):
        cursor = self.store.db.execute("UPDATE projects SET body=? WHERE id=?",
                                       (json.dumps(project.to_dict(), ensure_ascii=False), project.project_id))
        if cursor.rowcount != 1:
            raise ValueError("Project ontbreekt")

    def event(self, project_id, actor, action, **details):
        event = dict(project_id=project_id, actor=actor, action=action, timestamp=now(), details=details)
        self.store.db.execute("INSERT INTO project_audit(project_id, body) VALUES (?, ?)",
                              (project_id, json.dumps(event, ensure_ascii=False)))

    def events(self, project_id):
        return [json.loads(row[0]) for row in self.store.db.execute(
            "SELECT body FROM project_audit WHERE project_id=? ORDER BY seq", (project_id,))]
