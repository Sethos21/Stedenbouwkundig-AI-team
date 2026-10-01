"""A02 factual projection, isolated synthetic tests and accepted offline Meppel archive."""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import test_source_profiles as helpers
from test_source_import import TID
from bvc_ai.application.source_basis import SourceBasisService, REQUIRED_CONTRACTS
from bvc_ai.application.spatial_context import SpatialContextService
from bvc_ai.infrastructure.store import Store

ROOT = Path(__file__).resolve().parents[1]


class SpatialContextTests(unittest.TestCase):
    setUp = helpers.SourceProfileTests.setUp
    importer = helpers.SourceProfileTests.importer
    trusted_state = helpers.SourceProfileTests.trusted_state

    def populate(self):
        for key in sorted(REQUIRED_CONTRACTS):
            self.importer(key).import_source(TID, key, self.extent)
        return SpatialContextService(self.store)

    def test_categories_provenance_relations_and_read_only_cli(self):
        service = self.populate()
        before = self.trusted_state(), self.store.events()
        result = service.build(TID)
        self.assertEqual(len(result['categories']), 6)
        self.assertEqual(len(result['categories']['bebouwing']), 2)
        self.assertEqual(len(result['objects']), 8)
        basis = SourceBasisService(self.store).build(TID)
        for field in ('relations', 'uncertainties'):
            self.assertEqual([{k:v for k,v in r.items() if k != 'provenance_refs'}
                              for r in result[field]], basis[field])
        for obj in result['objects']:
            for fact in obj['facts']:
                self.assertEqual(result['provenance'][fact['provenance_ref']]['record_ref'], obj['record_ref'])
        self.assertEqual(service.verify(result), result)
        cmd = [sys.executable, str(ROOT / 'bvc_ai.py'), '--data', self.temp.name,
               'spatial-context', TID, '--revision', result['revision_id']]
        run = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertEqual(json.loads(run.stdout), result)
        self.assertEqual((self.trusted_state(), self.store.events()), before)

    def test_holes_area_bounds_and_point_not_floor_area(self):
        service = self.populate()
        response = helpers.profile_response('BGT/wegdeel', identity='with-hole')
        data = json.loads(response.body)
        data['features'][0]['place'] = dict(type='Polygon', coordinates=[
            [[0,0],[10,0],[10,10],[0,10],[0,0]], [[2,2],[2,4],[4,4],[4,2],[2,2]]])
        self.importer('BGT/wegdeel', [replace(response, body=json.dumps(data).encode())]).import_source(
            TID, 'hole-snapshot', self.extent)
        result = service.build(TID)
        road = next(o for o in result['objects'] if o['record_ref'][0] == 'BGT/wegdeel')
        facts = {f['name']: f for f in road['facts']}
        self.assertEqual(facts['source_geometry_area']['value'], 96)
        self.assertEqual(facts['bounds']['value'], [0,0,10,10])
        vbo = next(o for o in result['objects'] if o['record_ref'][0] == 'BAG/verblijfsobject')
        self.assertFalse(any(f['name'] == 'source_geometry_area' for f in vbo['facts']))
        self.assertTrue(any(f.get('source_field') == 'oppervlakte' and f['value'] == 80 for f in vbo['facts']))

    def test_partial_stale_and_tampered_context_fail_closed(self):
        self.importer('BGT/pand').import_source(TID, 'BGT/pand', self.extent)
        service = SpatialContextService(self.store)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            service.build(TID)
        service = self.populate()
        result = service.build(TID)
        changed = deepcopy(result)
        changed['objects'][0]['facts'][0]['value'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'Changed'):
            service.verify(changed)
        self.importer('BGT/wegdeel', [helpers.profile_response('BGT/wegdeel', 'new')]).import_source(
            TID, 'new-snapshot', self.extent)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            service.verify(result)


class MeppelSpatialContextTests(unittest.TestCase):
    def test_accepted_meppel_archive_offline_unchanged(self):
        package = ROOT / 'docs/evidence/bag-api-bootstrap'
        manifest = json.loads((package / 'archive-manifest.json').read_text())
        archive = package / manifest['archive']
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), manifest['sha256'])
        temp_root = ROOT / '.tools/test-runs'
        temp_root.mkdir(parents=True, exist_ok=True)
        with ExitStack() as stack:
            for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
                stack.enter_context(patch(name, side_effect=AssertionError('OFFLINE NETWORK BLOCKED')))
            directory = Path(stack.enter_context(tempfile.TemporaryDirectory(dir=temp_root)))
            with zipfile.ZipFile(archive) as zipped:
                for name, digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(zipped.read(name)).hexdigest(), digest)
                payload = zipped.read('archive/state.sqlite3')
                old = json.loads(zipped.read('source-basis.json'))
            database = directory / 'state.sqlite3'
            database.write_bytes(payload)
            store = Store(directory)
            try:
                before = store.list(), store.events()
                basis = SourceBasisService(store).build(old['task_id'])
                self.assertEqual(basis, old)
                result = SpatialContextService(store).build(old['task_id'])
                self.assertEqual(len(result['objects']), len(basis['records']))
                self.assertEqual({tuple(o['record_ref']) for o in result['objects']},
                                 {tuple(r['record_ref']) for r in basis['records']})
                self.assertTrue(all(result['categories'].values()))
                originals = {tuple(r['record_ref']): json.loads(r['properties_json'])
                             for r in basis['records']}
                for obj in result['objects']:
                    props = originals[tuple(obj['record_ref'])]
                    attributes = {f['source_field']: f['value'] for f in obj['facts']
                                  if f['name'] == 'source_attribute'}
                    for field in ('fysiek_voorkomen', 'relatieve_hoogteligging', 'in_onderzoek'):
                        if props.get(field) is not None:
                            self.assertEqual(attributes[field], props[field])
                    for field, value in attributes.items():
                        self.assertEqual(value, props[field])
                self.assertEqual(result['basis_hash'], basis['basis_hash'])
                self.assertEqual(len(result['relations']), len(basis['relations']))
                self.assertEqual(len(result['uncertainties']), len(basis['uncertainties']))
                self.assertEqual((store.list(), store.events()), before)
                self.assertTrue(all(p['raw_response_hash'] for p in result['provenance']))
                print('\nMEPPEL_SPATIAL_CONTEXT ' + json.dumps(dict(
                    categories={k:len(v) for k,v in result['categories'].items()},
                    relations=dict(Counter(r['status'] for r in result['relations'])),
                    uncertainties=dict(Counter(u['reason'] for u in result['uncertainties'])),
                    context_hash=result['context_hash'])))
            finally:
                store.close()
            self.assertEqual(database.read_bytes(), payload)
