"""Networkless transport tests. No live request is made by discovery."""
import io
import threading
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from bvc_ai.adapters.pdok_bgt import PDOKBGTAdapter, RD_URI
from bvc_ai.adapters.pdok_live import BBOX, PDOKLiveGetTransport
from bvc_ai.adapters.source_transport import ResponseOrigin
from bvc_ai.domain.sources import FetchExtent


class LiveTransportTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('NETWORKLESS'))
            guard.start()
            self.addCleanup(guard.stop)
        adapter = PDOKBGTAdapter(None, collection_metadata_json='{"id":"pand","crs":["' + RD_URI + '"]}')
        self.request = adapter.build_request(FetchExtent(tuple(map(float, BBOX.split(','))),
                                                       'EPSG:28992', 'testcase/analysis'))
        self.conn = Mock()
        self.response = Mock(status=200)
        self.response.getheaders.return_value = [('Content-Type', 'application/vnd.ogc.fg+json')]
        self.response.read1.side_effect = io.BytesIO(b'  exact\r\nbytes ').read1
        self.conn.getresponse.return_value = self.response
        factory = patch('bvc_ai.adapters.pdok_live.http.client.HTTPSConnection', return_value=self.conn)
        self.factory = factory.start()
        self.addCleanup(factory.stop)

    def test_exact_bytes_headers_origin_and_get(self):
        result = PDOKLiveGetTransport().get(self.request)
        self.assertEqual(result.body, b'  exact\r\nbytes ')
        self.assertEqual(result.headers, tuple(self.response.getheaders.return_value))
        self.assertEqual(result.origin, ResponseOrigin.PROVIDER_RESPONSE)
        self.assertEqual(self.conn.request.call_args.args[0], 'GET')
        self.assertEqual(self.factory.call_args.args, ('api.pdok.nl',))
        self.assertEqual(self.conn.request.call_args.kwargs['headers'],
                         {'Accept': 'application/vnd.ogc.fg+json', 'Accept-Encoding': 'identity'})

    def test_redirect_is_returned_never_followed(self):
        self.response.status = 302
        self.assertEqual(PDOKLiveGetTransport().get(self.request).status, 302)
        self.conn.request.assert_called_once()

    def test_byte_cap_during_read(self):
        with self.assertRaisesRegex(OSError, 'byte cap'):
            PDOKLiveGetTransport().get(replace(self.request, max_response_bytes=3))
        self.assertEqual(self.response.read1.call_args.args, (4,))

    def test_cap_exact_boundary(self):
        result = PDOKLiveGetTransport().get(replace(self.request, max_response_bytes=15))
        self.assertEqual(len(result.body), 15)

    def test_total_deadline_including_blocked_connect_and_body(self):
        for phase in ('connect', 'read1'):
            with self.subTest(phase=phase):
                released = threading.Event()
                finished = threading.Event()
                def block(*args):
                    released.wait(2)
                    finished.set()
                    return b''
                target = self.conn.connect if phase == 'connect' else self.response.read1
                target.side_effect = block
                try:
                    with self.assertRaises(TimeoutError):
                        PDOKLiveGetTransport().get(replace(self.request, timeout_seconds=0.02))
                finally:
                    released.set()
                    self.assertTrue(finished.wait(2))
                    target.side_effect = None

    def test_scope_and_metadata_rejected_before_connection(self):
        for request in (
            replace(self.request, url=self.request.url.replace('api.pdok.nl', 'evil.example')),
            replace(self.request, url=self.request.url.replace('/pand/', '/wegdeel/')),
            replace(self.request, url=self.request.url + '#fragment'),
            replace(self.request, parameters=()),
            replace(self.request, headers=(('Cookie', 'x'),)),
            replace(self.request, timeout_seconds=float('nan')),
            replace(self.request, max_response_bytes=0),
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                PDOKLiveGetTransport().get(request)
        self.factory.assert_not_called()

    def test_truncated_content_length_fails_closed(self):
        self.response.getheaders.return_value = [('Content-Length', '999')]
        with self.assertRaisesRegex(OSError, 'Content-Length mismatch'):
            PDOKLiveGetTransport().get(self.request)
