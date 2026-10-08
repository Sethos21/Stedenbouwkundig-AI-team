"""Offline tests for the trusted local PowerShell probe's Python entrypoint."""
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from test_ow_document import discovery, fixtures, response, DAY, AVAILABLE, IDENTITY

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dso_phase2_probe', ROOT / 'scripts/dso_phase2_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE PROBE TEST'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_meppel_point_from_pinned_archive(self):
        self.assertEqual(probe.meppel_point(), [208874.379, 524096.822])
        with patch.object(probe, 'ARCHIVE_HASH', 'changed'):
            with self.assertRaises(ValueError):
                probe.meppel_point()

    def test_opt_in_and_time_validation_before_network(self):
        with patch.object(probe, 'DSOLivePostTransport') as transport:
            with self.assertRaises(PermissionError):
                probe.probe(DAY, AVAILABLE)
            for day, stamp in [('bad', AVAILABLE), (DAY, '2026-10-02T09:00:00.1Z'), (DAY, 'missing')]:
                with self.assertRaises(ValueError):
                    probe.probe(day, stamp, live=True)
            transport.assert_not_called()

    def test_discovery_then_explicit_retrieval_without_writes(self):
        discovery_service = Mock()
        discovery_service.discover_point.return_value = discovery()
        transport = Mock()
        transport.get.side_effect = [response(d) for d in fixtures()]
        with patch.object(probe, 'DSODiscoveryService', return_value=discovery_service), patch.object(
                probe, 'DSOLiveOWTransport', return_value=transport):
            result = probe.probe(DAY, AVAILABLE, live=True)
            self.assertEqual(result['retrieval'], 'NOT_REQUESTED')
            transport.get.assert_not_called()
            result = probe.probe(DAY, AVAILABLE, IDENTITY, live=True)
            self.assertEqual(result['captures'], 4)
            self.assertEqual(result['components'], 1)
            self.assertNotIn('source_evidence', result)
            discovery_service.discover_point.assert_called_with(
                [208874.379, 524096.822], peildatum=DAY, beschikbaar_op=AVAILABLE)

    def test_errors_and_reflected_secret_never_printed(self):
        args = ['--live', '--peildatum', DAY, '--beschikbaar-op', AVAILABLE]
        for behavior in ({'side_effect': ValueError('private-provider-details')},
                         {'return_value': {'value': 'test-secret-only'}}):
            output = io.StringIO()
            with patch.dict(os.environ, {'DSO_API_KEY': 'test-secret-only'}), patch.object(
                    probe, 'probe', **behavior), redirect_stdout(output):
                self.assertEqual(probe.main(args), 1)
            self.assertEqual(output.getvalue(), '{"status":"FAILED_CLOSED","details":"SUPPRESSED"}\n')
