"""Project shell only: no agents, source import, Research Gate or design execution."""
from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4
from bvc_ai.domain.models import now
from bvc_ai.domain.projects import Project, check_project_transition, text
from bvc_ai.infrastructure.project_repository import ProjectRepository


@contextmanager
def project_operation(repository, project_id, actor, target):
    db = repository.store.db
    if db.in_transaction:
        raise RuntimeError("Project operation requires its own transaction")
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            yield
    except Exception as exc:
        with db:
            db.execute("BEGIN IMMEDIATE")
            repository.event(project_id, actor, "project_transition_blocked" if isinstance(
                exc, (ValueError, PermissionError)) else "project_operation_failed",
                target=target, error_type=type(exc).__name__)
        raise


class ProjectService:
    def __init__(self, store):
        self.repository = ProjectRepository(store)

    def create(self, name, *, research_type=None, address=None, location=None):
        project_id = "PRJ-" + uuid4().hex
        with project_operation(self.repository, project_id, "project_service", "PROJECT_AANGEMAAKT"):
            timestamp = now()
            project = Project(project_id, text(name, "name"), timestamp, timestamp,
                              research_type=research_type, address=address, location=location)
            self.repository._insert(project)
            self.repository.event(project_id, "project_service", "project_created",
                                  previous=None, target=project.status, origin="USER_INPUT",
                                  project=project.to_dict())
        return project

    def load(self, project_id):
        return self.repository.get(project_id)

    def transition(self, project_id, target, *, reason):
        # No caller-supplied actor or human flag: providers cannot impersonate a human.
        with project_operation(self.repository, project_id, "project_service", target):
            project = self.load(project_id)
            check_project_transition(project.status, target)
            reason = text(reason, "reason")
            updated = replace(project, status=target, updated_at=now())
            self.repository._update(updated)
            self.repository.event(project_id, "project_service", "project_status_changed",
                                  previous=project.status, target=target, reason=reason,
                                  origin="PROJECT_SERVICE")
        return updated
