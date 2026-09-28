from dataclasses import asdict
from bvc_ai.domain.models import Approval, now
from bvc_ai.domain.policies import check_transition, check_review_ready

# This capability is never supplied to providers or AgentSession.
_HUMAN_CAPABILITY = object()

class HumanApprovalService:
    def __init__(self, store, *, capability=None):
        if capability is not _HUMAN_CAPABILITY:
            raise PermissionError("Menselijke ingang vereist")
        self.store = store

    def release_project(self, project_id, human_actor, reason):
        """Explicit trusted CLI human decision; never called by project workflows."""
        from dataclasses import replace
        from bvc_ai.application.projects import project_operation
        from bvc_ai.infrastructure.project_repository import ProjectRepository
        from bvc_ai.domain.projects import ProjectStatus, check_project_transition, text
        repository = ProjectRepository(self.store)
        target = ProjectStatus.RELEASED
        with project_operation(repository, project_id, human_actor, target):
            actor = text(human_actor, "human_actor")
            if actor.upper() in {f"A{i:02}" for i in range(1, 9)}:
                raise PermissionError("Agentidentiteiten mogen onderzoek niet vrijgeven")
            reason = text(reason, "reason")
            project = repository.get(project_id)
            check_project_transition(project.status, target, human=True)
            updated = replace(project, status=target, updated_at=now())
            repository._update(updated)
            repository.event(project_id, actor, "project_human_released",
                             previous=project.status, target=target, reason=reason,
                             origin="TRUSTED_HUMAN_CLI", decision_at=updated.updated_at)
        return updated

    def decide(self, task_id, human_actor, decision, notes="", *, finding_id=None, idempotency_key=None):
        actor = "unknown"
        try:
            actor = human_actor.strip()
            if not actor or actor.upper() in {f"A{i:02}" for i in range(1, 9)}:
                raise PermissionError("Een menselijke actor is verplicht; agentidentiteiten zijn verboden")
            if decision not in {"APPROVED", "REJECTED", "ACCEPTED_RISK"}:
                raise ValueError("Ongeldig besluit")
            with self.store.db:
                self.store.db.execute("BEGIN IMMEDIATE")
                task = self.store.get(task_id)
                if task.get("workflow") == "ONTWERPLUS_2B":
                    return self._decide_design(task, actor, decision, notes, finding_id, idempotency_key)
                if decision == "ACCEPTED_RISK":
                    raise ValueError("Risicoacceptatie vereist Ontwerplus-context")
                check_transition(task["status"], decision, human_service=True)
                check_review_ready(task)
                approval = asdict(Approval(task_id, actor, now(), decision, notes))
                task.update(status=decision, updated_at=approval["timestamp"], human_approval=approval)
                self.store._save(task)
                self.store.event(task_id, actor, "human_approved" if decision == "APPROVED" else "human_rejected", approval=approval)
        except Exception as exc:
            # The decision transaction has exited and rolled back before this
            # independent audit transaction. Never retry or save the decision.
            with self.store.db:
                self.store.db.execute("BEGIN IMMEDIATE")
                if isinstance(exc, (ValueError, PermissionError)):
                    self.store.event(task_id, actor, "blocked_transition", reason=str(exc), target=decision)
                else:
                    self.store.event(task_id, actor, "human_decision_failed", target=decision,
                                     finding_id=finding_id, idempotency_key=idempotency_key,
                                     error_type=type(exc).__name__,
                                     reason="Menselijke transactie mislukt; geen besluit opgeslagen")
            raise

    def _decide_design(self, task, actor, decision, notes, finding_id, key):
        from bvc_ai.domain.design import HumanDecision, check_design_approval
        request = dict(actor=actor, decision=decision, notes=notes, finding_id=finding_id)
        records = task.setdefault("human_idempotency", {})
        if key is not None:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Ongeldige menselijke idempotency key")
            if key in records:
                if records[key] != request:
                    raise ValueError("Menselijke idempotency key heeft andere invoer")
                return
        if task["status"] in {"APPROVED", "REJECTED"}:
            raise ValueError("Bestaand menselijk besluit blijft ongewijzigd")
        item = asdict(HumanDecision(task["task_id"], actor, now(), decision, notes,
                                   dict(task["active_revisions"]), finding_id))
        if decision == "ACCEPTED_RISK":
            if not isinstance(notes, str) or not notes.strip():
                raise ValueError("Risicoacceptatie vereist expliciete motivering")
            finding = next((f for f in task["findings"] if f["finding_id"] == finding_id), None)
            if finding is None or finding["status"] in {"RESOLVED", "ACCEPTED_RISK"}:
                raise ValueError("Open finding ontbreekt")
            change = dict(finding_id=finding_id, previous=finding["status"], target="ACCEPTED_RISK", human_decision=item)
            task["finding_history"].append(change)
            finding["status"] = "ACCEPTED_RISK"
            package = task["active_revisions"].pop("A01_PACKAGE", None)
            if package:
                task["stale_revisions"].append(package)
                task["status"] = "READY"
            action = "human_risk_accepted"
        else:
            if finding_id is not None:
                raise ValueError("Finding-id hoort uitsluitend bij risicoacceptatie")
            if task["status"] != "AWAITING_HUMAN_APPROVAL":
                raise ValueError("Actueel beslispakket moet wachten op menselijke goedkeuring")
            check_transition(task["status"], decision, human_service=True)
            check_design_approval(task)
            task.update(status=decision, human_approval=item)
            action = "human_approved" if decision == "APPROVED" else "human_rejected"
        task["human_decisions"].append(item)
        task["updated_at"] = item["timestamp"]
        if key is not None:
            records[key] = request
        self.store._save(task)
        self.store.event(task["task_id"], actor, action, human_decision=item)
