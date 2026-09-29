"""Networkless source-set publication and read-model tests; no real approvals."""
import json
import unittest
import subprocess
import sys
import os
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import test_source_profiles as helpers
from test_source_profiles import profile_response
from test_source_import import TID
from bvc_ai.application.source_basis import SourceBasisService, REQUIRED_CONTRACTS, official_relations
from bvc_ai.infrastructure.source_store import SourceStore


class SourceBasisTests(unittest.TestCase):
    setUp = helpers.SourceProfileTests.setUp
    importer = helpers.SourceProfileTests.importer
    trusted_state = helpers.SourceProfileTests.trusted_state
    assert_failure_unchanged = helpers.SourceProfileTests.assert_failure_unchanged

    def populate(self):
        for key in sorted(REQUIRED_CONTRACTS):
            self.importer(key).import_source(TID, key, self.extent)
        return SourceBasisService(self.store)

    def test_complete_basis_has_all_records_bindings_and_is_read_only(self):
        service = self.populate()
        before = self.trusted_state(), self.store.events()
        basis = service.build(TID)
        self.assertTrue(basis['complete'])
        self.assertEqual({r['source_contract'] for r in basis['records']}, REQUIRED_CONTRACTS)
        self.assertEqual(len(basis['records']), 8)
        self.assertEqual(service.verify(basis), basis)
        self.assertEqual((self.trusted_state(), self.store.events()), before)
        self.assertEqual(basis['point_in_time_consistency'], 'NOT_GUARANTEED')
        self.assertTrue(basis['uncertainties'])
        self.assertIsNone(self.store.get(TID)['human_approval'])
        self.assertFalse(any(o['agent_id'] not in ('A01', 'A02') for o in self.store.get(TID)['outputs']))

    def test_cli_read_basis_and_reject_stale_revision(self):
        service = self.populate()
        basis = service.build(TID)
        root = Path(__file__).resolve().parents[1]
        cmd = [sys.executable, str(root / 'bvc_ai.py'), '--data', self.temp.name,
               'source-basis', TID, '--revision']
        result = subprocess.run(cmd + [basis['revision_id']], cwd=root,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), basis)
        result = subprocess.run(cmd + ['A02/old'], cwd=root,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_partial_basis_cannot_claim_complete(self):
        self.importer('BGT/pand').import_source(TID, 'one', self.extent)
        service = SourceBasisService(self.store)
        with self.assertRaises(ValueError):
            service.build(TID)
        result = service.build(TID, require_complete=False)
        self.assertFalse(result['complete'])
        self.assertEqual(len(result['missing_collections']), 7)

    def test_replacement_stales_view_preserves_others_and_historical_evidence(self):
        service = self.populate()
        old = service.build(TID)
        old_task = self.store.get(TID)
        changed = profile_response('BGT/wegdeel', identity='replacement')
        self.importer('BGT/wegdeel', [changed]).import_source(TID, 'replacement', self.extent)
        current = service.build(TID)
        self.assertNotEqual(old['basis_hash'], current['basis_hash'])
        with self.assertRaisesRegex(ValueError, 'Stale'):
            service.verify(old)
        self.assertIn(old['revision_id'], self.store.get(TID)['stale_revisions'])
        old_refs = {r['geometry_ref'] for r in old['records'] if r['source_contract'] != 'BGT/wegdeel'}
        self.assertEqual(old_refs, {r['geometry_ref'] for r in current['records'] if r['source_contract'] != 'BGT/wegdeel'})
        self.assertEqual(self.store.get(TID)['outputs'][:len(old_task['outputs'])], old_task['outputs'])
        self.assertEqual(self.sources.features('BGT/wegdeel')[0].source_id, 'one')

    def test_carried_source_noop_keeps_current_basis(self):
        service = self.populate()
        before = service.build(TID)
        binding = self.importer('BAG/pand').import_source(TID, 'BAG/pand', self.extent)
        self.assertEqual(binding.snapshot_id, 'BAG/pand')
        self.assertEqual(service.build(TID), before)
        self.assertEqual(self.store.events(TID)[-1]['action'], 'source_import_noop')

    def test_replacement_failure_rolls_back_entire_source_set(self):
        service = self.populate()
        before = service.build(TID)
        with patch.object(SourceStore, '_bind_revision', side_effect=OSError('Injected')):
            self.assert_failure_unchanged(lambda: self.importer('BAG/pand', [profile_response(
                'BAG/pand', 'replacement')]).import_source(TID, 'failed', self.extent))
        self.assertEqual(service.build(TID), before)

    def test_missing_publication_or_tampered_basis_is_rejected(self):
        service = self.populate()
        basis = service.build(TID)
        altered = deepcopy(basis)
        altered['records'][0]['properties_json'] = '{}'
        with self.assertRaises(ValueError):
            service.verify(altered)
        # Trusted-local corruption simulation, not a supported public write path.
        task = self.store.get(TID)
        task['outputs'][-1]['output']['source_set']['BAG/pand']['import_revision_id'] = 'A02/missing'
        with self.store.db:
            self.store._save(task)
        with self.assertRaises(ValueError):
            service.build(TID)
        self.assert_failure_unchanged(lambda: self.importer('BGT/wegdeel', [profile_response(
            'BGT/wegdeel', 'new')]).import_source(TID, 'new', self.extent))

    def test_literal_official_relations_only_and_ambiguities(self):
        def record(key, fid, **props):
            return dict(source_contract=key, source_id=fid, record_ref=[key, key, fid],
                        properties_json=json.dumps(props))
        records = [record('BGT/pand', 'bgt', bag_pnd='0123'),
                   record('BAG/pand', 'pand', identificatie='0123', verblijfsobject=['vbo']),
                   record('BAG/verblijfsobject', 'vbo', identificatie='0456', pand=[
                       'https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items/pand'])]
        relations, uncertainties = official_relations(records)
        self.assertEqual({r['status'] for r in relations}, {'RESOLVED'})
        self.assertFalse(uncertainties)
        records.append(record('BAG/pand', 'other', identificatie='0123'))
        relations, uncertainties = official_relations(records)
        self.assertEqual(relations[0]['status'], 'AMBIGUOUS')
        records[2]['properties_json'] = json.dumps({'pand':['https://evil.example/pand', 'outside-bbox']})
        relations, uncertainties = official_relations(records)
        self.assertTrue(any(r['status'] == 'UNRESOLVED' for r in relations))
        self.assertTrue(any(u['reason'] == 'RECIPROCAL_REFERENCE_NOT_CONFIRMED' for u in uncertainties))
