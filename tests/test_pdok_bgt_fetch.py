"""Phase 3B: exclusively synthetic TESTDATA and bounded fake transports."""
import copy
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from test_pdok_bgt import DOCUMENT, METADATA, EXTENT
from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter, FetchBudgets, ITEMS_URL, JSON_FG, RD_URI
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin
from bvc_ai.domain.sources import ImportStatus


def response(identity="one", next_link=None, status=200, **changes):
    document = copy.deepcopy(DOCUMENT)
    document["features"][0]["id"] = identity
    document["links"] = [] if next_link is None else [{"rel": "next", "href": next_link}]
    document.update(changes)
    return HttpResponse(status, (("Content-Type", JSON_FG), ("Content-Crs", RD_URI)),
                        json.dumps(document).encode(), ResponseOrigin.TESTDATA)


class Timer:
    value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, delay):
        self.value += delay


class SequenceTransport:
    def __init__(self, responses, timer, elapsed=0):
        self.responses = iter(responses)
        self.requests = []
        self.timer = timer
        self.elapsed = elapsed

    def get(self, request):
        self.requests.append(request)
        self.timer.sleep(self.elapsed)
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


class BoundedFetchTests(unittest.TestCase):
    def fetch(self, responses, *, elapsed=0, **budgets):
        self.timer = Timer()
        self.transport = SequenceTransport(responses, self.timer, elapsed)
        self.adapter = PDOKBGTAdapter(self.transport, collection_metadata_json=json.dumps(METADATA))
        return self.adapter.fetch("TESTDATA/snapshot", EXTENT, budgets=FetchBudgets(**budgets),
                                  monotonic=self.timer, sleep=self.timer.sleep)

    def incomplete(self, result, reason):
        self.assertEqual(result.status, ImportStatus.INCOMPLETE)
        self.assertFalse(result.pagination_exhausted)
        self.assertIn(reason, result.failure_reason)
        self.assertEqual(result.features, ())
        self.assertEqual(result.geometries, ())
        manifest = json.loads(result.manifest_json)
        self.assertFalse(manifest["pagination_exhausted"])
        self.assertEqual(manifest["failure_reason"], result.failure_reason)

    def test_multi_page_and_manifest(self):
        result = self.fetch([response(next_link="?cursor=two"), response("two")])
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertTrue(result.pagination_exhausted)
        self.assertEqual([p.page_number for p in result.pages], [1, 2])
        self.assertEqual([f.page_number for f in result.features], [1, 2])
        self.assertEqual(result.pages[0].next_url, result.pages[1].request_url)
        self.assertIsNone(result.pages[-1].next_url)
        self.assertEqual(len(result.captures), 2)
        manifest = json.loads(result.manifest_json)
        self.assertEqual(manifest["attempts"][0]["next_link"], "?cursor=two")
        self.assertEqual(manifest["point_in_time_consistency"], "NOT_GUARANTEED")
        self.assertIn('"source_status":"TESTDATA"', result.features[1].provenance_json)

    def test_opaque_query_is_not_reencoded(self):
        link = ITEMS_URL + "?cursor=a%2Bb%2F%3D&opaque=x+x&opaque=%20"
        result = self.fetch([response(next_link=link), response("two")])
        self.assertTrue(result.pagination_exhausted)
        self.assertEqual(self.transport.requests[1].url, link)

    def test_untrusted_links_never_reach_transport(self):
        for link in ("https://evil.invalid/", "//evil.invalid/x", "http://api.pdok.nl/x",
                     ITEMS_URL.replace("pand", "wegdeel"), ITEMS_URL + "/../items?cursor=x",
                     ITEMS_URL.replace("/items", "/%69tems"), ITEMS_URL + "#fragment",
                     "https://api.pdok.nl@evil.invalid/x", "https://api.pdok.nl:443/x",
                     "?cursor=x\n", "?cursor=bad%xx", "?cursor=x\\y", "../items?cursor=x"):
            with self.subTest(link=link):
                result = self.fetch([response(next_link=link)])
                self.incomplete(result, "continuation" if "Invalid" in result.failure_reason else "scope")
                self.assertEqual(len(self.transport.requests), 1)
                self.assertEqual(json.loads(result.manifest_json)["pending_continuation"], link)
                self.assertEqual(len(result.captures), 1)

    def test_continuation_cycle(self):
        result = self.fetch([response(next_link="?cursor=x"), response("two", "?cursor=x")])
        self.incomplete(result, "cycle")
        self.assertEqual(len(self.transport.requests), 2)

    def test_equivalent_query_cycle(self):
        result = self.fetch([response(next_link="?cursor=%78&a=1"),
                             response("two", "?a=1&cursor=x")])
        self.incomplete(result, "cycle")

    def test_repeated_cursor_with_changed_parameters(self):
        result = self.fetch([response(next_link="?cursor=x&a=1"),
                             response("two", "?cursor=x&a=2")])
        self.incomplete(result, "cursor cycle")
        self.assertEqual(len(self.transport.requests), 2)

    def test_cumulative_bytes_across_pages(self):
        first, second = response(next_link="?cursor=x"), response("two")
        result = self.fetch([first, second], max_bytes=len(first.body) + len(second.body) - 1)
        self.incomplete(result, "Byte budget")
        self.assertEqual(len(result.captures), 2)
        self.assertEqual(self.transport.requests[1].max_response_bytes, len(second.body) - 1)

    def test_page_budget(self):
        result = self.fetch([response(next_link="?cursor=x")], max_pages=1)
        self.incomplete(result, "Page budget")
        self.assertEqual(len(self.transport.requests), 1)

    def test_feature_budget_with_pending_link(self):
        self.incomplete(self.fetch([response(next_link="?cursor=x")], max_features=1), "Feature budget")

    def test_feature_budget_exceeded_inside_page(self):
        features = [copy.deepcopy(DOCUMENT["features"][0]) for _ in range(2)]
        features[1]["id"] = "second"
        result = self.fetch([response(features=features, numberReturned=2)], max_features=1)
        self.incomplete(result, "Feature budget")

    def test_byte_budget_before_parsing_retains_raw(self):
        item = response()
        result = self.fetch([item], max_bytes=len(item.body) - 1)
        self.incomplete(result, "Byte budget")
        self.assertEqual(result.captures[0].raw.body, item.body)
        self.assertEqual(result.pages, ())
        self.assertEqual(self.transport.requests[0].max_response_bytes, len(item.body) - 1)

    def test_retry_bytes_count_toward_budget(self):
        item = response(status=503)
        result = self.fetch([item], max_bytes=len(item.body))
        self.incomplete(result, "Byte budget")
        self.assertEqual(len(self.transport.requests), 1)

    def test_exact_budgets_terminal_success(self):
        item = response()
        result = self.fetch([item], max_pages=1, max_features=1, max_bytes=len(item.body))
        self.assertTrue(result.pagination_exhausted)

    def test_time_budget_late_response(self):
        result = self.fetch([response()], elapsed=2, max_seconds=1)
        self.incomplete(result, "Time budget")
        self.assertEqual(len(result.captures), 1)
        self.assertEqual(self.transport.requests[0].timeout_seconds, 1)

    def test_request_timeout_late_response(self):
        self.incomplete(self.fetch([response()], elapsed=2, request_timeout=1), "Request timeout")

    def test_transport_timeout_and_io_failure(self):
        for error in (TimeoutError("TESTDATA"), OSError("TESTDATA")):
            with self.subTest(error=type(error)):
                result = self.fetch([error])
                self.incomplete(result, "Transport failure")
                self.assertEqual(result.captures, ())
                self.assertIn(type(error).__name__, result.manifest_json)

    def test_429_retry_after(self):
        item = response(status=429)
        item = replace(item, headers=item.headers + (("Retry-After", "2"),))
        result = self.fetch([item, response()])
        self.assertTrue(result.pagination_exhausted)
        self.assertEqual(self.timer.value, 2)
        self.assertEqual(len(result.captures), 2)
        self.assertEqual(self.transport.requests[0].url, self.transport.requests[1].url)

    def test_5xx_bounded_retry(self):
        for status in (500, 502, 503, 599):
            with self.subTest(status=status):
                result = self.fetch([response(status=status), response()])
                self.assertTrue(result.pagination_exhausted)
                self.assertEqual(self.timer.value, 0.25)

    def test_retry_exhaustion(self):
        for status in (429, 503):
            result = self.fetch([response(status=status)] * 3)
            self.incomplete(result, "Retry exhaustion")
            self.assertEqual(len(self.transport.requests), 3)
            self.assertEqual(len(result.captures), 3)

    def test_retry_disabled(self):
        self.incomplete(self.fetch([response(status=503)], max_retries=0), "Retry exhaustion")

    def test_retry_after_over_time_budget(self):
        item = response(status=429)
        item = replace(item, headers=item.headers + (("Retry-After", "999"),))
        self.incomplete(self.fetch([item]), "Time budget insufficient")
        self.assertEqual(self.timer.value, 0)

    def test_invalid_retry_after_fails_closed(self):
        for value in ("tomorrow", "-1", "1.5"):
            item = response(status=429)
            item = replace(item, headers=item.headers + (("Retry-After", value),))
            self.incomplete(self.fetch([item]), "Unsupported Retry-After")

    def test_interrupted_second_page_no_partial_bundle(self):
        result = self.fetch([response(next_link="?cursor=x"), TimeoutError()])
        self.incomplete(result, "Transport failure")
        self.assertEqual(len(result.pages), 1)
        self.assertEqual(result.pages[0].next_url, ITEMS_URL + "?cursor=x")
        self.assertEqual(json.loads(result.manifest_json)["pending_continuation"], "?cursor=x")

    def test_bad_second_page_and_count_mismatch(self):
        result = self.fetch([response(next_link="?cursor=x"), response("two", numberReturned=3)])
        self.incomplete(result, "numberReturned")
        self.assertEqual(len(result.captures), 2)

    def test_missing_count_not_invented(self):
        item = response()
        doc = json.loads(item.body)
        del doc["numberReturned"]
        result = self.fetch([replace(item, body=json.dumps(doc).encode())])
        self.assertTrue(result.pagination_exhausted)
        self.assertIsNone(json.loads(result.manifest_json)["attempts"][0]["page_metadata"]["numberReturned"])

    def test_redirect_and_nonretryable_http_never_followed(self):
        for status in (301, 302, 400, 404):
            result = self.fetch([response(status=status)])
            self.incomplete(result, "HTTP 200")
            self.assertEqual(len(self.transport.requests), 1)

    def test_duplicate_identity_across_pages(self):
        self.incomplete(self.fetch([response(next_link="?cursor=x"), response()]), "Duplicate feature")

    def test_empty_intermediate_page_still_follows_next(self):
        result = self.fetch([response(next_link="?cursor=x", features=[], numberReturned=0), response()])
        self.assertTrue(result.pagination_exhausted)
        self.assertEqual(len(result.pages), 2)

    def test_malformed_json_keeps_exact_raw(self):
        result = self.fetch([replace(response(), body=b'broken')])
        self.incomplete(result, "validation")
        self.assertEqual(result.captures[0].raw.body, b'broken')

    def test_time_budget_includes_mapping(self):
        original = PDOKBGTAdapter._parse

        def slow_parse(adapter, *args):
            parsed = original(adapter, *args)
            self.timer.sleep(121)
            return parsed

        with patch.object(PDOKBGTAdapter, "_parse", slow_parse):
            self.incomplete(self.fetch([response()]), "Time budget")

    def test_timeout_shrinks_with_remaining_time(self):
        result = self.fetch([response(next_link="?cursor=x"), response("two")],
                            elapsed=0.6, max_seconds=1)
        self.incomplete(result, "Time budget")
        self.assertAlmostEqual(self.transport.requests[1].timeout_seconds, 0.4)

    def test_multiple_next_links_fail_closed(self):
        result = self.fetch([response(links=[{"rel": "next", "href": "?cursor=x"},
                                            {"rel": "next", "href": "?cursor=y"}])])
        self.incomplete(result, "Multiple next links")
        self.assertEqual(len(result.captures), 1)

    def test_single_page_entrypoint_checks_timeout(self):
        timer = Timer()
        transport = SequenceTransport([response()], timer, elapsed=16)
        adapter = PDOKBGTAdapter(transport, collection_metadata_json=json.dumps(METADATA))
        with patch("bvc_ai.adapters.pdok_bgt.time.monotonic", timer):
            result = adapter.fetch_page("TESTDATA/snapshot", EXTENT)
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn("timeout", result.failure_reason)
        self.assertIsNotNone(result.capture)

    def test_invalid_budget_configuration(self):
        for kwargs in ({"max_pages": 0}, {"max_features": True}, {"max_bytes": -1},
                       {"max_seconds": float("inf")}, {"request_timeout": 0},
                       {"max_retries": 11}, {"max_retries": True}, {"retry_delay": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FetchBudgets(**kwargs)


if __name__ == "__main__":
    unittest.main()
