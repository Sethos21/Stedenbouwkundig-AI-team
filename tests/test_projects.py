import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bvc_ai.application.approval import HumanApprovalService, _HUMAN_CAPABILITY
from bvc_ai.application.projects import ProjectService
from bvc_ai.domain.projects import ProjectStatus as S, TRANSITIONS
from bvc_ai.infrastructure.store import Store

ROOT = Path(__file__).resolve().parents[1]


class ProjectTests(unittest.TestCase):
    def setUp(self):
        testroot = ROOT / ".tools/test-runs"
        testroot.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=testroot)
        self.store = Store(self.temp.name)
        self.service = ProjectService(self.store)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self):
        return self.service.create("Project test")

    def ready(self):
        project = self.create()
        for target in (S.INTAKE, S.RESEARCH, S.READY):
            project = self.service.transition(project.project_id, target, reason="Test transition")
        return project

    def human(self):
        # Trusted CLI simulation only in isolated temporary storage.
        return HumanApprovalService(self.store, capability=_HUMAN_CAPABILITY)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "bvc_ai.py"), "--data", self.temp.name, *args],
                              cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                              capture_output=True, text=True, encoding="utf-8")

    def test_create_load_unique_identity_and_optional_fields(self):
        project = self.create()
        other = self.create()
        self.assertNotEqual(project.project_id, other.project_id)
        self.assertEqual(project, self.service.load(project.project_id))
        self.assertEqual(project.status, S.CREATED)
        self.assertEqual(project.created_at, project.updated_at)
        for field in ("research_type", "address", "location"):
            self.assertIsNone(getattr(project, field))
        populated = self.service.create("Locatie", research_type="Haalbaarheid", address="Testadres",
                                        location="Door gebruiker beschreven locatie")
        self.assertEqual(self.service.load(populated.project_id), populated)
        self.assertEqual(self.store.list(), [])

    def test_persistence_status_and_audit_after_reopen(self):
        project = self.ready()
        events = self.service.repository.events(project.project_id)
        self.store.close()
        self.store = Store(self.temp.name)
        self.service = ProjectService(self.store)
        self.assertEqual(self.service.load(project.project_id), project)
        self.assertEqual(self.service.repository.events(project.project_id), events)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0]["details"]["origin"], "USER_INPUT")
        self.assertEqual(events[-1]["details"]["previous"], S.RESEARCH)
        self.assertEqual(events[-1]["details"]["target"], S.READY)
        self.assertTrue(all(e["project_id"] == project.project_id and e["timestamp"] for e in events))

    def test_valid_transitions_and_return_for_research(self):
        project = self.ready()
        revised = self.service.transition(project.project_id, S.RESEARCH, reason="Aanvullen")
        self.assertEqual(revised.status, S.RESEARCH)
        self.assertEqual(revised.created_at, project.created_at)
        self.assertGreaterEqual(revised.updated_at, project.updated_at)
        self.assertEqual(revised.project_id, project.project_id)

    def test_every_invalid_transition_is_audited_and_preserves_state(self):
        for current in S:
            for target in S:
                if target in TRANSITIONS[current] and target != S.RELEASED:
                    continue
                project = self.create()
                # Set up each state through genuine public transitions/human route.
                for step in (S.INTAKE, S.RESEARCH, S.READY, S.RELEASED):
                    if project.status == current:
                        break
                    project = (self.human().release_project(project.project_id, "Testmens", "Testbesluit")
                               if step == S.RELEASED else self.service.transition(
                                   project.project_id, step, reason="Test setup"))
                with self.subTest(current=current, target=target):
                    with self.assertRaises((ValueError, PermissionError)):
                        self.service.transition(project.project_id, target, reason="Invalid")
                    self.assertEqual(self.service.load(project.project_id), project)
                    self.assertEqual(self.service.repository.events(project.project_id)[-1]["action"],
                                     "project_transition_blocked")

    def test_human_capability_and_agent_names(self):
        project = self.ready()
        for capability in (None, object(), "human", "A01"):
            with self.assertRaises(PermissionError):
                HumanApprovalService(self.store, capability=capability)
        for actor in ("", " ", *(f"A{i:02}" for i in range(1, 9)), " a01 "):
            with self.assertRaises((PermissionError, ValueError)):
                self.human().release_project(project.project_id, actor, "Test")
        self.assertEqual(self.service.load(project.project_id), project)
        with self.assertRaises(TypeError):
            self.service.transition(project.project_id, S.RELEASED, reason="Fake", actor="Human")
        with self.assertRaises(TypeError):
            self.service.transition(project.project_id, S.RELEASED, reason="Fake", human=True)

    def test_human_release_requires_ready_and_reason_and_is_terminal(self):
        early = self.create()
        with self.assertRaises(ValueError):
            self.human().release_project(early.project_id, "Testmens", "Te vroeg")
        project = self.ready()
        with self.assertRaises(ValueError):
            self.human().release_project(project.project_id, "Testmens", " ")
        released = self.human().release_project(project.project_id, "Testmens", "Expliciet testbesluit")
        self.assertEqual(released.status, S.RELEASED)
        audit = self.service.repository.events(project.project_id)[-1]
        self.assertEqual(audit["actor"], "Testmens")
        self.assertEqual(audit["action"], "project_human_released")
        self.assertEqual(audit["details"]["origin"], "TRUSTED_HUMAN_CLI")
        self.assertEqual(audit["details"]["decision_at"], released.updated_at)
        with self.assertRaises(ValueError):
            self.human().release_project(project.project_id, "Testmens", "Dubbel")
        self.assertEqual(self.service.load(project.project_id), released)

    def test_audit_failure_rolls_back_status_and_human_decision(self):
        project = self.ready()
        self.store.db.execute("""CREATE TRIGGER fail_project_success BEFORE INSERT ON project_audit
            WHEN json_extract(NEW.body, '$.action') IN ('project_status_changed', 'project_human_released')
            BEGIN SELECT RAISE(ABORT, 'Injected audit failure'); END""")
        for action in (lambda: self.service.transition(project.project_id, S.RESEARCH, reason="Test"),
                       lambda: self.human().release_project(project.project_id, "Testmens", "Test")):
            with self.assertRaises(sqlite3.IntegrityError):
                action()
            self.assertEqual(self.service.load(project.project_id), project)
            self.assertEqual(self.service.repository.events(project.project_id)[-1]["action"],
                             "project_operation_failed")

    def test_create_failure_rolls_back_and_invalid_input_has_no_project(self):
        with patch.object(self.service.repository, "_insert", side_effect=OSError("Injected failure")):
            with self.assertRaises(OSError):
                self.create()
        for name in ("", " ", None):
            with self.assertRaises(ValueError):
                self.service.create(name)
        with self.assertRaises(ValueError):
            self.service.create("Naam", location=" ")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM projects").fetchone()[0], 0)

    def test_audit_immutable_and_project_audits_isolated(self):
        project = self.create()
        other = self.create()
        for statement in ("UPDATE project_audit SET body='{}'", "DELETE FROM project_audit",
                          "INSERT OR REPLACE INTO project_audit SELECT * FROM project_audit"):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.store.db:
                    self.store.db.execute(statement)
        self.assertEqual(len(self.service.repository.events(project.project_id)), 1)
        self.assertEqual(len(self.service.repository.events(other.project_id)), 1)
        self.assertEqual(self.store.events(), [])

    def test_unknown_project_invalid_status_and_owned_transaction(self):
        with self.assertRaises(ValueError):
            self.service.load("missing")
        project = self.create()
        with self.assertRaises(ValueError):
            self.service.transition(project.project_id, "UNKNOWN", reason="Test")
        self.store.db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaises(RuntimeError):
                self.service.transition(project.project_id, S.INTAKE, reason="Test")
            self.assertTrue(self.store.db.in_transaction)
        finally:
            self.store.db.rollback()
        self.assertEqual(self.service.load(project.project_id), project)

    def test_cli_create_reload_transitions_release_and_audit_isolated(self):
        result = self.cli("project-create", "CLI test")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project = json.loads(result.stdout)
        project_id = project["project_id"]
        self.assertEqual(json.loads(self.cli("project-show", project_id).stdout), project)
        for target in (S.INTAKE, S.RESEARCH, S.READY):
            result = self.cli("project-transition", project_id, target, "--reason", "CLI test")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.cli("project-transition", project_id, S.RELEASED, "--reason", "Bypass")
        self.assertEqual(result.returncode, 2)
        result = self.cli("project-release", project_id, "--actor", "A01", "--reason", "Bypass")
        self.assertEqual(result.returncode, 2)
        result = self.cli("project-release", project_id, "--actor", "Testmens", "--reason", "Testbesluit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], S.RELEASED)
        events = json.loads(self.cli("project-audit", project_id).stdout)
        self.assertEqual(events[-1]["action"], "project_human_released")
        self.assertEqual(self.store.list(), [])
