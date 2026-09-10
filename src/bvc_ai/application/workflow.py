import json
from dataclasses import asdict
from bvc_ai.domain.models import Task, AgentOutput, Review, AgentProfile, now
from bvc_ai.domain.policies import check_transition, validate_output, check_review_ready

class AgentSession:
    """Agent-facing API: no approval service, storage handle or arbitrary tools."""
    def __init__(self, transition, agent_id):
        self.agent_id = agent_id
        self.__transition = transition
    def transition(self, task_id, target):
        return self.__transition(task_id, target, self.agent_id)

class Workflow:
    def __init__(self, store, provider, project):
        self.store, self.provider, self.project = store, provider, project
        self.profiles = {p["agent_id"]: AgentProfile(**p) for p in json.loads((project / "config/agents.json").read_text(encoding="utf-8"))}

    def agent(self, agent_id):
        if not self.profiles[agent_id].active:
            raise PermissionError("Rol is nog niet actief")
        return AgentSession(self.transition, agent_id)

    def transition(self, task_id, target, actor="A01"):
        try:
            with self.store.db:
                self.store.db.execute("BEGIN IMMEDIATE")
                task = self.store.get(task_id)
                check_transition(task["status"], target)
                if actor != "A01":
                    raise PermissionError("Alleen A01 coördineert statusovergangen")
                if target in {"SPECIALIST_COMPLETE", "REVIEW_PENDING"} and not task["output_refs"]:
                    raise ValueError("Specialist-output ontbreekt")
                if target in {"REVIEWED", "AWAITING_HUMAN_APPROVAL"}:
                    check_review_ready(task)
                previous = task["status"]
                task.update(status=target, updated_at=now())
                self.store._save(task)
                self.store.event(task_id, actor, "status_changed", previous=previous, target=target)
        except (ValueError, PermissionError) as exc:
            with self.store.db:
                self.store.event(task_id, actor, "blocked_transition", target=target, reason=str(exc))
            raise

    def _event(self, task_id, actor, action, **details):
        with self.store.db:
            self.store.event(task_id, actor, action, **details)

    def _assign(self, task_id, actor):
        with self.store.db:
            task = self.store.get(task_id)
            task.update(assigned_agent=actor, updated_at=now())
            self.store._save(task)
            self.store.event(task_id, "A01", "task_assigned", assigned_agent=actor)

    def demo(self):
        brief = json.loads((self.project / "examples/gis-001.json").read_text(encoding="utf-8"))
        task_id = "GIS-001"
        if any(t["task_id"] == task_id for t in self.store.list()):
            raise ValueError("GIS-001 bestaat al; gebruik resume voor READY of een aparte --data map")
        with self.store.db:
            task = asdict(Task(task_id, "Basisgeometrie Mastenbroekweg", brief["description"], input_refs=("examples/gis-001.json",)))
            task.update(outputs=[], reviews=[])
            self.store._save(task)
            self.store.event(task_id, "A01", "task_created", source_status="TESTDATA")
        self.transition(task_id, "READY")
        return self.run(task_id, brief)

    def run(self, task_id, brief=None):
        task = self.store.get(task_id)
        if task["status"] != "READY":
            raise ValueError("Hervatten kan uitsluitend vanaf READY")
        if brief is None:
            brief = json.loads((self.project / "examples/gis-001.json").read_text(encoding="utf-8"))
        self._event(task_id, "A01", "agent_started")
        try:
            self._assign(task_id, "A02")
            self.transition(task_id, "RUNNING")
            self._event(task_id, "A02", "agent_started")
            points = task["reviews"][-1]["findings"] if task["reviews"] else []
            payload = self.provider.inventory(brief, points)
            output = AgentOutput(task_id, "A02", now(), task["input_refs"],
                [s["source_id"] for s in payload["sources"]], "fixture", "TESTDATA", 0.0,
                len(task["outputs"]) + 1, None, "PENDING", None,
                ["Uitsluitend synthetische TESTDATA; geen bewijs over de echte locatie."],
                "source_inventory", payload)
            validate_output(output)
            with self.store.db:
                task = self.store.get(task_id)
                task["outputs"].append(asdict(output))
                task["output_refs"].append(f"{task_id}/A02/v{output.output_version}")
                task["review_status"] = "PENDING"
                self.store._save(task)
                for source in payload["sources"]:
                    self.store.event(task_id, "A02", "source_registered", source=source)
                self.store.event(task_id, "A02", "agent_completed", output_version=output.output_version)
            self.transition(task_id, "SPECIALIST_COMPLETE")
            self.transition(task_id, "REVIEW_PENDING")
            self._assign(task_id, "A07")
            self._event(task_id, "A01", "review_requested")
            self._event(task_id, "A07", "agent_started")
            result = self.provider.review(asdict(output))
            if result["verdict"] not in {"SUFFICIENT", "INSUFFICIENT"}:
                raise ValueError("Reviewer mag geen definitief besluit geven")
            if result["verdict"] == "INSUFFICIENT" and not result["findings"]:
                raise ValueError("Onvoldoende review vereist concrete herstelpunten")
            review = asdict(Review(task_id, "A07", now(), output.output_version, result["verdict"], result["findings"]))
            with self.store.db:
                task = self.store.get(task_id)
                task["reviews"].append(review)
                task["review_status"] = review["verdict"]
                # Versioned output remains unchanged; review links to exact version.
                self.store._save(task)
                self.store.event(task_id, "A07", "review_completed", review=review)
                self.store.event(task_id, "A07", "agent_completed")
            self._assign(task_id, "A01")
            if review["verdict"] == "INSUFFICIENT":
                self._event(task_id, "A01", "revision_requested", findings=review["findings"])
                self.transition(task_id, "READY")
            else:
                self.transition(task_id, "REVIEWED")
                self.transition(task_id, "AWAITING_HUMAN_APPROVAL")
                self._event(task_id, "A01", "approval_requested")
            self._event(task_id, "A01", "agent_completed")
            return self.store.get(task_id)
        except Exception as exc:
            self._event(task_id, "runtime", "error", reason=str(exc))
            if self.store.get(task_id)["status"] in {"RUNNING", "SPECIALIST_COMPLETE", "REVIEW_PENDING", "REVIEWED"}:
                self.transition(task_id, "FAILED")
            raise
