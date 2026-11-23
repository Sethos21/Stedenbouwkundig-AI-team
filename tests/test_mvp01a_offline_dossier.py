import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    import mvp01a_offline_dossier as runner
finally:
    sys.path.pop(0)


class OfflineDossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.members = runner.verified_members()

    def setUp(self):
        self.primary, self.baseline, self.report, self.basis = (
            json.loads(self.members[name]) for name in (
                'address-evidence.json', 'baseline-address-evidence.json',
                'report.json', 'source-basis.json',
            )
        )
        self.address = self.primary['address_input']

    def command(self, address):
        return subprocess.run(
            [sys.executable, '-B', str(ROOT / 'scripts/mvp01a_offline_dossier.py'),
             '--address', address],
            env={'PYTHONIOENCODING': 'utf-8'}, capture_output=True, text=True, encoding='utf-8',
            timeout=180,
        )

    def test_historical_archive_produces_dossier(self):
        run = self.command(self.address)
        self.assertEqual(run.returncode, 0, run.stderr)
        dossier = json.loads(run.stdout)
        self.assertEqual(dossier['basis_hash'], self.basis['basis_hash'])
        self.assertEqual(dossier['context_hash'],
                         'c3126944265fdc308d75e2b65ab0c083f527632eda2c0265aec170f8700661eb')
        self.assertEqual(len(dossier['sources']), 8)
        self.assertEqual(dossier['archive_sha256'], runner.ARCHIVE_SHA)

    def test_wrong_or_ambiguous_address_has_no_dossier(self):
        for address in ('K.E. Borgerlaan 5, 7942 HC Meppel', 'K.E. Borgerlaan, Meppel'):
            with self.subTest(address=address):
                run = self.command(address)
                self.assertEqual(run.returncode, 1)
                self.assertEqual(run.stdout, '')

    def test_address_identity_and_extent_must_match(self):
        for field, value in (
            ('official_identifiers', {'nummeraanduiding_id': 'invalid'}),
            ('bbox', [0, 0, 1, 1]),
            ('crs', 'EPSG:4326'),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.bind_address(self.address, self.primary, self.baseline, self.report | {field: value})

    def test_missing_collection_and_stale_revision(self):
        for changes in ({'collections': self.report['collections'][:-1]},
                        {'revision_id': 'A02/v0'}):
            with self.subTest(changes=changes.keys()), self.assertRaises(ValueError):
                runner.bind_collections(self.basis, self.report | changes)

    def test_missing_manifest_member_and_changed_archive(self):
        runtime = ROOT / 'runtime/2d-live'
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as temp:
            package = Path(temp)
            manifest = json.loads((runner.PACKAGE / 'archive-manifest.json').read_bytes())
            digest = manifest['files'].pop('report.json')
            manifest_path = package / 'archive-manifest.json'
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            with patch.object(runner, 'PACKAGE', package):
                with self.assertRaisesRegex(ValueError, 'Unexpected archive manifest'):
                    runner.verified_members()
                manifest['files']['report.json'] = digest
                manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
                with ZipFile(package / runner.ARCHIVE, 'w') as archive:
                    archive.writestr('report.json', 'changed')
                with self.assertRaisesRegex(ValueError, 'Archive hash mismatch'):
                    runner.verified_members()

    def test_network_guard_blocks_socket_and_dns_in_python_child(self):
        code = (
            'import sys, socket; '
            f'sys.path.insert(0, {str(ROOT / "scripts")!r}); '
            'from mvp01a_offline_dossier import block_network; sys.addaudithook(block_network); '
        )
        for expression in ('socket.socket()', 'socket.getaddrinfo("localhost", 80)'):
            with self.subTest(expression=expression):
                run = subprocess.run([sys.executable, '-B', '-c', code + expression],
                                     env={}, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('socket and DNS access blocked', run.stderr)
