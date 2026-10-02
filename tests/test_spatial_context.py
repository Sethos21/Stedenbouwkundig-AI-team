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
from bvc_ai.application.spatial_summary import summarize

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
        self.assertEqual(result['summary']['by_collection']['BGT/wegdeel']['source_geometry_area']['sum_m2'], 96)
        self.assertIsNone(result['summary']['by_collection']['BAG/verblijfsobject']['source_geometry_area']['sum_m2'])
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
        changed['summary']['by_collection']['BAG/pand']['record_count'] += 1
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
                summary = result['summary']
                self.assertEqual(summary['basis_hash'], basis['basis_hash'])
                expected_counts = Counter(r['source_contract'] for r in basis['records'])
                self.assertEqual({k:v['record_count'] for k,v in summary['by_collection'].items()},
                                 dict(expected_counts))
                self.assertEqual(summary['by_category']['bebouwing'], dict(collection_record_counts={
                    k: expected_counts[k] for k in ('BAG/pand', 'BGT/pand')}))
                self.assertEqual(summary['relations']['status_counts'],
                                 dict(RESOLVED=936, UNRESOLVED=13, AMBIGUOUS=0))
                for key, group in summary['by_collection'].items():
                    values = [props['bouwjaar'] for ref, props in originals.items()
                              if ref[0] == key and props.get('bouwjaar') is not None]
                    year_range = group['attributes']['bouwjaar']['positive_integer_range']
                    years = [v for v in values if type(v) is int and v > 0]
                    self.assertEqual(year_range['minimum'], min(years) if years else None)
                    self.assertEqual(year_range['maximum'], max(years) if years else None)
                    self.assertEqual(group['attributes']['bouwjaar']['present_count'], len(values))
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


class SpatialSummaryTests(unittest.TestCase):
    def test_literal_distributions_separate_registries_empty_and_deterministic(self):
        def obj(key, identity, area=None, **attrs):
            facts = [dict(name='source_attribute', source_field=k, value=v) for k,v in attrs.items()]
            if area is not None:
                facts.append(dict(name='source_geometry_area', value=area))
            return dict(record_ref=[key, 'snapshot', identity], facts=facts)
        objects = [obj('BAG/pand', 'a', 96, bouwjaar=2000, gebruiksdoel=['woonfunctie','kantoorfunctie']),
                   obj('BAG/pand', 'b', 4, bouwjaar=0, gebruiksdoel=['woonfunctie','kantoorfunctie']),
                   obj('BAG/pand', 'c', 10, bouwjaar='1990', status=True),
                   obj('BAG/pand', 'd', 20, bouwjaar=2020, status=1),
                   obj('BAG/pand', 'e', 30, bouwjaar=True, status='1'),
                   obj('BAG/pand', 'f', 40), obj('BGT/pand', 'g', 200)]
        context = dict(objects=objects, basis_hash='bound-hash', revision_id='A02/v1',
                       scope=[dict(source_contract=k) for k in ('BAG/pand', 'BGT/pand', 'BGT/waterdeel')],
                       categories=dict(bebouwing=[o['record_ref'] for o in objects], water=[]),
                       relations=[dict(status=s) for s in ('RESOLVED','RESOLVED','UNRESOLVED','AMBIGUOUS')])
        before = deepcopy(context)
        result = summarize(context)
        self.assertEqual(context, before)
        self.assertEqual(result['by_category']['bebouwing'],
                         dict(collection_record_counts={'BAG/pand':6, 'BGT/pand':1}))
        bag = result['by_collection']['BAG/pand']
        self.assertEqual(bag['source_geometry_area']['sum_m2'], 200)
        self.assertEqual(result['by_collection']['BGT/pand']['source_geometry_area']['sum_m2'], 200)
        self.assertIsNone(result['by_collection']['BGT/waterdeel']['source_geometry_area']['sum_m2'])
        self.assertEqual(bag['attributes']['gebruiksdoel'], dict(present_count=2, absent_count=4,
            values=[dict(value=['woonfunctie','kantoorfunctie'], count=2)]))
        self.assertEqual(len(bag['attributes']['status']['values']), 3)
        self.assertEqual(bag['attributes']['bouwjaar']['positive_integer_range'],
                         dict(count=2, minimum=2000, maximum=2020, excluded_present_count=3))
        self.assertEqual(result['relations']['status_counts'], dict(RESOLVED=2, UNRESOLVED=1, AMBIGUOUS=1))
        context['objects'].reverse()
        context['scope'].reverse()
        context['relations'].reverse()
        self.assertEqual(summarize(context), result)