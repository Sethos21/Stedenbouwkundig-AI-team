import contextlib
from copy import deepcopy
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from bvc_ai.agents.openai_provider import OpenAIProvider, OpenAIProviderError, DEFAULT_MODEL, FIELDS
from bvc_ai.agents.factory import create_provider
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.agents.smoke import InventorySmokeProvider
from bvc_ai.application.workflow import Workflow
from bvc_ai.cli.main import main
from bvc_ai.infrastructure.store import Store

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "unit-test-credential-not-valid"


def inventory():
    return {field: ["TESTDATA: informatie ontbreekt."] for field in FIELDS}


def envelope(payload):
    return {"status": "completed", "output": [{"type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": json.dumps(payload)}]}]}


class OpenAIProviderTests(unittest.TestCase):
    def setUp(self):
        # Every test replaces credentials AND the entire transport; never a paid request.
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": FAKE_KEY})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.transport = patch("bvc_ai.agents.openai_provider.http.client.HTTPSConnection")
        self.connection_type = self.transport.start()
        self.addCleanup(self.transport.stop)
        self.connection = self.connection_type.return_value
        self.connection.getresponse.return_value.status = 200
        self.brief = json.loads((ROOT / "examples/gis-001.json").read_text(encoding="utf-8"))
        testroot = ROOT / ".tools/test-runs"
        testroot.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=testroot)
        self.addCleanup(self.temp.cleanup)

    def responses(self, *values):
        replies = []
        for value in values:
            response = MagicMock(status=200)
            response.read.return_value = json.dumps(value).encode()
            replies.append(response)
        self.connection.getresponse.side_effect = replies

    def workflow(self):
        store = Store(self.temp.name)
        self.addCleanup(store.close)
        return store, Workflow(store, OpenAIProvider(), ROOT)

    def cli(self, *args):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--data", self.temp.name, *args])
        return code, stdout.getvalue()

    def test_missing_key_is_clear_and_does_not_connect(self):
        for key in ("", "   "):
            with self.subTest(key=key), patch.dict(os.environ, {"OPENAI_API_KEY": key}):
                with self.assertRaisesRegex(OpenAIProviderError, "OPENAI_API_KEY ontbreekt"):
                    OpenAIProvider()
        self.connection_type.assert_not_called()

    def test_key_removed_after_construction_is_rejected(self):
        provider = OpenAIProvider()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(OpenAIProviderError, "OPENAI_API_KEY ontbreekt"):
                provider.inventory(self.brief, [])
        self.connection_type.assert_not_called()

    def test_mock_default_works_without_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            provider = create_provider()
            self.assertIsInstance(provider, DeterministicTestProvider)
            code, output = self.cli("demo", "gis-001")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "AWAITING_HUMAN_APPROVAL")
        self.connection_type.assert_not_called()

    def test_provider_selection_and_settings(self):
        self.assertIsInstance(create_provider("openai"), OpenAIProvider)
        with self.assertRaises(ValueError):
            create_provider("unknown")
        for timeout in (0, -1, float("nan"), float("inf"), 121):
            with self.subTest(timeout=timeout), self.assertRaises(OpenAIProviderError):
                OpenAIProvider(timeout=timeout)
        with self.assertRaises(OpenAIProviderError):
            OpenAIProvider(model="bad\nmodel")

    def test_request_is_bounded_structured_and_has_no_tools(self):
        self.responses(envelope(inventory()))
        OpenAIProvider(timeout=12).inventory(self.brief, ["Controleer CRS."])
        self.connection_type.assert_called_once_with("api.openai.com", timeout=12)
        args, kwargs = self.connection.request.call_args
        self.assertEqual(args, ("POST", "/v1/responses"))
        request = json.loads(kwargs["body"])
        self.assertEqual(request["tools"], [])
        self.assertFalse(request["store"])
        self.assertEqual(request["max_output_tokens"], 1200)
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertFalse(request["text"]["format"]["schema"]["additionalProperties"])
        self.assertEqual(json.loads(request["input"])["revision_points"], ["Controleer CRS."])
        self.assertNotIn(FAKE_KEY, kwargs["body"].decode())
        self.connection.close.assert_called_once()

    def test_provenance_is_adapter_owned_and_sources_unchanged(self):
        self.responses(envelope(inventory()))
        original = deepcopy(self.brief)
        result = OpenAIProvider().inventory(self.brief, [])
        self.assertEqual(result["sources"], original["sources"])
        self.assertEqual(self.brief, original)
        self.assertIn(f"Provider: openai; model: {DEFAULT_MODEL}", result["recommendations"][0])
        result["sources"][0]["label"] = "changed"
        self.assertEqual(self.brief, original)
        self.assertNotIn(FAKE_KEY, json.dumps(result))

    def test_real_sources_rejected_before_network(self):
        self.brief["sources"][0].update(source_type="official", source_status="VERIFIED_SOURCE")
        with self.assertRaises(OpenAIProviderError):
            OpenAIProvider().inventory(self.brief, [])
        self.connection_type.assert_not_called()

    def test_inventory_control_fields_are_rejected(self):
        for name, value in (("status", "APPROVED"), ("human_approval", {"human_actor": "Seth"}),
                            ("sources", []), ("K00", "modified"), ("new_roads", [])):
            with self.subTest(name=name):
                self.responses(envelope({**inventory(), name: value}))
                with self.assertRaisesRegex(OpenAIProviderError, "verboden velden"):
                    OpenAIProvider().inventory(self.brief, [])

    def test_invalid_inventory_lists_rejected(self):
        for bad in ([], "APPROVED", [1], [" "], None):
            with self.subTest(bad=bad):
                data = inventory()
                data["missing_data"] = bad
                self.responses(envelope(data))
                with self.assertRaises(OpenAIProviderError):
                    OpenAIProvider().inventory(self.brief, [])

    def test_full_openai_workflow_waits_and_persists_provenance(self):
        self.responses(envelope(inventory()), envelope({"verdict": "SUFFICIENT", "findings": []}))
        store, workflow = self.workflow()
        task = workflow.demo()
        self.assertEqual(task["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertIsNone(task["human_approval"])
        self.assertEqual(task["outputs"][0]["source_status"], "TESTDATA")
        self.assertIn("Provider: openai", task["outputs"][0]["payload"]["recommendations"][0])
        self.assertIn("Provider: openai", task["reviews"][0]["findings"][-1])
        self.assertEqual(task["outputs"][0]["payload"]["sources"], self.brief["sources"])
        for actor in workflow.profiles:
            for target in ("APPROVED", "REJECTED"):
                with self.assertRaises(PermissionError):
                    workflow.transition("GIS-001", target, actor)
        self.assertEqual(store.get("GIS-001")["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertFalse(any(e["action"] == "human_approved" for e in store.events()))

    def test_approved_review_fails_and_is_audited(self):
        self.responses(envelope(inventory()), envelope({"verdict": "APPROVED", "findings": []}))
        store, workflow = self.workflow()
        with self.assertRaises(OpenAIProviderError):
            workflow.demo()
        self.assertEqual(store.get("GIS-001")["status"], "FAILED")
        self.assertIsNone(store.get("GIS-001")["human_approval"])
        self.assertTrue(any(e["action"] == "error" for e in store.events()))
        self.assertFalse(any(e["action"] == "human_approved" for e in store.events()))

    def test_insufficient_review_retains_real_revision_points(self):
        self.responses(envelope(inventory()), envelope({"verdict": "INSUFFICIENT", "findings": ["Beschrijf CRS."]}))
        store, workflow = self.workflow()
        task = workflow.demo()
        self.assertEqual(task["status"], "READY")
        self.assertIn("Beschrijf CRS.", task["reviews"][0]["findings"])

    def test_insufficient_review_cannot_use_provenance_as_finding(self):
        self.responses(envelope(inventory()), envelope({"verdict": "INSUFFICIENT", "findings": []}))
        store, workflow = self.workflow()
        with self.assertRaises(OpenAIProviderError):
            workflow.demo()
        self.assertEqual(store.get("GIS-001")["status"], "FAILED")

    def test_http_errors_are_sanitized_and_never_retried(self):
        for status in (302, 400, 401, 403, 404, 429, 500):
            with self.subTest(status=status):
                self.connection.reset_mock()
                self.connection.getresponse.return_value.status = status
                self.connection.getresponse.return_value.read.return_value = FAKE_KEY.encode()
                with self.assertRaisesRegex(OpenAIProviderError, f"HTTP {status}") as error:
                    OpenAIProvider().inventory(self.brief, [])
                self.assertNotIn(FAKE_KEY, str(error.exception))
                self.assertEqual(self.connection.request.call_count, 1)
                self.connection.getresponse.return_value.read.assert_not_called()

    def test_transport_errors_are_sanitized(self):
        for error in (TimeoutError(FAKE_KEY), OSError(FAKE_KEY), http.client.HTTPException(FAKE_KEY)):
            with self.subTest(error=type(error).__name__):
                self.connection.request.side_effect = error
                with self.assertRaises(OpenAIProviderError) as caught:
                    OpenAIProvider().inventory(self.brief, [])
                self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_malformed_refused_incomplete_and_tool_output_rejected(self):
        values = [None, {}, {"status": "incomplete"},
                  {"status": "completed", "output": [{"type": "function_call"}]},
                  {"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "refusal"}]}]},
                  {"status": "completed", "output": []}]
        for value in values:
            with self.subTest(value=value):
                self.responses(value)
                with self.assertRaises(OpenAIProviderError):
                    OpenAIProvider().inventory(self.brief, [])

    def test_invalid_json_and_oversize_response_rejected(self):
        for value in (b"not json", b"x" * 1_000_001, b"\xff"):
            with self.subTest(size=len(value)):
                self.connection.getresponse.return_value.read.return_value = value
                with self.assertRaises(OpenAIProviderError):
                    OpenAIProvider().inventory(self.brief, [])

    def test_smoke_calls_openai_once_and_isolates_existing_task(self):
        existing = Store(self.temp.name)
        try:
            sentinel = {"task_id": "GIS-001", "status": "APPROVED", "human_approval": {"human_actor": "Seth"}}
            with existing.db:
                existing._save(sentinel)
        finally:
            existing.close()
        before = (Path(self.temp.name) / "state.sqlite3").read_bytes()
        self.responses(envelope(inventory()))
        code, output = self.cli("--provider", "openai", "smoke")
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertEqual(result["task"]["status"], "AWAITING_HUMAN_APPROVAL")
        self.assertIsNone(result["task"]["human_approval"])
        self.assertEqual(result["review_provider"], "mock")
        self.assertEqual(self.connection.request.call_count, 1)
        self.assertEqual(before, (Path(self.temp.name) / "state.sqlite3").read_bytes())
        self.assertTrue((ROOT / result["data_directory"] / "audit.jsonl").exists())

    def test_smoke_without_key_skips_without_creating_store(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            code, output = self.cli("--provider", "openai", "smoke")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "SKIPPED")
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        self.connection_type.assert_not_called()

    def test_cli_missing_key_fails_before_creating_task(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            code, output = self.cli("--provider", "openai", "demo", "gis-001")
        self.assertEqual(code, 2)
        self.assertIn("OPENAI_API_KEY ontbreekt", output)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_read_commands_do_not_construct_openai_provider(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            code, output = self.cli("--provider", "openai", "tasks")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), [])
        self.connection_type.assert_not_called()

    def test_smoke_wrapper_prevents_second_inventory_call(self):
        provider = InventorySmokeProvider(DeterministicTestProvider())
        provider.inventory(self.brief, [])
        with self.assertRaises(ValueError):
            provider.inventory(self.brief, [])
