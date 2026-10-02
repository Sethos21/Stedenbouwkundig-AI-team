"""Offline A06 tests using a real validated A02 over synthetic source responses."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import test_source_profiles as helpers
from test_source_import import TID
from planological_fixtures import planological_fixture
from bvc_ai.application.source_basis import REQUIRED_CONTRACTS
from bvc_ai.application.spatial_context import SpatialContextService
from bvc_ai.application.planological_context import PlanologicalContextService, input_hash


class PlanologicalContextTests(unittest.TestCase):
    importer = helpers.SourceProfileTests.importer
    trusted_state = helpers.SourceProfileTests.trusted_state

    def setUp(self):
        helpers.SourceProfileTests.setUp(self)
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(name, side_effect=AssertionError('A06 OFFLINE ONLY'))
            blocker.start()
            self.addCleanup(blocker.stop)
        for key in sorted(REQUIRED_CONTRACTS):
            self.importer(key).import_source(TID, key, self.extent)
        self.spatial_service = SpatialContextService(self.store)
        self.spatial = self.spatial_service.build(TID)
        self.data = planological_fixture(self.spatial)
        self.service = PlanologicalContextService(self.store)
        self.digest = input_hash(self.data)

    def build(self, data=None):
        data = self.data if data is None else data
        return self.service.build(self.spatial, data, expected_input_hash=input_hash(data))

    def test_four_classifications_literal_sources_provenance_and_quantities(self):
        output = self.build()
        self.assertEqual([r['classification'] for r in output['rules']],
                         ['CONSTRAINT', 'STEERING', 'INFORMATION', 'UNCERTAINTY'])
        self.assertEqual(output['source_status'], 'TESTDATA')
        source = self.data['sources'][0]
        for i, (original, row) in enumerate(zip(source['rules'], output['rules'])):
            self.assertEqual(row['source_rule'], original)
            self.assertNotEqual(row['source_rule'], row['interpretation'])
            self.assertEqual(row['rule_identity'], [source['source_id'], original['rule_id']])
            provenance = row['provenance']
            self.assertEqual(provenance['source_hash'], input_hash(source))
            self.assertEqual(provenance['rule_hash'], input_hash(original))
            self.assertEqual(provenance['applicability_hash'], input_hash(original['applicability']))
            self.assertEqual(provenance['input_hash'], self.digest)
            self.assertEqual(provenance['a02_context_hash'], self.spatial['context_hash'])
            self.assertEqual(row['interpretation']['provenance_path'], f'rules/{i}/provenance')
            self.assertEqual(row['classification_provenance_path'], f'rules/{i}/provenance')
        self.assertEqual(output['rules'][0]['quantity'], dict(value=12, unit='m', operator='MAXIMUM'))
        self.assertIsNone(output['rules'][1]['quantity'])
        self.assertTrue(output['rules'][3]['uncertainties'])

    def test_applicability_retains_targets_and_a02_geometry_bindings(self):
        rows = self.build()['rules']
        self.assertEqual([r['applicability']['target']['kind'] for r in rows[:3]],
                         ['SOURCE_OBJECT', 'A02_GEOMETRY', 'FULL_ANALYSIS_SCOPE'])
        for row in rows:
            target = row['applicability']['target']
            ps = [self.spatial['provenance'][i] for i in row['provenance']['a02_provenance_refs']]
            self.assertTrue(ps)
            if target['kind'] == 'SOURCE_OBJECT':
                self.assertEqual([p['record_ref'] for p in ps], target['record_refs'])
            elif target['kind'] == 'A02_GEOMETRY':
                self.assertEqual([p['geometry_ref'] for p in ps], target['geometry_refs'])
            else:
                self.assertEqual(ps, self.spatial['provenance'])
        for status in ('DOES_NOT_APPLY', 'UNKNOWN'):
            changed = deepcopy(self.data)
            changed['sources'][0]['rules'][0]['applicability']['status'] = status
            row = self.build(changed)['rules'][0]
            self.assertEqual(row['applicability']['status'], status)
            self.assertEqual(row['classification'], 'UNCERTAINTY')
            self.assertIn('APPLICABILITY_' + status, [u['code'] for u in row['uncertainties']])

    def test_uncertainty_blocks_hard_constraints_and_ambitions_stay_soft(self):
        for mutation in ('draft', 'unknown_source', 'unclear', 'missing_basis', 'uncertainty', 'unknown_kind', 'indicative'):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                source = data['sources'][0]
                rule = source['rules'][0]
                if mutation == 'draft':
                    source['legal_status'] = 'DRAFT'
                elif mutation == 'unknown_source':
                    source['legal_status'] = 'UNKNOWN'
                elif mutation == 'unclear':
                    rule['certainty'] = 'UNCLEAR'
                elif mutation == 'missing_basis':
                    rule['applicability']['basis'] = ''
                elif mutation == 'uncertainty':
                    rule['uncertainties'] = ['TESTDATA: unresolved exception']
                elif mutation == 'indicative':
                    rule['structured']['quantity']['operator'] = 'INDICATIVE'
                else:
                    rule['structured']['kind'] = 'UNKNOWN'
                self.assertEqual(self.build(data)['rules'][0]['classification'], 'UNCERTAINTY')
        data = deepcopy(self.data)
        # Even a numeric policy target remains steering, never a hard constraint.
        data['sources'][0]['rules'][0]['structured']['kind'] = 'POLICY_AMBITION'
        self.assertEqual(self.build(data)['rules'][0]['classification'], 'STEERING')

    def test_read_only_deterministic_roundtrip_and_no_shared_mutable_output(self):
        before = deepcopy(self.spatial), deepcopy(self.data), self.trusted_state(), self.store.events()
        result = self.build()
        self.assertEqual(result, self.build())
        self.assertEqual(result, json.loads(json.dumps(result)))
        self.assertEqual(result['context_hash'], input_hash({k: v for k, v in result.items() if k != 'context_hash'}))
        self.assertEqual(self.service.verify(result, self.spatial, self.data,
                                             expected_input_hash=self.digest), result)
        self.assertEqual((self.spatial, self.data, self.trusted_state(), self.store.events()), before)
        result['rules'][0]['source_rule']['text'] = 'tampered'
        result['rules'][0]['applicability']['status'] = 'UNKNOWN'
        self.assertEqual((self.spatial, self.data), before[:2])
        self.assertEqual(self.build()['rules'][0]['source_rule']['text'],
                         self.data['sources'][0]['rules'][0]['text'])

    def test_tampered_input_and_output_fail_even_with_rehashed_output(self):
        result = self.build()
        changed = deepcopy(self.data)
        changed['sources'][0]['rules'][0]['text'] = 'TESTDATA: altered source'
        with self.assertRaisesRegex(ValueError, 'Changed planological input'):
            self.service.build(self.spatial, changed, expected_input_hash=self.digest)
        for field in ('classification', 'source_rule', 'applicability', 'provenance', 'quantity', 'interpretation'):
            with self.subTest(field=field):
                altered = deepcopy(result)
                altered['rules'][0][field] = 'tampered'
                altered['context_hash'] = input_hash({k: v for k, v in altered.items() if k != 'context_hash'})
                with self.assertRaisesRegex(ValueError, 'Changed planological context'):
                    self.service.verify(altered, self.spatial, self.data, expected_input_hash=self.digest)
        changed['input_revision'] = 'synthetic/v2'
        with self.assertRaisesRegex(ValueError, 'Changed planological context'):
            self.service.verify(result, self.spatial, changed, expected_input_hash=input_hash(changed))

    def test_numeric_type_tampering_with_original_hash_is_rejected(self):
        result = self.build()
        result['rules'][0]['quantity']['value'] = 12.0
        with self.assertRaisesRegex(ValueError, 'Changed planological context'):
            self.service.verify(result, self.spatial, self.data, expected_input_hash=self.digest)

    def test_stale_or_tampered_a02_fails_closed(self):
        altered = deepcopy(self.spatial)
        altered['objects'][0]['facts'][0]['value'] = 'invented'
        altered['context_hash'] = input_hash({k: v for k, v in altered.items() if k != 'context_hash'})
        data = planological_fixture(altered)
        with self.assertRaisesRegex(ValueError, 'Changed spatial context'):
            self.service.build(altered, data, expected_input_hash=input_hash(data))
        self.importer('BGT/wegdeel', [helpers.profile_response('BGT/wegdeel', 'new')]).import_source(
            TID, 'new-snapshot', self.extent)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.build()
        current = self.spatial_service.build(TID)
        with self.assertRaisesRegex(ValueError, 'Stale A02 binding'):
            self.service.build(current, self.data, expected_input_hash=self.digest)

    def test_final_a02_check_detects_revision_change_during_derivation(self):
        original = self.service._spatial.verify
        calls = []
        def verify(context):
            calls.append(1)
            if len(calls) == 2:
                self.importer('BGT/wegdeel', [helpers.profile_response('BGT/wegdeel', 'new')]).import_source(
                    TID, 'during-build', self.extent)
            return original(context)
        with patch.object(self.service._spatial, 'verify', side_effect=verify):
            with self.assertRaisesRegex(ValueError, 'Stale'):
                self.build()

    def test_invalid_schema_identities_origins_and_targets_fail_closed(self):
        def bad_cases():
            for field, value in [('source_status', 'LIVE'), ('format', 'OTHER'), ('sources', [])]:
                data = deepcopy(self.data)
                data[field] = value
                yield data
            for field, value in [('source_status', 'PROVIDER_RESPONSE'), ('legal_status', 'APPROVED')]:
                data = deepcopy(self.data)
                data['sources'][0][field] = value
                yield data
            data = deepcopy(self.data)
            data['sources'].append(deepcopy(data['sources'][0]))
            yield data
            data = deepcopy(self.data)
            data['sources'][0]['rules'].append(deepcopy(data['sources'][0]['rules'][0]))
            yield data
            for field, value in [('record_refs', [['BAG/pand', 'missing', 'invented']]),
                                 ('geometry_refs', ['invented']), ('kind', 'NEW_GEOMETRY'),
                                 ('coordinates', [1, 2])]:
                data = deepcopy(self.data)
                data['sources'][0]['rules'][0]['applicability']['target'][field] = value
                yield data
            data = deepcopy(self.data)
            data['sources'][0]['rules'][2]['applicability']['target']['scope_contracts'].pop()
            yield data
            for field, value in [('value', True), ('value', float('nan')), ('unit', ''), ('operator', 'GUESS')]:
                data = deepcopy(self.data)
                data['sources'][0]['rules'][0]['structured']['quantity'][field] = value
                yield data
            data = deepcopy(self.data)
            data['sources'][0]['rules'][0]['classification'] = 'CONSTRAINT'
            yield data
        for i, data in enumerate(bad_cases()):
            with self.subTest(case=i), self.assertRaises(ValueError):
                self.build(data)
