"""Synthetic orchestration evidence; never real provider data or network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import live_mastenbroekweg_2d as proof
from test_source_profiles import profile_response
from test_pdok_bgt_fetch import SequenceTransport, Timer


class Proof2DTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'runtime/2d-live').mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'runtime/2d-live')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'proof'
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('TEST NETWORK BLOCKED'))
            guard.start()
            self.addCleanup(guard.stop)

    def transport(self, *, source_contract):
        self.keys.append(source_contract)
        return SequenceTransport([profile_response(source_contract)], Timer())

    def test_opt_in_and_directory_guard_before_transport_or_writes(self):
        with patch.object(proof, 'PDOKLiveGetTransport') as transport:
            with self.assertRaisesRegex(ValueError, 'opt-in'):
                proof.run_proof(self.directory, 'synthetic')
            with self.assertRaisesRegex(ValueError, 'runtime/2d-live'):
                proof.run_proof(ROOT / 'runtime/GIS-001', 'synthetic', live_opt_in=True)
            transport.assert_not_called()
            self.assertFalse(self.directory.exists())

    def test_eight_contracts_complete_basis_and_offline_reconstruction(self):
        self.keys = []
        with patch.object(proof, 'PDOKLiveGetTransport', side_effect=self.transport):
            result = proof.run_proof(self.directory, 'synthetic', live_opt_in=True)
        self.assertEqual(result['result'], 'PASS', result)
        self.assertEqual(self.keys, sorted(proof.REQUIRED_CONTRACTS))
        self.assertEqual(result['records'], 8)
        self.assertEqual(result['replay'], 'PASS')
        self.assertTrue(result['complete'])
        self.assertIsNone(result['human_approval'])
        basis = json.loads((self.directory / 'source-basis.json').read_text())
        self.assertEqual(basis['basis_hash'], result['basis_hash'])
        with self.assertRaises(FileExistsError):
            proof.run_proof(self.directory, 'synthetic', live_opt_in=True)

    def test_failed_collection_stops_and_preserves_report_without_pass(self):
        with patch.object(proof, 'PDOKLiveGetTransport', side_effect=OSError('Injected unavailable')):
            result = proof.run_proof(self.directory, 'synthetic', live_opt_in=True)
        self.assertEqual(result['result'], 'BLOCKED')
        self.assertEqual(result['replay'], 'NOT_RUN')
        self.assertFalse(result['collections'])
        self.assertTrue((self.directory / 'report.json').exists())
        self.assertFalse((self.directory / 'source-basis.json').exists())

    def test_non_json_failure_evidence_still_reports_blocked(self):
        from dataclasses import replace
        def broken(*, source_contract):
            item = replace(profile_response(source_contract), body=b'<html>unavailable</html>')
            return SequenceTransport([item], Timer())
        with patch.object(proof, 'PDOKLiveGetTransport', side_effect=broken):
            result = proof.run_proof(self.directory, 'synthetic', live_opt_in=True)
        self.assertEqual(result['result'], 'BLOCKED')
        self.assertEqual(result['failure_phase'], 'validation')
        self.assertEqual(result['failed_captures'][0]['received_bytes'], 24)
        self.assertTrue(result['failed_captures'][0]['raw_hash'])
        self.assertTrue((self.directory / 'report.json').exists())
