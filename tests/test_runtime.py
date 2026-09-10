import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from bvc_ai.domain.models import AgentOutput, SourceReference, Task
from bvc_ai.domain.policies import TRANSITIONS, K00Policy, check_transition, validate_output
from bvc_ai.infrastructure.store import Store
from bvc_ai.application.workflow import Workflow
from bvc_ai.application.approval import HumanApprovalService, _HUMAN_CAPABILITY
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.adapters.repositories import MockGISAdapter, MockDocumentRepository

ROOT = Path(__file__).resolve().parents[1]

class RecordingProvider(DeterministicTestProvider):
    def __init__(self):
        self.calls = []
    def inventory(self, brief, revision_points):
        self.calls.append(("A02", list(revision_points)))
        return super().inventory(brief, revision_points)
    def review(self, output):
        self.calls.append(("A07", output["output_version"]))
        return super().review(output)

class RevisionProvider(RecordingProvider):
    def review(self, output):
        self.calls.append(("A07", output["output_version"]))
        if output["output_version"] == 1:
            return {"verdict": "INSUFFICIENT", "findings": ["Beschrijf de ontbrekende CRS-validatie explicieter."]}
        return super().review(output)

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        testroot = ROOT / ".tools/test-runs"
        testroot.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=testroot)
        self.store = Store(self.temp.name)
        self.provider = RecordingProvider()
        self.workflow = Workflow(self.store, self.provider, ROOT)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def demo(self):
        return self.workflow.demo()

    def service(self):
        # Test-only simulation of trusted CLI composition; never supplied to an agent.
        return HumanApprovalService(self.store, capability=_HUMAN_CAPABILITY)

    def cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "bvc_ai.py"), "--data", self.temp.name, *args],
                              cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")

    def test_a01_calls_a02_then_a07(self):
        self.demo()
        self.assertEqual([c[0] for c in self.provider.calls], ["A02", "A07"])
        assignments = [e["details"]["assigned_agent"] for e in self.store.events() if e["action"] == "task_assigned"]
        self.assertEqual(assignments, ["A02", "A07", "A01"])

    def test_provenance_is_complete_and_testdata(self):
        task = self.demo()
        output = task["outputs"][0]
        for key in ("task_id", "agent_id", "timestamp", "input_refs", "source_refs", "source_type",
                    "source_status", "confidence", "output_version", "reviewer", "review_status",
                    "human_approval", "notes"):
            self.assertIn(key, output)
        self.assertEqual(output["task_id"], "GIS-001")
        self.assertEqual(output["source_status"], "TESTDATA")
        self.assertEqual(len(output["source_refs"]), 4)
        self.assertIsNone(output["human_approval"])
        self.assertTrue(all(s["source_status"] == "TESTDATA" for s in output["payload"]["sources"]))

    def test_review_sufficient_and_bound_to_version(self):
        task = self.demo()
        self.assertEqual(task["reviews"][-1]["reviewer"], "A07")
        self.assertEqual(task["reviews"][-1]["verdict"], "SUFFICIENT")
        self.assertEqual(task["reviews"][-1]["output_version"], task["outputs"][-1]["output_version"])

    def test_demo_stops_before_human_approval(self):
        task = self.demo()
        self.assertEqual(task["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertIsNone(task["human_approval"])
        self.assertFalse(any(e["action"] == "human_approved" for e in self.store.events()))

    def test_all_seven_agents_cannot_approve_or_reject(self):
        self.demo()
        for actor in self.workflow.profiles:
            for decision in ("APPROVED", "REJECTED"):
                with self.subTest(actor=actor, decision=decision):
                    with self.assertRaises(PermissionError):
                        self.workflow.transition("GIS-001", decision, actor)
        self.assertEqual(self.store.get("GIS-001")["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertEqual(len([e for e in self.store.events() if e["action"] == "blocked_transition"]), 14)

    def test_agent_session_has_no_human_service(self):
        self.demo()
        session = self.workflow.agent("A01")
        self.assertFalse(hasattr(session, "approve"))
        self.assertFalse(hasattr(session, "store"))
        with self.assertRaises(PermissionError):
            session.transition("GIS-001", "APPROVED")

    def test_running_to_approved_is_denied_even_to_human_route(self):
        with self.assertRaises(ValueError):
            check_transition("RUNNING", "APPROVED", human_service=True)
        with self.assertRaises(PermissionError):
            check_transition("RUNNING", "APPROVED")

    def test_all_status_pairs_obey_explicit_graph(self):
        for current in TRANSITIONS:
            for target in TRANSITIONS:
                with self.subTest(current=current, target=target):
                    if target in TRANSITIONS[current]:
                        check_transition(current, target, human_service=True)
                    else:
                        with self.assertRaises(ValueError):
                            check_transition(current, target, human_service=True)

    def test_service_cannot_be_constructed_by_agent(self):
        with self.assertRaises(PermissionError):
            HumanApprovalService(self.store)
        with self.assertRaises(PermissionError):
            HumanApprovalService(self.store, capability=object())

    def test_human_service_approval_is_audited(self):
        self.demo()
        self.service().decide("GIS-001", "Testmens", "APPROVED", "Alleen testbesluit")
        task = self.store.get("GIS-001")
        self.assertEqual(task["status"], "APPROVED")
        self.assertEqual(task["human_approval"]["human_actor"], "Testmens")
        events = [e for e in self.store.events() if e["action"] == "human_approved"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["details"]["approval"], task["human_approval"])

    def test_agent_identity_rejected_by_human_service(self):
        self.demo()
        for actor in ["", "  ", *self.workflow.profiles, " a02 "]:
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionError):
                    self.service().decide("GIS-001", actor, "APPROVED")

    def test_duplicate_approval_preserves_first_decision(self):
        self.demo()
        self.service().decide("GIS-001", "Testmens", "APPROVED")
        original = self.store.get("GIS-001")["human_approval"]
        with self.assertRaises(ValueError):
            self.service().decide("GIS-001", "Ander", "APPROVED")
        self.assertEqual(self.store.get("GIS-001")["human_approval"], original)

    def test_unknown_task_and_invalid_decision_are_rejected(self):
        self.demo()
        with self.assertRaises(ValueError):
            self.service().decide("UNKNOWN", "Testmens", "APPROVED")
        with self.assertRaises(ValueError):
            self.service().decide("GIS-001", "Testmens", "ACCEPTED")
        self.assertEqual(self.store.get("GIS-001")["status"], "AWAITING_HUMAN_APPROVAL")

    def test_testdata_cannot_be_reclassified_as_verified(self):
        with self.assertRaises(ValueError):
            SourceReference("id", "BGT", "fixture", "VERIFIED_SOURCE", "fixture", "none")
        output = AgentOutput(**self.demo()["outputs"][0])
        with self.assertRaises(ValueError):
            validate_output(replace(output, source_status="VERIFIED_SOURCE"))

    def test_verified_source_inside_fixture_output_is_denied(self):
        output = AgentOutput(**self.demo()["outputs"][0])
        output.payload["sources"][0].update(source_type="official", source_status="VERIFIED_SOURCE")
        with self.assertRaises(ValueError):
            validate_output(output)

    def test_a02_cannot_register_design(self):
        output = AgentOutput(**self.demo()["outputs"][0])
        with self.assertRaises(PermissionError):
            validate_output(replace(output, kind="design"))
        output.payload["new_roads"] = []
        with self.assertRaises(ValueError):
            validate_output(output)

    def test_agent_cannot_embed_approval(self):
        output = AgentOutput(**self.demo()["outputs"][0])
        with self.assertRaises(PermissionError):
            validate_output(replace(output, human_approval={"decision": "APPROVED"}))

    def test_k00_cannot_be_written_regenerated_or_modified(self):
        for operation in ("write", "regenerate", "modify", "delete"):
            with self.subTest(operation=operation):
                with self.assertRaises(PermissionError):
                    K00Policy.authorize(" k00 ", operation)
        adapter = MockGISAdapter()
        before = adapter.read("K00")
        with self.assertRaises(PermissionError):
            adapter.register_layer("K00", {"geometry": "changed"})
        copy = adapter.read("K00")
        copy["geometry"] = "changed"
        self.assertEqual(adapter.read("K00"), before)

    def test_derived_layers_allowed_but_design_not_existing(self):
        adapter = MockGISAdapter()
        adapter.register_layer("D01", {"reference": "K00"})
        self.assertEqual(adapter.read("D01")["reference"], "K00")
        with self.assertRaises(PermissionError):
            adapter.register_layer("D02", {}, origin="design", classification="existing")

    def test_revision_points_reach_a02_and_versions_are_retained(self):
        provider = RevisionProvider()
        workflow = Workflow(self.store, provider, ROOT)
        first = workflow.demo()
        self.assertEqual(first["status"], "READY")
        self.assertTrue(first["reviews"][0]["findings"])
        second = workflow.run("GIS-001")
        self.assertEqual(second["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertEqual([o["output_version"] for o in second["outputs"]], [1, 2])
        self.assertEqual(second["outputs"][0], first["outputs"][0])
        self.assertEqual([c for c in provider.calls if c[0] == "A02"][1][1], first["reviews"][0]["findings"])
        self.assertTrue(any(e["action"] == "revision_requested" for e in self.store.events()))

    def test_provider_failure_is_failed_and_audited(self):
        class Broken(DeterministicTestProvider):
            def inventory(self, brief, revision_points):
                raise RuntimeError("Gesimuleerde providerfout")
        with self.assertRaises(RuntimeError):
            Workflow(self.store, Broken(), ROOT).demo()
        self.assertEqual(self.store.get("GIS-001")["status"], "FAILED")
        self.assertTrue(any(e["action"] == "error" for e in self.store.events()))

    def test_reviewer_cannot_return_approved(self):
        class Malicious(DeterministicTestProvider):
            def review(self, output):
                return {"verdict": "APPROVED", "findings": []}
        with self.assertRaises(ValueError):
            Workflow(self.store, Malicious(), ROOT).demo()
        self.assertEqual(self.store.get("GIS-001")["status"], "FAILED")
        self.assertIsNone(self.store.get("GIS-001")["human_approval"])

    def test_inactive_agents_cannot_run(self):
        for actor in ("A03", "A04", "A05", "A06"):
            with self.assertRaises(PermissionError):
                self.workflow.agent(actor)

    def test_cli_manual_approval_in_isolated_test_store(self):
        result = self.cli("demo", "gis-001")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "AWAITING_HUMAN_APPROVAL")
        result = self.cli("approve", "GIS-001", "--actor", "Testmens", "--reason", "Geautomatiseerde CLI-test, geen echt besluit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "APPROVED")
        repeat = self.cli("approve", "GIS-001", "--actor", "Testmens")
        self.assertEqual(repeat.returncode, 2)

    def test_cli_rejection(self):
        self.demo()
        result = self.cli("reject", "GIS-001", "--actor", "Testmens", "--reason", "Test: meer onderbouwing nodig")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "REJECTED")
        self.assertTrue(any(e["action"] == "human_rejected" for e in self.store.events()))

    def test_cli_requires_actor(self):
        self.demo()
        result = self.cli("approve", "GIS-001")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.store.get("GIS-001")["status"], "AWAITING_HUMAN_APPROVAL")

    def test_cli_read_commands_and_audit_jsonl(self):
        self.demo()
        for command in (("tasks",), ("status", "GIS-001"), ("review", "GIS-001"), ("audit", "GIS-001")):
            result = self.cli(*command)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout))
        exported = [json.loads(line) for line in (Path(self.temp.name) / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(exported, self.store.events())

    def test_duplicate_demo_does_not_overwrite(self):
        original = self.demo()
        with self.assertRaises(ValueError):
            self.demo()
        self.assertEqual(self.store.get("GIS-001"), original)

    def test_persistence_across_repository_instances(self):
        task = self.demo()
        other = Store(self.temp.name)
        try:
            self.assertEqual(other.get("GIS-001"), task)
        finally:
            other.close()

    def test_document_mock_does_not_expose_mutable_storage(self):
        repo = MockDocumentRepository()
        original = {"title": "TESTDATA"}
        repo.write("doc", original)
        original["title"] = "changed"
        self.assertEqual(repo.read("doc")["title"], "TESTDATA")

    def test_missing_output_blocks_review_transition(self):
        from dataclasses import asdict
        with self.store.db:
            task = asdict(Task("EMPTY", "Empty", "TESTDATA", status="RUNNING"))
            self.store._save(task)
        with self.assertRaises(ValueError):
            self.workflow.transition("EMPTY", "SPECIALIST_COMPLETE")
        self.assertEqual(self.store.get("EMPTY")["status"], "RUNNING")

    def test_stale_review_blocks_human_approval(self):
        task = self.demo()
        task["reviews"][-1]["output_version"] = 0
        with self.store.db:
            self.store._save(task)
        with self.assertRaises(ValueError):
            self.service().decide("GIS-001", "Testmens", "APPROVED")
        self.assertIsNone(self.store.get("GIS-001")["human_approval"])

    def test_missing_review_blocks_human_approval(self):
        task = self.demo()
        task["reviews"] = []
        with self.store.db:
            self.store._save(task)
        with self.assertRaises(ValueError):
            self.service().decide("GIS-001", "Testmens", "APPROVED")

    def test_cli_prevents_data_outside_project(self):
        result = self.cli("--data", str(ROOT.parent / "outside-bvc"), "tasks")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--data moet binnen de projectmap liggen", result.stderr)

    def test_source_reference_mismatch_is_denied(self):
        output = AgentOutput(**self.demo()["outputs"][0])
        with self.assertRaises(ValueError):
            validate_output(replace(output, source_refs=["nonexistent"]))
