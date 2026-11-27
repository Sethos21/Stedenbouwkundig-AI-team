import base64
from contextlib import redirect_stderr
import io
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

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

    def test_handoff_success_and_fail_closed(self):
        task = self.task | {"branch": "codex/issue-42", "base": "base", "run": "17"}
        path = "docs/codex-results/issue-42.md"
        report_path = "docs/opleveringen/codex-actions-issue-42-run-17.md"
        root = f"https://github.com/{route.REPO}"
        pr = {"number": 50, "draft": True, "state": "open",
              "head": {"sha": "report", "ref": task["branch"]}, "base": {"ref": "master"}}
        for fail in (None, "base", "backlink", "draft", "ref", "report", "diff", "post", "get", "late-pr", "late-ref"):
            with self.subTest(fail=fail), patch.dict(os.environ, {"DOCUMENT": "c3ludGhldGlj"}):
                reports, comments, branches = {}, {}, []

                def api(endpoint, *, method="GET", data=None):
                    if endpoint == "issues/42":
                        return self.issue
                    if endpoint == "branches/master":
                        return {"commit": {"sha": "advanced" if fail == "base" and reports else "base"}}
                    if endpoint.startswith("git/ref/heads/"):
                        return {"object": {"sha": ("other" if fail == "ref" or (fail == "late-ref" and 2 in comments) else "report") if branches else "base"}}
                    if endpoint == "git/trees/base?recursive=1":
                        return {"truncated": False, "tree": []}
                    if endpoint == "compare/base...report":
                        files = [path, report_path] if fail != "diff" else [path, "AGENTS.md"]
                        return {"files": [{"filename": name, "status": "added"} for name in files]}
                    if endpoint.startswith("git/refs/heads/"):
                        self.assertEqual(data, {"sha": "report", "force": False})
                        branches.append(data)
                        return {}
                    if endpoint == "pulls":
                        self.assertTrue(data["draft"])
                        return pr
                    if endpoint == "pulls/50":
                        return pr | {"draft": fail != "draft" and not (fail == "late-pr" and 2 in comments)}
                    if endpoint.startswith("contents/"):
                        self.assertEqual(endpoint, f"contents/{report_path}?ref=report")
                        payload = "changed" if fail == "report" else reports[report_path]
                        return {"content": base64.b64encode(payload.encode()).decode()}
                    if method == "POST" and endpoint in ("issues/42/comments", "issues/50/comments"):
                        if fail == "backlink":
                            raise route.RouteError("Status write failed")
                        comment_id = len(comments) + 1
                        comments[comment_id] = data["body"]
                        if comment_id == 2 and fail == "post":
                            raise route.RouteError("Ambiguous receipt POST")
                        return {"id": comment_id}
                    if endpoint.startswith("issues/comments/"):
                        comment_id = int(endpoint.rsplit("/", 1)[1])
                        if comment_id == 2 and fail == "get":
                            raise route.RouteError("Receipt GET failed")
                        return {"body": comments[comment_id]}
                    self.fail(f"Unexpected request: {method} {endpoint}")

                def commit(parent, filename, content, message):
                    self.assertIn((parent, filename), [("base", path), ("work", report_path)])
                    reports[filename] = content
                    return "work" if parent == "base" else "report"

                with patch.object(route, "github", side_effect=api), patch.object(
                    route, "create_document_commit", side_effect=commit
                ):
                    if fail:
                        with self.assertRaises(route.RouteError):
                            route.publish(task)
                        if fail in {"post", "get", "late-pr", "late-ref"}:
                            self.assertIn("publicatiestatus: VOORLOPIG", comments[2])
                            self.assertEqual(len(comments), 2)
                        else:
                            self.assertNotIn(2, comments)
                        self.assertFalse(any("publicatiestatus: GEPUBLICEERD" in c for c in comments.values()))
                    else:
                        route.publish(task)
                        self.assertIn("    synthetic", reports[path])
                        self.assertNotIn("synthetic", reports[report_path])
                        self.assertEqual(len(comments), 2)
                        self.assertIn("publicatiestatus: VOORLOPIG", comments[2])
                        self.assertIn(f"verification_run: {root}/actions/runs/17", comments[2])
                        self.assertIn("work_commit: work", comments[2])
                        self.assertIn("report_commit: report", comments[2])
                        self.assertIn(f"report_url: {root}/blob/report/{report_path}", comments[2])

    def test_http_diagnostics_are_allowlisted_for_both_providers(self):
        for code, category in ((400, "bad_request"), (401, "unauthorized"), (403, "forbidden"),
                               (404, "not_found"), (429, "rate_limited"), (503, "server_error"),
                               (302, "http_error")):
            for provider in ("GitHub", "OpenAI"):
                with self.subTest(code=code, provider=provider), patch.dict(os.environ, {
                    "GH_TOKEN": "github-secret", "CODEX_ACTIONS_API_KEY": "openai-secret",
                    "GITHUB_SHA": "base",
                }), patch.object(route.urllib.request, "build_opener") as opener, redirect_stderr(io.StringIO()) as log:
                    body = Mock()
                    opener.return_value.open.side_effect = HTTPError(
                        "https://untrusted.invalid/path-secret", code, "reason-secret",
                        {"X-Private": "header-secret"}, body,
                    )
                    with self.assertRaisesRegex(route.RouteError, "^API call failed"):
                        if provider == "GitHub":
                            route.github("issues/path-secret?param=query-secret")
                        else:
                            with patch.object(route, "github", return_value={"commit": {"sha": "base"}}):
                                route.preflight()
                    operation = "GitHub GET issues" if provider == "GitHub" else "OpenAI preflight model lookup"
                    self.assertEqual(log.getvalue(), f"{operation} http_status={code} category={category}\n")
                    body.read.assert_not_called()
                    opener.return_value.open.assert_called_once()

    def test_transport_and_invalid_json_are_redacted(self):
        for error, category in ((URLError("secret"), "transport_error"),
                                (ValueError("secret"), "invalid_json")):
            with self.subTest(category=category), patch.dict(os.environ, {"GH_TOKEN": "secret"}), \
                 patch.object(route.urllib.request, "build_opener") as opener, redirect_stderr(io.StringIO()) as log:
                opener.return_value.open.side_effect = error
                with self.assertRaises(route.RouteError):
                    route.github("branches/master")
                self.assertEqual(log.getvalue(), f"GitHub GET branches http_status=none category={category}\n")

    def test_preflight_only_reads_fixed_endpoints_with_separate_credentials(self):
        with patch.dict(os.environ, {
            "GH_TOKEN": "github-secret", "CODEX_ACTIONS_API_KEY": "openai-secret",
            "GITHUB_SHA": "base",
        }), patch.object(route, "request_json", side_effect=[
            ({"commit": {"sha": "base"}}, False), ({"id": route.MODEL}, False),
        ]) as api, patch.object(route, "output") as output:
            route.preflight()
            output.assert_not_called()
        requests = [call.args[0] for call in api.call_args_list]
        self.assertEqual([request.get_method() for request in requests], ["GET", "GET"])
        self.assertEqual([request.full_url for request in requests], [
            f"https://api.github.com/repos/{route.REPO}/branches/master",
            f"https://api.openai.com/v1/models/{route.MODEL}",
        ])
        self.assertEqual([request.get_header("Authorization") for request in requests],
                         ["Bearer github-secret", "Bearer openai-secret"])
        self.assertTrue(all(request.data is None for request in requests))

    def test_preflight_stops_before_openai_on_stale_master(self):
        with patch.dict(os.environ, {
            "GH_TOKEN": "github-secret", "CODEX_ACTIONS_API_KEY": "openai-secret",
            "GITHUB_SHA": "stale",
        }), patch.object(route, "request_json", return_value=({"commit": {"sha": "base"}}, False)) as api:
            with self.assertRaisesRegex(route.RouteError, "stale"):
                route.preflight()
            api.assert_called_once()

    def test_github_pagination_keeps_requests_on_fixed_origin(self):
        with patch.dict(os.environ, {"GH_TOKEN": "test"}), \
             patch.object(route.urllib.request, "build_opener") as opener, redirect_stderr(io.StringIO()):
            responses = []
            for body, link in ((b"[1]", '<https://untrusted.invalid/>; rel="next"'), (b"[2]", "")):
                response = Mock(status=200, headers={"Link": link})
                response.read.return_value = body
                context = Mock()
                context.__enter__ = Mock(return_value=response)
                context.__exit__ = Mock(return_value=False)
                responses.append(context)
            opener.return_value.open.side_effect = responses
            self.assertEqual(route.github("issues?state=open", paginate=True), [1, 2])
            self.assertEqual([call.args[0].full_url for call in opener.return_value.open.call_args_list], [
                f"https://api.github.com/repos/{route.REPO}/issues?state=open&page=1",
                f"https://api.github.com/repos/{route.REPO}/issues?state=open&page=2",
            ])

    def test_redirect_does_not_forward_model_credentials(self):
        self.assertIsNone(route.NoRedirect().redirect_request(
            None, None, 302, "Found", {}, "https://example.org"
        ))


if __name__ == "__main__":
    unittest.main()
