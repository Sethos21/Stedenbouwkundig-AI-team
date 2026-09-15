"""Transactional, context-scoped eight-agent Ontwerplus orchestration."""
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from bvc_ai.domain.models import now
from bvc_ai.domain.design import (
    STEPS, REVIEW_STEPS, ROLES, AgentTask, DesignObject, Finding, ReviewResult,
    Handoff, DecisionRequest, RevisionDependency, current_output, open_findings,
    check_critical, check_design_approval, decision_variants,
)
from bvc_ai.domain.design_validation import validate_proposal
from bvc_ai.domain.design_verification import resolution_evidence


class DesignSession:
    def __init__(self, execute, actor):
        self.__execute, self.agent_id = execute, actor

    def step(self, task_id, step, idempotency_key, expected_inputs=None):
        return self.__execute(task_id, step, idempotency_key, actor=self.agent_id,
                              expected_inputs=expected_inputs)


class DesignWorkflow:
    def __init__(self, store, provider, project):
        self.store, self.provider, self.project = store, provider, project

    def agent(self, actor):
        if actor not in ROLES:
            raise PermissionError("Geen Ontwerplus-agent")
        return DesignSession(self.step, actor)

    def create(self):
        fixture = json.loads((self.project / "examples/design-test-001.json").read_text(encoding="utf-8-sig"))
        tid = fixture["project_id"]
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            if any(t["task_id"] == tid for t in self.store.list()):
                task = self.store.get(tid)
                if task.get("workflow") != "ONTWERPLUS_2B" or task["geometry_registry"] != fixture["geometry_registry"]:
                    raise ValueError("Bestaande taak verschilt van fixture")
                return task
            task = dict(task_id=tid, project_id=tid, workflow="ONTWERPLUS_2B", status="READY",
                        source_status="TESTDATA", human_approval=None, iteration_count=0,
                        active_revisions={}, outputs=[], objects=[], findings=[], reviews=[],
                        stale_reviews=[], stale_revisions=[], dependencies=[], handoffs=[],
                        decision_requests=[], human_decisions=[], finding_history=[],
                        idempotency={}, geometry_registry=fixture["geometry_registry"], updated_at=now())
            self.store._save(task)
            self.store.event(tid, "A01", "design_created", source_status="TESTDATA", fixture="examples/design-test-001.json")
        return task

    def inputs(self, task, step):
        if step not in STEPS:
            raise PermissionError("Geen toegestane Ontwerplus-stap")
        inputs = {}
        for dependency in STEPS[step][1]:
            output = current_output(task, dependency)
            inputs.update(output["input_revisions"])
            inputs[dependency] = output["revision_id"]
        return inputs

    def _gate(self, task, step, actor, expected_inputs):
        if task.get("workflow") != "ONTWERPLUS_2B":
            raise PermissionError("Verkeerde workflowcontext")
        if step not in STEPS or actor != STEPS[step][0]:
            raise PermissionError("Agent heeft geen capability voor deze stap")
        if task["status"] in {"APPROVED", "REJECTED", "REQUIRES_HUMAN_DECISION"}:
            raise PermissionError("Menselijk besluit vereist of besluit reeds definitief")
        inputs = self.inputs(task, step)
        if step in REVIEW_STEPS and step in task["active_revisions"]:
            raise ValueError("Review voor deze integratie bestaat al; nieuwe integratierevisie vereist")
        if expected_inputs is not None and expected_inputs != inputs:
            raise ValueError("Aangeboden inputrevisies zijn stale of mismatched")
        if step not in {"A01_START", "A02", "A06", "A08_GATE"}:
            check_critical(task)
        if step in {"A07", "A01_PACKAGE"}:
            for dep in STEPS[step][1]:
                if current_output(task, dep)["output"]["review"]["verdict"] not in {"PASS", "PASS_WITH_FINDINGS"}:
                    raise ValueError("Reviewgate vereist PASS of PASS_WITH_FINDINGS")
        return inputs

    def step(self, task_id, step, idempotency_key, *, actor=None, expected_inputs=None):
        actor = actor or STEPS.get(step, ("unknown", ()))[0]
        phase = "gate"
        try:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise ValueError("Idempotency key verplicht")
            request = {"step": step, "actor": actor, "expected_inputs": expected_inputs}
            fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            before = self.store.get(task_id)
            record = before.get("idempotency", {}).get(idempotency_key)
            if record:
                if record["fingerprint"] != fingerprint:
                    raise ValueError("Idempotency key is eerder voor andere invoer gebruikt")
                return before
            inputs = self._gate(before, step, actor, expected_inputs)
            # Escalation is an explicit committed control transition, not a failed design mutation.
            limit = step == "A03_INTEGRATION" and before["iteration_count"] >= 3
            context = self._proposal_context(before, step)
            phase = "provider"
            proposal = None if limit else self.provider.design_step(step, deepcopy(context), deepcopy(inputs))
            if not limit:
                phase = "validation"
                validate_proposal(step, proposal, context, inputs)
            phase = "transaction"
            with self.store.db:
                self.store.db.execute("BEGIN IMMEDIATE")
                task = self.store.get(task_id)
                record = task["idempotency"].get(idempotency_key)
                if record:
                    if record["fingerprint"] != fingerprint:
                        raise ValueError("Conflicterende idempotency key")
                    return task
                if task != before:
                    raise ValueError("State gewijzigd tijdens provideruitvoering; stap opnieuw aanbieden")
                self._gate(task, step, actor, expected_inputs)
                if limit:
                    task["status"] = "REQUIRES_HUMAN_DECISION"
                    task["decision_requests"].append(asdict(DecisionRequest(
                        "iteration-limit/4", dict(task["active_revisions"]),
                        "Drie automatische ontwerpcycli verbruikt. Beoordeel open herstelpunten en bepaal een nieuw ontwerpbesluit; er volgt geen automatische vierde integratie.",
                        decision_variants(task),
                        [r for r in task["reviews"] if r["review_id"] not in task["stale_reviews"]],
                        deepcopy(open_findings(task)),
                        [f for f in open_findings(task) if f["classification"] == "ENVIRONMENTAL_RISK"],
                        [c for o in task["outputs"] if o["revision_id"] in task["active_revisions"].values() for c in o["output"]["conditions"] if c["classification"] in {"UNCERTAIN", "RESEARCH_REQUIRED"}],
                        [o["revision_id"] for o in task["outputs"]])))
                    task["idempotency"][idempotency_key] = {"fingerprint": fingerprint, "result": "REQUIRES_HUMAN_DECISION"}
                    self.store.event(task_id, "A01", "iteration_limit", attempted_cycle=4, iteration_count=3,
                                     question="Drie ontwerpcycli verbruikt. Welk menselijk vervolg is gewenst?")
                else:
                    self._apply(task, step, actor, inputs, proposal, idempotency_key, fingerprint)
                task["updated_at"] = now()
                self.store._save(task)
            return self.store.get(task_id)
        except Exception as exc:
            # The preceding context rolls back ALL domain and success-audit writes first.
            with self.store.db:
                self.store.db.execute("BEGIN IMMEDIATE")
                self.store.event(task_id, actor, "step_failed", step=step, idempotency_key=idempotency_key,
                                 error_type=type(exc).__name__, failure_phase=phase, expected_inputs=expected_inputs,
                                 reason=str(exc) if phase in {"gate", "validation"} else "Provider- of transactiefout; geen stapmutaties opgeslagen")
            raise

    def _proposal_context(self, task, step):
        context = deepcopy(task)
        old = task["active_revisions"].get(step)
        affected = {o["revision_id"] for o in task["outputs"] if old is not None and (o["revision_id"] == old or old in o["input_revisions"].values())}
        for finding in context["findings"]:
            resolutions = [h for h in context["finding_history"] if h["finding_id"] == finding["finding_id"] and h.get("target") == "RESOLVED"]
            if finding["status"] == "RESOLVED" and resolutions and resolutions[-1]["review_id"] in affected:
                finding["status"] = "OPEN"
        return context

    def _invalidate(self, task, step):
        old = task["active_revisions"].get(step)
        if old is None:
            return
        affected = {old}
        # Every output holds the transitive input closure.
        for output in task["outputs"]:
            if old in output["input_revisions"].values():
                affected.add(output["revision_id"])
        for revision in sorted(affected):
            if revision not in task["stale_revisions"]:
                task["stale_revisions"].append(revision)
        task["active_revisions"] = {s: r for s, r in task["active_revisions"].items() if r not in affected}
        for review in task["reviews"]:
            if review["review_id"] in affected and review["review_id"] not in task["stale_reviews"]:
                task["stale_reviews"].append(review["review_id"])
        for finding in task["findings"]:
            resolutions = [h for h in task["finding_history"] if h["finding_id"] == finding["finding_id"] and h.get("target") == "RESOLVED"]
            if finding["status"] == "RESOLVED" and resolutions and resolutions[-1]["review_id"] in affected:
                finding["status"] = "OPEN"
                change = dict(finding_id=finding["finding_id"], previous="RESOLVED", target="OPEN", stale_review=resolutions[-1]["review_id"])
                task["finding_history"].append(change)
                self.store.event(task["task_id"], "A01", "finding_reopened", change=change)
        self.store.event(task["task_id"], "A01", "dependencies_invalidated", upstream_revision=old, stale_revisions=sorted(affected))

    def _apply(self, task, step, actor, inputs, proposal, key, fingerprint):
        revision = f"{step}/v{1 + sum(o['step'] == step for o in task['outputs'])}"
        self._invalidate(task, step)
        output = asdict(AgentTask(task["task_id"], actor, step, revision, inputs, deepcopy(proposal), now()))
        task["outputs"].append(output)
        task["active_revisions"][step] = revision
        for dep, upstream in inputs.items():
            task["dependencies"].append(asdict(RevisionDependency(revision, dep, upstream)))
        for dep in STEPS[step][1]:
            task["handoffs"].append(asdict(Handoff(dep, step, revision, inputs)))
        new_findings = []
        for index, item in enumerate(proposal["findings"], 1):
            fid = f"{revision}/F{index}"
            finding = asdict(Finding(fid, actor, revision, inputs, item["severity"], "OPEN",
                                    item["description"], item["spatial_effect"], item["classification"]))
            task["findings"].append(finding)
            new_findings.append(fid)
            self.store.event(task["task_id"], actor, "finding_created", finding=finding)
        for obj in proposal["objects"]:
            properties = deepcopy(obj["properties"])
            if step == "A03_INTEGRATION":
                variant = next(v for v in decision_variants(task) if v["variant_id"] == proposal["hypothesis_variant_id"])
                properties.update(hypothesis_variant_id=variant["variant_id"],
                                  hypothesis_revision_id=variant["hypothesis_revision_id"],
                                  hypothesis_object_ids=variant["object_ids"])
            if obj["object_type"] == "DEVELOPMENT_FIELD":
                coordinates = task["geometry_registry"][obj["geometry_ref"]]["coordinates"]
                area = abs(sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(coordinates, coordinates[1:] + coordinates[:1]))) / 2
                properties.update(area_m2=area, capacity=int(area / 10000 * properties["density_per_ha"]),
                                  capacity_basis="synthetic polygon area * assumed density; derived, not input")
            entity = asdict(DesignObject(f"{revision}/{obj['local_id']}", task["project_id"], obj["object_type"],
                              obj["geometry_ref"], obj["geometry_status"], revision, actor, obj["source_basis"],
                              properties, [] if actor == "A02" else ["A04", "A05", "A08", "A07"], new_findings))
            task["objects"].append(entity)
            self.store.event(task["task_id"], actor, "design_object_registered", object=entity)
        if step == "A03_INTEGRATION":
            task["iteration_count"] += 1
        if step in REVIEW_STEPS:
            item = proposal["review"]
            review = asdict(ReviewResult(revision, actor, item["revision_id"], inputs,
                                        item["verdict"], new_findings, item["rationale"]))
            task["reviews"].append(review)
            if item["verdict"] in {"REVISE", "BLOCKED"}:
                for finding in task["findings"]:
                    if finding["created_by"] == actor and finding["status"] in {"OPEN", "UNRESOLVED", "BLOCKED"} and finding["finding_id"] not in item["resolved_findings"]:
                        target = "UNRESOLVED" if item["verdict"] == "REVISE" else "BLOCKED"
                        change = dict(finding_id=finding["finding_id"], previous=finding["status"], target=target, review_id=revision)
                        finding["status"] = target
                        task["finding_history"].append(change)
                        self.store.event(task["task_id"], actor, "finding_reviewed", change=change)
            for fid in item["resolved_findings"]:
                finding = next(f for f in task["findings"] if f["finding_id"] == fid)
                change = dict(finding_id=fid, previous=finding["status"], target="RESOLVED", review_id=revision, actor=actor,
                              verification=resolution_evidence(task, finding, inputs["A03_INTEGRATION"]))
                task["finding_history"].append(change)
                finding["status"] = "RESOLVED"
                self.store.event(task["task_id"], actor, "finding_resolved", change=change)
        active_verdicts = {r["verdict"] for r in task["reviews"] if r["review_id"] in task["active_revisions"].values()}
        task["status"] = "BLOCKED" if "BLOCKED" in active_verdicts else "A03_INTEGRATION" if "REVISE" in active_verdicts else "READY"
        if step == "A01_PACKAGE":
            conditions = [c for o in task["outputs"] if o["revision_id"] in task["active_revisions"].values() for c in o["output"]["conditions"]]
            request = asdict(DecisionRequest(revision, inputs,
                "Welke TESTDATA-variant en welke resterende risico's en onderzoeksvragen wilt u expliciet beoordelen? Geen uitvoerings- of onderzoeksgoedkeuring is verleend.",
                decision_variants(task), [r for r in task["reviews"] if r["review_id"] not in task["stale_reviews"]],
                deepcopy(open_findings(task)), [f for f in open_findings(task) if f["classification"] == "ENVIRONMENTAL_RISK"],
                [c for c in conditions if c["classification"] in {"UNCERTAIN", "RESEARCH_REQUIRED"}],
                [o["revision_id"] for o in task["outputs"]]))
            task["decision_requests"].append(request)
            check_design_approval(task)
            task["status"] = "AWAITING_HUMAN_APPROVAL"
        task["idempotency"][key] = {"fingerprint": fingerprint, "result": revision, "input_revisions": inputs}
        self.store.event(task["task_id"], actor, "step_completed", step=step, revision_id=revision,
                         input_revisions=inputs, idempotency_key=key, state=task["status"], source_status="TESTDATA")

    def run(self, task_id="DESIGN-TEST-001"):
        task = self.store.get(task_id)
        if task["status"] == "A03_INTEGRATION":
            return self._revise(task_id)
        for step in STEPS:
            if task["status"] in {"AWAITING_HUMAN_APPROVAL", "REQUIRES_HUMAN_DECISION", "APPROVED", "REJECTED", "BLOCKED"}:
                return task
            try:
                current_output(task, step)
                continue
            except ValueError:
                pass
            task = self.step(task_id, step, f"run/{step}/{len(task['outputs']) + 1}")
            if step in REVIEW_STEPS and task["status"] == "A03_INTEGRATION":
                return self._revise(task_id)
        return task

    def _revise(self, task_id):
        # At most three accepted integrations, plus one explicit escalation attempt.
        while True:
            task = self.store.get(task_id)
            task = self.step(task_id, "A03_INTEGRATION", f"run/integration/{task['iteration_count'] + 1}")
            if task["status"] == "REQUIRES_HUMAN_DECISION":
                return task
            revised = False
            for step in ("A04_REVIEW", "A05_REVIEW", "A08_REVIEW", "A07"):
                task = self.step(task_id, step, f"run/{step}/cycle{task['iteration_count']}")
                if task["status"] == "BLOCKED":
                    return task
                if task["status"] == "A03_INTEGRATION":
                    revised = True
                    break
            if not revised:
                return self.step(task_id, "A01_PACKAGE", f"run/package/cycle{task['iteration_count']}")

    def report(self, task_id):
        task = self.store.get(task_id)
        return {"project_id": task["project_id"], "task_id": task_id, "workflowstate": task["status"],
                "source_status": "TESTDATA", "active_revisions": task["active_revisions"],
                "output_per_agent": {a: [o for o in task["outputs"] if o["agent_id"] == a] for a in sorted(ROLES)},
                "open_findings_per_severity": {s: [f for f in open_findings(task) if f["severity"] == s] for s in ("INFO", "MINOR", "MAJOR", "CRITICAL")},
                "stale_reviews": task["stale_reviews"], "iteration_count": task["iteration_count"],
                "a07_verdict": next((r["verdict"] for r in reversed(task["reviews"]) if r["reviewer"] == "A07" and r["review_id"] not in task["stale_reviews"]), None),
                "human_approval": task["human_approval"], "audit_event_count": len(self.store.events(task_id)), "state": task}
