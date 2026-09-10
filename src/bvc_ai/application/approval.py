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

    def decide(self, task_id, human_actor, decision, notes=""):
        actor = human_actor.strip()
        try:
            if not actor or actor.upper() in {f"A{i:02}" for i in range(1, 8)}:
                raise PermissionError("Een menselijke actor is verplicht; agentidentiteiten zijn verboden")
            if decision not in {"APPROVED", "REJECTED"}:
                raise ValueError("Ongeldig besluit")
            with self.store.db:
                self.store.db.execute("BEGIN IMMEDIATE")
                task = self.store.get(task_id)
                check_transition(task["status"], decision, human_service=True)
                check_review_ready(task)
                approval = asdict(Approval(task_id, actor, now(), decision, notes))
                task.update(status=decision, updated_at=approval["timestamp"], human_approval=approval)
                self.store._save(task)
                self.store.event(task_id, actor, "human_approved" if decision == "APPROVED" else "human_rejected", approval=approval)
        except (ValueError, PermissionError) as exc:
            with self.store.db:
                self.store.event(task_id, actor, "blocked_transition", reason=str(exc), target=decision)
            raise
