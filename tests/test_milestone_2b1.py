"""Regression coverage for F1-F4; all writes stay in isolated project storage."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import test_design_workflow as legacy
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.domain.design import decision_variants
from bvc_ai.domain.design_verification import resolution_evidence

spec = importlib.util.spec_from_file_location("validation_2b", legacy.ROOT / "scripts/validate_milestone_2b.py")
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class RepairTests(unittest.TestCase):
    setUp = legacy.DesignTests.setUp
    tearDown = legacy.DesignTests.tearDown
    step = legacy.DesignTests.step
    through = legacy.DesignTests.through
    service = legacy.DesignTests.service
    mutate = legacy.DesignTests.mutate
    fails_unchanged = legacy.DesignTests.fails_unchanged

    def conflicting_integration(self):
        self.mutate(lambda s,p,c: p["objects"][0].update(geometry_ref="design/compact") if s == "A03_INTEGRATION" else None)

    def test_f1_original_geometry_keeps_specialist_findings_open(self):
        self.conflicting_integration()
        task = self.workflow.run()
        self.assertEqual(task["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertTrue(all(f["status"] == "OPEN" for f in task["findings"] if f["created_by"] in {"A04", "A05"}))
        self.assertFalse(any(h["target"] == "RESOLVED" for h in task["finding_history"]))
        self.assertIsNone(task["human_approval"])

    def test_f1_textual_resolution_of_conflicting_geometry_is_rejected(self):
        self.conflicting_integration()
        self.through("A03_INTEGRATION")
        def force(s,p,c):
            p["review"]["resolved_findings"] = [f["finding_id"] for f in c["findings"] if f["created_by"] == s[:3]]
        self.mutate(force)
        for step in ("A04_REVIEW", "A05_REVIEW"):
            with self.subTest(step=step):
                self.fails_unchanged(lambda: self.step(step))

    def test_f1_unknown_finding_is_not_automatically_resolved(self):
        self.mutate(lambda s,p,c: p["findings"][0].update(description="Onbekende landschappelijke conditie") if s == "A04" else None)
        task = self.workflow.run()
        self.assertEqual(next(f for f in task["findings"] if f["created_by"] == "A04")["status"], "OPEN")

    def test_f1_resolution_has_geometry_and_revision_evidence(self):
        task = self.workflow.run()
        histories = [h for h in task["finding_history"] if h["target"] == "RESOLVED"]
        self.assertEqual(len(histories), 2)
        for h in histories:
            proof = h["verification"]
            self.assertEqual(proof["integration_revision_id"], "A03_INTEGRATION/v1")
            self.assertTrue(proof["checked_objects"])
            self.assertTrue(proof["specialist_object_ids"])
            self.assertTrue(all(o["bounds"][2] <= 240 and o["bounds"][1] >= 50 for o in proof["checked_objects"]))
            event = next(e for e in self.store.events() if e["action"] == "finding_resolved" and e["details"]["change"]["finding_id"] == h["finding_id"])
            self.assertEqual(event["details"]["change"]["verification"], proof)
        finding = next(f for f in task["findings"] if f["created_by"] == "A04")
        updated = self.step("A03_INTEGRATION")
        self.assertIsNone(resolution_evidence(updated, finding, "A03_INTEGRATION/v1"))

    def test_f1_missing_required_specialist_object_keeps_finding_open(self):
        self.mutate(lambda s,p,c: p["objects"][0].update(geometry_ref="design/compact") if s == "A04" else None)
        task = self.workflow.run()
        self.assertEqual(next(f for f in task["findings"] if f["created_by"] == "A04")["status"], "OPEN")

    def test_f2_failure_after_state_write_rolls_back_and_audits_all_human_routes(self):
        self.workflow.run()
        fid = self.store.get(legacy.TID)["findings"][0]["finding_id"]
        original = self.store._save
        def fail(task):
            original(task)
            raise RuntimeError("injected secret detail")
        for decision in ("APPROVED", "REJECTED", "ACCEPTED_RISK"):
            with self.subTest(decision=decision):
                before = self.store.get(legacy.TID)
                count = len(self.store.events())
                with patch.object(self.store, "_save", side_effect=fail), self.assertRaises(RuntimeError):
                    self.service().decide(legacy.TID, "Testmens", decision, "Test", finding_id=fid if decision == "ACCEPTED_RISK" else None, idempotency_key=decision)
                self.assertEqual(self.store.get(legacy.TID), before)
                self.assertEqual(len(self.store.events()), count + 1)
                event = self.store.events()[-1]
                self.assertEqual(event["action"], "human_decision_failed")
                self.assertNotIn("secret", json.dumps(event))

    def test_f2_failure_after_success_audit_rolls_back_success_and_decision(self):
        self.workflow.run()
        before = self.store.get(legacy.TID)
        count = len(self.store.events())
        original = self.store.event
        def fail(tid, actor, action, **details):
            original(tid, actor, action, **details)
            if action == "human_approved":
                raise RuntimeError("after success audit SQL")
        with patch.object(self.store, "event", side_effect=fail), self.assertRaises(RuntimeError):
            self.service().decide(legacy.TID, "Testmens", "APPROVED", idempotency_key="retry")
        self.assertEqual(self.store.get(legacy.TID), before)
        self.assertEqual(len(self.store.events()), count + 1)
        self.assertEqual(self.store.events()[-1]["action"], "human_decision_failed")
        self.service().decide(legacy.TID, "Testmens", "APPROVED", idempotency_key="retry")
        self.assertEqual(sum(e["action"] == "human_approved" for e in self.store.events()), 1)

    def test_f2_unavailable_fault_audit_never_commits_decision(self):
        self.workflow.run()
        before = self.store.get(legacy.TID)
        events = self.store.events()
        original = self.store._save
        def fail(task):
            original(task)
            raise RuntimeError("save failure")
        with patch.object(self.store, "_save", side_effect=fail), patch.object(self.store, "event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
                self.service().decide(legacy.TID, "Testmens", "APPROVED")
        self.assertEqual(self.store.get(legacy.TID), before)
        self.assertEqual(self.store.events(), events)

    def test_f3_package_refs_resolve_and_integration_has_hypothesis_lineage(self):
        task = self.workflow.run()
        objects = {o["object_id"]: o for o in task["objects"]}
        compact, linear = task["decision_requests"][-1]["variants"]
        for variant in (compact, linear):
            self.assertTrue(set(variant["object_ids"]) <= objects.keys())
            self.assertEqual(variant["hypothesis_revision_id"], "A03_HYPOTHESIS/v1")
        self.assertEqual(compact["integration_revision_id"], "A03_INTEGRATION/v1")
        self.assertTrue(compact["integrated_object_ids"])
        self.assertIsNone(linear["integration_revision_id"])
        for oid in compact["integrated_object_ids"]:
            self.assertEqual(objects[oid]["properties"]["hypothesis_variant_id"], compact["variant_id"])
            self.assertEqual(objects[oid]["properties"]["hypothesis_object_ids"], compact["object_ids"])

    def test_f3_new_hypothesis_rejects_old_variant_reference(self):
        task = self.through("A05")
        old_variant = decision_variants(task)[0]["variant_id"]
        self.step("A03_HYPOTHESIS")
        self.step("A04")
        self.step("A05")
        self.mutate(lambda s,p,c: p.update(hypothesis_variant_id=old_variant))
        self.fails_unchanged(lambda: self.step("A03_INTEGRATION"))

    def test_f3_limit_package_uses_registered_references(self):
        self.mutate(lambda s,p,c: p["review"].update(verdict="REVISE", resolved_findings=[]) if s == "A04_REVIEW" else None)
        task = self.workflow.run()
        self.assertEqual(task["status"], "REQUIRES_HUMAN_DECISION")
        registered = {o["object_id"] for o in task["objects"]}
        for v in task["decision_requests"][-1]["variants"]:
            self.assertTrue(set(v["object_ids"]) <= registered)
            self.assertTrue(set(v["integrated_object_ids"]) <= registered)

    def test_f4_old_success_log_cannot_mask_current_test_failure(self):
        root = Path(self.temp.name)
        (root / "docs").mkdir()
        old = root / "docs/milestone-2b-tests.txt"
        old.write_text("Ran 999 tests in 1.0s\nOK\n", encoding="utf-8")
        failed = subprocess.CompletedProcess([], 1, "", "Ran 1 tests in 0.1s\nFAILED\n")
        with patch.object(validation, "code_identity", return_value={"source_sha256":"current"}), patch.object(validation.subprocess, "run", return_value=failed) as run:
            with self.assertRaises(RuntimeError):
                validation.run_current_tests(root)
            self.assertIn("test.ps1", run.call_args.args[0][-1])
        self.assertIn("999", old.read_text())

    def test_f4_success_binds_actual_run_and_code_identity(self):
        current = {"git_head":"commit", "source_sha256":"digest", "source_files":{"a.py":"hash"}}
        passed = subprocess.CompletedProcess([], 0, "", "Ran 7 tests in 0.2s\nOK\n")
        with patch.object(validation, "code_identity", return_value=current), patch.object(validation.subprocess, "run", return_value=passed):
            log, evidence = validation.run_current_tests(Path(self.temp.name))
        self.assertEqual(evidence["test_count"], 7)
        self.assertEqual(evidence["code"], current)
        self.assertEqual(evidence["exit_code"], 0)
        self.assertTrue(evidence["started_at"] <= evidence["finished_at"])
        self.assertIn("Ran 7", log)

    def test_f4_changes_during_test_run_invalidate_evidence(self):
        passed = subprocess.CompletedProcess([], 0, "", "Ran 7 tests in 0.2s\nOK\n")
        with patch.object(validation, "code_identity", side_effect=[{"source_sha256":"before"}, {"source_sha256":"after"}]), patch.object(validation.subprocess, "run", return_value=passed):
            with self.assertRaisesRegex(RuntimeError, "Code gewijzigd"):
                validation.run_current_tests(Path(self.temp.name))

    def test_f4_empty_or_nonzero_success_output_is_not_evidence(self):
        for code, log in ((0,""), (1,"Ran 7 tests in 0.2s\nOK\n"), (0,"Ran 0 tests in 0.1s\nOK\n")):
            with self.subTest(code=code, log=log):
                result = subprocess.CompletedProcess([], code, log, "")
                with patch.object(validation, "code_identity", return_value={}), patch.object(validation.subprocess, "run", return_value=result):
                    with self.assertRaises(RuntimeError):
                        validation.run_current_tests(Path(self.temp.name))
