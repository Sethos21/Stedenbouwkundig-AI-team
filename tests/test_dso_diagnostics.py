"""All diagnostic categories tested offline; no real credential or HTTP access."""
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
import os
import unittest
from unittest.mock import Mock, patch

from bvc_ai.adapters.dso_diagnostics import diagnostic, report
from bvc_ai.adapters.dso_discovery import build_request, parse_response
from bvc_ai.adapters.dso_live import DSOLivePostTransport, DSOLiveOWTransport
from bvc_ai.adapters.ow_document import build_request as ow_request, parse_response as ow_parse
from test_dso_discovery import response as discovery_response
from test_ow_document import DAY, AVAILABLE, URI, discovery, fixtures, response
from test_dso_phase2_probe import probe

SECRET = 'synthetic-diagnostic-secret'
ARGS = ['--live', '--peildatum', DAY, '--beschikbaar-op', AVAILABLE]


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(target, side_effect=AssertionError('OFFLINE'))
            guard.start()
            self.addCleanup(guard.stop)

    def capture(self, operation):
        with self.assertRaises(Exception) as caught:
            operation()
        output = io.StringIO()
        with patch.object(probe, 'probe', side_effect=caught.exception), redirect_stdout(output):
            self.assertEqual(probe.main(ARGS), 1)
        text = output.getvalue()
        for forbidden in (SECRET, 'provider-private', 'X-API-Key', 'Authorization'):
            self.assertNotIn(forbidden, text)
        result = json.loads(text)
        self.assertEqual(result['status'], 'FAILED_CLOSED')
        self.assertEqual(set(result), {'status', 'details', 'phase', 'category',
                                      'http_status', 'contract_version', 'validation_error_code'})
        return result

    def transport(self, status=200, version='2.13.1', failure=None, body=b'{}', get=False):
        conn, http = Mock(), Mock(status=status)
        conn.getresponse.return_value = http
        http.getheaders.return_value = [('API-Version', version), ('Content-Type', 'application/hal+json')]
        http.read1.side_effect = io.BytesIO(body).read1
        if failure is not None:
            conn.connect.side_effect = failure
        transport = DSOLiveOWTransport(live_opt_in=True) if get else DSOLivePostTransport(live_opt_in=True)
        request = ow_request(URI, 'metadata', DAY, AVAILABLE) if get else build_request(
            [208874.379, 524096.822], DAY, AVAILABLE)
        with patch.dict(os.environ, {'DSO_API_KEY': SECRET}), patch(
                'bvc_ai.adapters.dso_live.http.client.HTTPSConnection', return_value=conn):
            result = self.capture(lambda: transport.get(request) if get else transport.post(request))
        return result, http

    def test_authentication_and_unexpected_http_for_both_transports(self):
        for get in (False, True):
            for status, category in ((401, 'AUTHENTICATION'), (403, 'AUTHENTICATION'),
                                     (302, 'UNEXPECTED_HTTP_STATUS'), (429, 'UNEXPECTED_HTTP_STATUS'),
                                     (500, 'UNEXPECTED_HTTP_STATUS')):
                with self.subTest(get=get, status=status):
                    result, http = self.transport(status=status, get=get)
                    self.assertEqual(result['category'], category)
                    self.assertEqual(result['phase'], 'response')
                    self.assertEqual(result['http_status'], status)
                    self.assertEqual(result['contract_version'], '2.13.1')
                    http.read1.assert_not_called()

    def test_network_timeout_tls_and_internal_failures(self):
        import ssl
        for failure, category in ((OSError(SECRET), 'NETWORK_TRANSPORT'),
                                  (TimeoutError(SECRET), 'NETWORK_TRANSPORT'),
                                  (ssl.SSLError(SECRET), 'NETWORK_TRANSPORT'),
                                  (RuntimeError(SECRET), 'INTERNAL_APPLICATION')):
            result, _ = self.transport(failure=failure)
            self.assertEqual(result['phase'], 'transport')
            self.assertEqual(result['category'], category)
            self.assertIsNone(result['http_status'])

    def test_malformed_json_and_secret_reflection_are_response_validation(self):
        for body in (b'{', json.dumps({'provider-private': SECRET}).encode()):
            result, _ = self.transport(body=body)
            self.assertEqual(result['category'], 'SCHEMA_VALIDATION')
            self.assertEqual(result['phase'], 'response')
            self.assertEqual(result['http_status'], 200)

    def test_missing_credential_no_network(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self.capture(lambda: DSOLivePostTransport(live_opt_in=True).post(
                build_request([208874.379, 524096.822], DAY, AVAILABLE)))
        self.assertEqual(result['category'], 'AUTHENTICATION')

    def test_version_drift_and_schema_failures_in_both_parsers(self):
        for get in (False, True):
            original = response(fixtures()[0]) if get else discovery_response()
            request = ow_request(URI, 'metadata', DAY, AVAILABLE) if get else build_request(
                [208874.379, 524096.822], DAY, AVAILABLE)
            def parse(value):
                return ow_parse(value, request, 'metadata', discovery()['documents'][0]) if get else parse_response(value, request)
            for version in ('9.9.9', 'provider-private', SECRET, None):
                headers = [('Content-Type', 'application/hal+json')]
                if version is not None:
                    headers.append(('API-Version', version))
                result = self.capture(lambda: parse(replace(original, headers=tuple(headers))))
                self.assertEqual(result['category'], 'CONTRACT_VERSION_MISMATCH')
                self.assertEqual(result['phase'], 'validatie')
                self.assertEqual(result['http_status'], 200)
                self.assertEqual(result['contract_version'], '9.9.9' if version == '9.9.9' else None)
            result = self.capture(lambda: parse(replace(original, body=b'{}')))
            self.assertEqual(result['category'], 'SCHEMA_VALIDATION')

    def test_pinned_contract_drift_has_own_category(self):
        for module in ('dso_contract', 'ow_document'):
            with patch('bvc_ai.adapters.' + module + '.Path.read_bytes', return_value=b'{}'):
                import importlib
                result = self.capture(importlib.import_module('bvc_ai.adapters.' + module).contract)
                self.assertEqual(result['category'], 'CONTRACT_VERSION_MISMATCH')

    def test_preflight_validation_and_internal_application(self):
        result = self.capture(lambda: probe.probe('invalid', AVAILABLE, live=True))
        self.assertEqual(result['phase'], 'discovery')
        self.assertEqual(result['category'], 'SCHEMA_VALIDATION')
        with patch.object(probe, 'meppel_point', side_effect=RuntimeError(SECRET)):
            result = self.capture(lambda: probe.probe(DAY, AVAILABLE, live=True))
        self.assertEqual(result['category'], 'INTERNAL_APPLICATION')

    def test_version_allowlist_format_and_credential_collision(self):
        with patch.dict(os.environ, {'DSO_API_KEY': '2.13.1'}):
            self.assertIsNone(diagnostic('response', 'SCHEMA_VALIDATION', 200, '2.13.1')['contract_version'])
        for value in ('1.2.3\nprovider-private', '1234.5.6', {}, None):
            self.assertIsNone(diagnostic('response', 'SCHEMA_VALIDATION', 200, value)['contract_version'])
        self.assertEqual(report(RuntimeError(SECRET))['category'], 'INTERNAL_APPLICATION')
