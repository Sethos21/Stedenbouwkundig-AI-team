import os
import unittest
from unittest.mock import patch

import route


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.issue = {
            "title": "[CODEX-AUTO-DOC] Documentation trial",
            "state": "open",
            "body": "Summarize a synthetic park design.",
            "user": {"login": route.OWNER},
        }
        self.digest = route.revision(self.issue)
        self.task = {"issue": "42", "revision": self.digest}

    def test_valid_release(self):
        route.release(self.issue, self.digest)

    def test_edited_release(self):
        self.issue["body"] += " Changed."
        with self.assertRaisesRegex(route.RouteError, "revision"):
            route.release(self.issue, self.digest)

    def test_unapproved_sources(self):
        for override in (
            {"user": {"login": "other"}},
            {"state": "closed"},
            {"pull_request": {}},
            {"title": "[KLAAR_VOOR_CODEX] Manual task"},
        ):
            with self.subTest(override=override), self.assertRaises(route.RouteError):
                candidate = self.issue | override
                route.release(candidate, route.revision(candidate))

    def test_generated_content_is_literal(self):
        self.assertEqual(
            route.document("@someone\n<script>$(command)</script>"),
            "    @someone\n    <script>$(command)</script>\n",
        )
        for value in (" ", "a\0b", "a" * 10001, None):
            with self.subTest(value_type=type(value)), self.assertRaises(route.RouteError):
                route.document(value)

    def test_no_secret_makes_no_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(route, "github") as github:
            with self.assertRaisesRegex(route.RouteError, "Missing"):
                route.execute(self.task)
            github.assert_not_called()

    def test_duplicate_and_claim_race_never_emit_task(self):
        for earlier_claim in (True, False):
            with self.subTest(earlier_claim=earlier_claim), patch.dict(os.environ, {
                "TASK_ISSUE": "42", "TASK_REVISION": self.digest,
                "GITHUB_SHA": "base", "GITHUB_RUN_ID": "17",
            }), patch.object(route, "github") as github, patch.object(route, "output") as output:
                github.side_effect = [
                    {"commit": {"sha": "base"}}, [], [],
                    [{"body": "CODEX_OPDRACHT_V1"}] if earlier_claim else [],
                    self.issue, route.RouteError("Ref create failed"),
                ]
                with self.assertRaises(route.RouteError):
                    route.claim()
                output.assert_not_called()
                self.assertEqual(github.call_count, 4 if earlier_claim else 6)


    def test_publish_rejects_unexpected_diff_before_ref_write(self):
        task = self.task | {"branch": "codex/issue-42", "base": "base", "run": "17"}
        responses = [
            self.issue, {"commit": {"sha": "base"}}, {"object": {"sha": "base"}},
            {"truncated": False, "tree": []}, {"tree": {"sha": "base-tree"}},
            {"sha": "new-tree"}, {"sha": "new"}, {"parents": [{"sha": "base"}]},
            {"files": [{"filename": "AGENTS.md", "status": "modified"}]},
        ]
        with patch.dict(os.environ, {"DOCUMENT": "c3ludGhldGlj"}), patch.object(route, "github") as github:
            github.side_effect = responses
            with self.assertRaisesRegex(route.RouteError, "Unexpected diff"):
                route.publish(task)
            methods = [call.kwargs.get("method", "GET") for call in github.call_args_list]
            self.assertNotIn("PATCH", methods)

    def test_redirect_does_not_forward_model_credentials(self):
        self.assertIsNone(route.NoRedirect().redirect_request(
            None, None, 302, "Found", {}, "https://example.org"
        ))


if __name__ == "__main__":
    unittest.main()
