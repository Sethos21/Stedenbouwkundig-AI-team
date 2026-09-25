"""Phase 3C: adversarial synthetic TESTDATA; no network or publication."""
import copy
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from test_pdok_bgt import DOCUMENT, METADATA, EXTENT
from test_pdok_bgt_fetch import Timer, SequenceTransport, response
from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter, FetchBudgets, ITEMS_URL, JSON_FG, RD_URI
from bvc_ai.adapters.source_transport import HttpResponse
from bvc_ai.domain.sources import ImportStatus


class FailureSecurityTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(target, side_effect=AssertionError('NETWORKLESS test'))
            guard.start()
            self.addCleanup(guard.stop)

    def fetch(self, responses, *, elapsed=0, **budgets):
        self.timer = Timer()
        self.transport = SequenceTransport(responses, self.timer, elapsed)
        self.adapter = PDOKBGTAdapter(self.transport, collection_metadata_json=json.dumps(METADATA))
        return self.adapter.fetch('TESTDATA/phase3c', EXTENT, budgets=FetchBudgets(**budgets),
                                  monotonic=self.timer, sleep=self.timer.sleep)

    def incomplete(self, result, reason=None):
        self.assertEqual(result.status, ImportStatus.INCOMPLETE)
        self.assertFalse(result.pagination_exhausted)
        self.assertTrue(result.failure_reason)
        if reason:
            self.assertIn(reason, result.failure_reason)
        self.assertEqual(result.features, ())
        self.assertEqual(result.geometries, ())
        manifest = json.loads(result.manifest_json)
        self.assertEqual(manifest['failure_reason'], result.failure_reason)
        self.assertFalse(manifest['pagination_exhausted'])
        self.assertEqual(manifest['point_in_time_consistency'], 'NOT_GUARANTEED')

    def test_request_deadline_includes_successful_parsing(self):
        original = PDOKBGTAdapter._parse

        def slow_parse(adapter, *args):
            parsed = original(adapter, *args)
            self.timer.sleep(1)
            return parsed

        with patch.object(PDOKBGTAdapter, '_parse', slow_parse):
            result = self.fetch([response()], request_timeout=1, max_seconds=10)
        self.incomplete(result, 'Request timeout')
        self.assertEqual(len(result.captures), 1)

    def test_request_deadline_includes_failing_parsing(self):
        def slow_parse(adapter, *args):
            self.timer.sleep(1)
            raise ValueError('synthetic parse failure')

        with patch.object(PDOKBGTAdapter, '_parse', slow_parse):
            result = self.fetch([response()], request_timeout=1, max_seconds=10)
        self.incomplete(result)
        self.assertEqual(len(result.captures), 1)

    def test_invalid_response_body_fails_without_fabricated_bytes(self):
        for body in (None, 'not bytes', bytearray(b'body'), 3):
            with self.subTest(body=repr(body)):
                item = response()
                # Simulates a broken trusted transport bypassing dataclass validation.
                object.__setattr__(item, 'body', body)
                result = self.fetch([item])
                self.incomplete(result, 'Invalid transport response')
                self.assertEqual(result.captures, ())
                self.assertEqual(len(self.transport.requests), 1)

    def test_cursor_multiset_cycle_with_reordered_duplicates(self):
        result = self.fetch([response(next_link='?cursor=a&cursor=b&other=1'),
                             response('two', '?cursor=b&cursor=a&other=2')])
        self.incomplete(result, 'cursor cycle')
        self.assertEqual(len(self.transport.requests), 2)


    def test_forbidden_continuations_never_reach_transport(self):
        path = '/lv/bgt/ogc/v1/collections/pand/items'
        links = [
            'http://api.pdok.nl' + path, 'ftp://api.pdok.nl' + path,
            'https://evil.invalid' + path, 'https://api.pdok.nl.evil.invalid' + path,
            'https://api.pdok.nl.' + path, 'https://user@api.pdok.nl' + path,
            'https://user:pass@api.pdok.nl' + path, 'https://api.pdok.nl@evil.invalid' + path,
            'https://api.pdok.nl:443' + path, 'https://api.pdok.nl:80' + path,
            'https://api.pdok.nl:invalid' + path, '//api.pdok.nl' + path,
            '//evil.invalid' + path, '///evil.invalid' + path,
            ITEMS_URL + '#', ITEMS_URL + '#fragment', '?cursor=x#fragment',
            ITEMS_URL + '\\evil', '?cursor=x\\y',
            '?cursor=%', '?cursor=%0', '?cursor=%GG', '?cursor=x%2g',
            ITEMS_URL.replace('/items', '/%69tems'),
            ITEMS_URL.replace('/items', '/%2569tems'),
            ITEMS_URL.replace('/pand/items', '/pand%2fitems'),
            ITEMS_URL + '/.', ITEMS_URL + '/..', ITEMS_URL + '/../items',
            ITEMS_URL + '/%2e%2e/items', ITEMS_URL + '/%252e%252e/items',
            ITEMS_URL + '/%5c..%5citems', ITEMS_URL + '/%00',
            ITEMS_URL.replace('/pand/', '/wegdeel/'),
            ITEMS_URL.replace('/items', ''), ITEMS_URL + '/id',
            '../items?cursor=x', './items?cursor=x', 'items?cursor=x',
            'https://[invalid' + path, '?cursor=\u00e9',
        ]
        for char in (' ', '\t', '\r', '\n', '\x00', '\x1f', '\x7f'):
            links.extend((char + ITEMS_URL, '?cursor=x' + char, ITEMS_URL + char))
        for link in links:
            with self.subTest(link=repr(link)):
                item = response(next_link=link)
                result = self.fetch([item])
                self.incomplete(result)
                self.assertEqual(len(self.transport.requests), 1)
                self.assertEqual(result.captures[0].raw.body, item.body)
                self.assertEqual(json.loads(result.manifest_json)['pending_continuation'], link)

    def test_query_only_opaque_data_cannot_change_endpoint(self):
        links = ('?cursor=%2F%2Fevil.invalid%2Fx', '?cursor=%2e%2e%2fitems',
                 '?cursor=%23fragment%5c%0d%0a', '?redirect=https://evil.invalid/x',
                 '?cursor=a%2Bb%2Fc%3D&opaque=one&opaque=two&blank=&flag',
                 '?cursor=%252e%252e&x=%26cursor%3Dother')
        for link in links:
            with self.subTest(link=link):
                result = self.fetch([response(next_link=link), response('two')])
                self.assertEqual(result.status, ImportStatus.VALIDATING)
                self.assertEqual(self.transport.requests[1].url, ITEMS_URL + link)
                self.assertEqual(result.captures[1].request.url, ITEMS_URL + link)

    def test_equivalent_request_cycles_without_cursor(self):
        for first, second in (
            ('?offset=2&a=1', '?a=1&offset=2'),
            ('?offset=%32&x=%7e', '?x=~&offset=2'),
            ('?x=a+b', '?x=a%20b'),
            ('?flag', '?flag='),
            ('?x=1&x=2', '?x=2&x=1'),
            ('?%6Fffset=2', '?offset=2'),
        ):
            with self.subTest(first=first, second=second):
                result = self.fetch([response(next_link=first), response('two', ITEMS_URL + second)])
                self.incomplete(result, 'Continuation cycle')
                self.assertEqual(len(self.transport.requests), 2)

    def test_original_request_cycle_and_bare_query(self):
        adapter = PDOKBGTAdapter(None, collection_metadata_json=json.dumps(METADATA))
        original = adapter.build_request(EXTENT).url
        for link in (original, '?'):
            with self.subTest(link=link):
                result = self.fetch([response(next_link=link)])
                self.incomplete(result, 'Continuation cycle')
                self.assertEqual(len(self.transport.requests), 1)

    def test_distinct_duplicate_parameter_requests_remain_distinct(self):
        first, second = '?offset=2&tag=a&tag=b', '?offset=2&tag=b&tag=b'
        result = self.fetch([response(next_link=first), response('two', second), response('three')])
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertEqual(self.transport.requests[1].parameters,
                         (('offset', '2'), ('tag', 'a'), ('tag', 'b')))
        self.assertEqual(self.transport.requests[2].parameters,
                         (('offset', '2'), ('tag', 'b'), ('tag', 'b')))

    def test_malformed_pagination_preserves_previous_page_only(self):
        for links in (None, {}, [None], [{}], [{'rel': 'next'}],
                      [{'rel': 'next', 'href': None}], [{'rel': 'next', 'href': 2}],
                      [{'rel': 'next', 'href': ''}], [{'rel': 'next', 'href': ' '}],
                      [{'rel': 'next', 'href': '?x=2'}] * 2):
            with self.subTest(links=links):
                item = response('two', links=links)
                result = self.fetch([response(next_link='?cursor=two'), item])
                self.incomplete(result)
                self.assertEqual(len(result.pages), 1)
                self.assertEqual(len(result.captures), 2)
                self.assertEqual(result.captures[1].raw.body, item.body)

    def test_missing_next_is_exhaustion_only_even_with_number_matched(self):
        item = response(numberMatched=999)
        document = json.loads(item.body)
        del document['links']
        result = self.fetch([replace(item, body=json.dumps(document).encode())])
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertTrue(result.pagination_exhausted)
        manifest = json.loads(result.manifest_json)
        self.assertEqual(manifest['point_in_time_consistency'], 'NOT_GUARANTEED')
        self.assertEqual(manifest['attempts'][0]['page_metadata']['response_metadata']['numberMatched'], 999)
        self.assertFalse(hasattr(result, 'snapshot'))

    def test_duplicate_features_within_and_across_pages_drop_all_bundles(self):
        duplicate = copy.deepcopy(DOCUMENT['features'][0])
        cases = (
            [response(features=[duplicate, duplicate], numberReturned=2)],
            [response(next_link='?cursor=two'), response()],
        )
        for responses in cases:
            with self.subTest(pages=len(responses)):
                result = self.fetch(responses)
                self.incomplete(result, 'Duplicate feature')
                self.assertEqual(len(result.captures), len(responses))

    def test_exact_terminal_and_pending_budget_boundaries(self):
        terminal = response()
        result = self.fetch([terminal], max_pages=1, max_features=1, max_bytes=len(terminal.body))
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        for budget in ('max_pages', 'max_features', 'max_bytes'):
            with self.subTest(budget=budget):
                item = response(next_link='?cursor=two')
                value = len(item.body) if budget == 'max_bytes' else 1
                result = self.fetch([item], **{budget: value})
                self.incomplete(result, 'budget')
                self.assertEqual(len(self.transport.requests), 1)
                self.assertEqual(len(result.pages), 1)

    def test_time_boundary_exact_and_just_before(self):
        for elapsed, succeeds in ((0.999, True), (1.0, False), (1.001, False)):
            with self.subTest(elapsed=elapsed):
                result = self.fetch([response()], elapsed=elapsed, max_seconds=1)
                if succeeds:
                    self.assertEqual(result.status, ImportStatus.VALIDATING)
                else:
                    self.incomplete(result, 'Time budget')
                self.assertEqual(len(result.captures), 1)

    def test_page_feature_and_response_size_overflow(self):
        features = [dict(DOCUMENT['features'][0], id=str(i)) for i in range(2)]
        self.incomplete(self.fetch([response(features=features, numberReturned=2)], max_features=1),
                        'Feature budget')
        oversized = replace(response(), body=b'invalid JSON larger than cap')
        result = self.fetch([oversized], max_bytes=4)
        self.incomplete(result, 'Byte budget')
        self.assertEqual(result.captures[0].raw.body, oversized.body)
        self.assertEqual(result.pages, ())
        self.assertEqual(self.transport.requests[0].max_response_bytes, 4)

    def test_request_page_limit_still_enforced(self):
        item = response(features=[dict(DOCUMENT['features'][0], id=str(i)) for i in range(1001)],
                        numberReturned=1001)
        self.incomplete(self.fetch([item]), 'page limit')

    def test_transport_errors_after_partial_page_are_not_retried(self):
        for error in (TimeoutError('TESTDATA timeout'), OSError('TESTDATA IO')):
            with self.subTest(error=type(error)):
                result = self.fetch([response(next_link='?cursor=two'), error], max_retries=10)
                self.incomplete(result, 'Transport failure')
                self.assertEqual(len(result.pages), 1)
                self.assertEqual(len(result.captures), 1)
                self.assertEqual(len(self.transport.requests), 2)
                self.assertNotIn('raw_response_hash', json.loads(result.manifest_json)['attempts'][1])

    def test_all_retryable_statuses_have_bounded_attempts_and_raw_evidence(self):
        for status in (429, *range(500, 600)):
            with self.subTest(status=status):
                item = replace(response(status=status), body=b'TESTDATA error response')
                result = self.fetch([item] * 3)
                self.incomplete(result, 'Retry exhaustion')
                self.assertEqual(len(self.transport.requests), 3)
                self.assertEqual([c.raw.body for c in result.captures], [item.body] * 3)
                self.assertEqual(self.timer.value, 0.75)
                manifest = json.loads(result.manifest_json)
                self.assertEqual([a['retry'] for a in manifest['attempts']], [0, 1, 2])
                self.assertEqual(manifest['received_bytes'], len(item.body) * 3)

    def test_retry_after_malformed_duplicate_and_http_date(self):
        values = ('', ' ', '+1', '-1', '1.0', '1e1', ' 1', '1 ', '1,2', '1\r\n2',
                  '9999999999', 'Fri, 25 Sep 2026 12:00:00 GMT')
        extras = [(("Retry-After", value),) for value in values]
        extras += [(('Retry-After', '1'), ('retry-after', '1')),
                   (('Retry-After', '1'), ('RETRY-AFTER', '2'))]
        for headers in extras:
            with self.subTest(headers=headers):
                item = response(status=429)
                result = self.fetch([replace(item, headers=item.headers + headers)])
                self.incomplete(result, 'Retry-After')
                self.assertEqual(len(self.transport.requests), 1)
                self.assertEqual(len(result.captures), 1)
                self.assertEqual(self.timer.value, 0)

    def test_retry_after_delay_respects_budget_and_minimum_backoff(self):
        for value, delay in (('0', 0.25), ('0002', 2), ('2', 2)):
            with self.subTest(value=value):
                item = response(status=503)
                item = replace(item, headers=item.headers + (('Retry-After', value),))
                result = self.fetch([item, response()])
                self.assertEqual(result.status, ImportStatus.VALIDATING)
                self.assertEqual(self.timer.value, delay)
        item = replace(response(status=429), headers=(('Retry-After', '1'),))
        result = self.fetch([item], max_seconds=1)
        self.incomplete(result, 'Time budget insufficient')
        self.assertEqual(self.timer.value, 0)

    def test_retry_bytes_exhaust_budget_without_losing_error_response(self):
        error = replace(response(status=503), body=b'error')
        final = response()
        result = self.fetch([error, final], max_bytes=len(error.body) + len(final.body) - 1)
        self.incomplete(result, 'Byte budget')
        self.assertEqual([c.raw.body for c in result.captures], [error.body, final.body])
        self.assertEqual(self.transport.requests[1].max_response_bytes, len(final.body) - 1)

    def test_redirects_and_unexpected_status_never_retried_or_followed(self):
        for status in (100, 101, 199, 201, 204, 206, 299, 300, 301, 302, 303, 304, 307, 308,
                       400, 401, 403, 404, 408, 418, 499):
            with self.subTest(status=status):
                item = replace(response(status=status), body=b'TESTDATA HTTP failure',
                               headers=(('Location', 'https://evil.invalid/'),))
                result = self.fetch([item])
                self.incomplete(result, 'HTTP 200')
                self.assertEqual(len(self.transport.requests), 1)
                self.assertEqual(result.captures[0].response, item)

    def test_invalid_transport_response_objects(self):
        for item in (None, {}, b'bytes', 'text', 200):
            with self.subTest(item=item):
                result = self.fetch([item])
                self.incomplete(result, 'Invalid transport response')
                self.assertEqual(result.captures, ())

    def test_invalid_http_response_metadata_retains_actual_body(self):
        for field, value in (('status', True), ('status', '200'), ('status', 999),
                             ('headers', []), ('headers', (('bad',),)),
                             ('headers', ((3, 'value'),)), ('headers', (('name', None),)),
                             ('origin', 'FAKE_ORIGIN')):
            with self.subTest(field=field, value=value):
                item = response()
                object.__setattr__(item, field, value)
                result = self.fetch([item])
                self.incomplete(result)
                self.assertEqual(result.captures[0].raw.body, item.body)
                self.assertEqual(len(self.transport.requests), 1)

    def test_json_failures_preserve_bytes_after_partial_page(self):
        for body in (b'', b'{', b'null', b'[]', b'\xff', b'{"type":"FeatureCollection","type":"FeatureCollection"}',
                     b'{"value":NaN}', b'{"value":Infinity}', b'[' * 1100 + b']' * 1100):
            with self.subTest(body=body[:60]):
                item = replace(response('two'), body=body)
                result = self.fetch([response(next_link='?cursor=two'), item])
                self.incomplete(result)
                self.assertEqual(len(result.pages), 1)
                self.assertEqual(result.captures[1].raw.body, body)

    def test_response_headers_crs_encoding_and_duplicates(self):
        good = response().headers
        headers = [(), (('Content-Type', JSON_FG),),
                   (('Content-Type', 'application/json'), ('Content-Crs', RD_URI)),
                   (('Content-Type', JSON_FG + '; charset=latin1'), ('Content-Crs', RD_URI)),
                   (('Content-Type', JSON_FG), ('Content-Crs', 'EPSG:4326')),
                   (('Content-Type', JSON_FG), ('Content-Crs', ''))]
        for name, value in good + (('Content-Encoding', 'identity'),):
            headers.append(good + ((name, value), (name.upper(), value)))
        for encoding in ('gzip', 'br', 'deflate', 'identity, gzip', ''):
            headers.append(good + (('Content-Encoding', encoding),))
        for values in headers:
            with self.subTest(headers=values):
                item = replace(response('two'), headers=values)
                result = self.fetch([response(next_link='?cursor=two'), item])
                self.incomplete(result)
                self.assertEqual(len(result.pages), 1)
                self.assertEqual(result.captures[1].response.headers, values)

    def test_featurecollection_crs_and_count_failures(self):
        changes = [{'type': 'Feature'}, {'features': None}, {'features': {}},
                   {'coordRefSys': None}, {'coordRefSys': 'EPSG:4326'},
                   {'coordRefSys': {'type': 'Reference', 'href': RD_URI}}]
        changes += [{'numberReturned': count} for count in (None, True, '1', -1, 0, 1.5, 2)]
        for change in changes:
            with self.subTest(change=change):
                item = response('two', **change)
                result = self.fetch([response(next_link='?cursor=two'), item])
                self.incomplete(result)
                self.assertEqual(len(result.pages), 1)
                self.assertEqual(result.captures[1].raw.body, item.body)

    def test_bad_feature_after_valid_feature_drops_mapping(self):
        feature = DOCUMENT['features'][0]
        bad_features = [None, {}, dict(feature, id=[]), dict(feature, id=''),
                        dict(feature, id='two', properties=[]),
                        dict(feature, id='two', place=None),
                        dict(feature, id='two', coordRefSys='EPSG:4326'),
                        dict(feature, id='two', place={'type': 'Polygon', 'coordinates': []})]
        for bad in bad_features:
            with self.subTest(bad=bad):
                item = response(features=[feature, bad], numberReturned=2)
                result = self.fetch([item])
                self.incomplete(result)
                self.assertEqual(result.pages, ())
                self.assertEqual(result.captures[0].raw.body, item.body)

    def test_capture_exists_before_parser_is_entered(self):
        observed = []

        def inspect_capture(adapter, capture, *args):
            observed.append(capture)
            self.assertEqual(capture.raw.body, b'TESTDATA unparsed bytes')
            self.assertEqual(capture.response.body, capture.raw.body)
            raise ValueError('intentional parser failure')

        item = replace(response(), body=b'TESTDATA unparsed bytes')
        with patch.object(PDOKBGTAdapter, '_parse', inspect_capture):
            result = self.fetch([item])
        self.incomplete(result, 'intentional parser failure')
        self.assertIs(result.captures[0], observed[0])

    def test_single_page_invalid_transport_response_fails_closed(self):
        for item in (None, object(), response()):
            if isinstance(item, HttpResponse):
                object.__setattr__(item, 'body', None)
            with self.subTest(item=repr(item)):
                transport = SequenceTransport([item], Timer())
                adapter = PDOKBGTAdapter(transport, collection_metadata_json=json.dumps(METADATA))
                result = adapter.fetch_page('TESTDATA/phase3c', EXTENT)
                self.assertEqual(result.status, ImportStatus.FAILED)
                self.assertEqual(result.features, ())
                self.assertEqual(result.geometries, ())
                self.assertIsNone(result.capture)


    def test_request_deadline_on_later_page_discards_previous_bundle(self):
        original = PDOKBGTAdapter._parse

        def slow_second_page(adapter, *args):
            parsed = original(adapter, *args)
            if len(self.transport.requests) == 2:
                self.timer.sleep(1)
            return parsed

        with patch.object(PDOKBGTAdapter, '_parse', slow_second_page):
            result = self.fetch([response(next_link='?cursor=two'), response('two')],
                                request_timeout=1, max_seconds=10)
        self.incomplete(result, 'Request timeout')
        self.assertEqual(len(result.pages), 1)
        self.assertEqual(len(result.captures), 2)

    def test_retry_limit_applies_per_page_and_total_requests_are_bounded(self):
        error = response(status=503)
        items = [error, error, response(next_link='?cursor=two'),
                 error, error, response('two', '?cursor=three')]
        result = self.fetch(items, max_pages=2, max_retries=2)
        self.incomplete(result, 'Page budget')
        self.assertEqual(len(self.transport.requests), 2 * (2 + 1))
        self.assertEqual(len(result.captures), 6)
        self.assertEqual(len(result.pages), 2)
        attempts = json.loads(result.manifest_json)['attempts']
        self.assertEqual([a['retry'] for a in attempts], [0, 1, 2, 0, 1, 2])

    def test_single_page_parse_deadline_retains_raw_without_mapping(self):
        timer = Timer()
        item = response()
        transport = SequenceTransport([item], timer)
        adapter = PDOKBGTAdapter(transport, collection_metadata_json=json.dumps(METADATA))
        original = adapter._parse

        def slow_parse(*args):
            parsed = original(*args)
            timer.sleep(15)
            return parsed

        with patch('bvc_ai.adapters.pdok_bgt.time.monotonic', timer), \
                patch.object(adapter, '_parse', slow_parse):
            result = adapter.fetch_page('TESTDATA/phase3c', EXTENT)
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIn('timeout', result.failure_reason)
        self.assertEqual(result.features, ())
        self.assertEqual(result.geometries, ())
        self.assertIsNone(result.page)
        self.assertEqual(result.capture.raw.body, item.body)


if __name__ == '__main__':
    unittest.main()
