"""Synthetic official-relation cases only; no fetch, geometry inference or promotion."""
import copy
import json
import unittest
from unittest.mock import patch
from bvc_ai.application.source_basis import official_relations
from bvc_ai.domain.source_profiles import source_profile


def href(collection, identity):
    return source_profile('BAG/' + collection).items_url + '/' + identity


def record(collection, identity, **properties):
    return dict(source_contract='BAG/' + collection, source_id=identity,
                record_ref=['BAG/' + collection, 'synthetic-snapshot', identity],
                properties_json=json.dumps(dict(identificatie='registration-' + identity, **properties)))


class BagHrefTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE TEST'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_pand_href_and_literal_provenance(self):
        raw = href('verblijfsobject', 'vbo')
        rows = [record('pand', 'pand', **{'verblijfsobject.href':[raw]}), record('verblijfsobject','vbo')]
        before = copy.deepcopy(rows)
        relations, _ = official_relations(rows)
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]['status'], 'RESOLVED')
        self.assertEqual(relations[0]['field'], 'verblijfsobject.href')
        self.assertEqual(relations[0]['official_reference'], raw)
        self.assertEqual(relations[0]['target_refs'], [rows[1]['record_ref']])
        self.assertEqual(rows, before)

    def test_verblijfsobject_href(self):
        rows = [record('verblijfsobject','vbo', **{'pand.href':[href('pand','pand')]}),record('pand','pand')]
        relations, _ = official_relations(rows)
        self.assertEqual(relations[0]['status'], 'RESOLVED')
        self.assertEqual(relations[0]['field'], 'pand.href')

    def test_existing_attributes_and_official_attribute_urls(self):
        for raw in ('pand', href('pand','pand')):
            relations, _ = official_relations([record('verblijfsobject','vbo',pand=[raw]),record('pand','pand')])
            self.assertEqual(relations[0]['status'], 'RESOLVED')
            self.assertEqual(relations[0]['field'], 'pand')
            self.assertNotIn('official_references', relations[0])

    def test_equal_attribute_and_href_sets_deduplicate_and_preserve_both_fields(self):
        refs = [href('pand','pand'),href('pand','pand')]
        for attr in (['pand'],[href('pand','pand')],['pand','pand']):
            relations, _ = official_relations([record('verblijfsobject','vbo',pand=attr,**{'pand.href':refs}),record('pand','pand')])
            self.assertEqual(len(relations),1)
            self.assertEqual(relations[0]['status'],'RESOLVED')
            self.assertEqual({p['field'] for p in relations[0]['official_references']},{'pand','pand.href'})

    def test_conflicting_sets_block_entire_group_including_overlap(self):
        for attrs,refs in ((['other'],['pand']), (['pand','other'],['pand']), ([],['pand']), (['pand'],[])):
            rows=[record('verblijfsobject','vbo',pand=attrs,**{'pand.href':[href('pand',r) for r in refs]}),record('pand','pand'),record('pand','other')]
            relations,uncertainties=official_relations(rows)
            self.assertFalse(relations)
            conflicts=[u for u in uncertainties if u['reason']=='CONFLICTING_OFFICIAL_REFERENCES']
            self.assertEqual(len(conflicts),1)
            self.assertEqual(conflicts[0]['official_fields']['pand'],attrs)

    def test_malformed_href_blocks_group_no_attribute_fallback(self):
        for value in ({},True,href('pand','pand'),[None],[1],[''],[' '],
                      [href('pand','pand'),'not-a-url']):
            relations,uncertainties=official_relations([record('verblijfsobject','vbo',pand=['pand'],**{'pand.href':value}),record('pand','pand')])
            self.assertFalse(relations)
            self.assertTrue(any(u['reason']=='INVALID_OFFICIAL_HREF' for u in uncertainties))

    def test_unexpected_routes_and_encoded_identifiers_never_resolve(self):
        good=href('pand','pand')
        for value in (good.replace('https:','http:'),good.replace('api.pdok.nl','evil.invalid'),
                      good.replace('/pand/','/verblijfsobject/'),good+'?q=x',good+'#x',good+'/',
                      good.replace('/items/pand','/items/%70and'),good.replace('/items/pand','/items/../pand'),
                      good.replace('api.pdok.nl','user:pass@api.pdok.nl'),good.replace('/v2/','/v1/'),
                      good.replace('api.pdok.nl','api.pdok.nl:443'),good+'\\other',good+'\n'):
            with self.subTest(value=value):
                relations,uncertainties=official_relations([record('verblijfsobject','vbo',**{'pand.href':[value]}),record('pand','pand')])
                self.assertFalse(relations)
                self.assertEqual(uncertainties[0]['reason'],'INVALID_OFFICIAL_HREF')

    def test_null_href_is_explicit_source_absence(self):
        relations, uncertainties = official_relations([record('pand','pand', **{'verblijfsobject.href':None})])
        self.assertFalse(relations)
        self.assertEqual(uncertainties[0]['reason'], 'NO_OFFICIAL_REFERENCE_AVAILABLE')
        relations, _ = official_relations([record('verblijfsobject','vbo',pand=['pand'],**{'pand.href':None}),record('pand','pand')])
        self.assertEqual(relations[0]['status'], 'RESOLVED')

    def test_missing_identifier(self):
        for value in (href('pand',''), source_profile('BAG/pand').items_url):
            relations,uncertainties=official_relations([record('verblijfsobject','vbo',**{'pand.href':[value]})])
            self.assertFalse(relations)
            self.assertEqual(uncertainties[0]['reason'],'INVALID_OFFICIAL_HREF')

    def test_empty_href_array_has_no_usable_reference(self):
        relations,uncertainties=official_relations([record('verblijfsobject','vbo',**{'pand.href':[]})])
        self.assertFalse(relations)
        self.assertEqual(uncertainties[0]['reason'],'NO_OFFICIAL_REFERENCE_AVAILABLE')

    def test_unknown_target_remains_unresolved(self):
        relations,uncertainties=official_relations([record('verblijfsobject','vbo',**{'pand.href':[href('pand','outside-scope')]})])
        self.assertEqual(relations[0]['status'],'UNRESOLVED')
        self.assertEqual(relations[0]['target_refs'],[])
        self.assertEqual(uncertainties[0]['official_reference'],href('pand','outside-scope'))

    def test_href_uses_feature_id_never_registration_identity(self):
        target=record('pand','feature-id')
        relations,_=official_relations([record('verblijfsobject','vbo',**{'pand.href':[href('pand','registration-feature-id')]}),target])
        self.assertEqual(relations[0]['status'],'UNRESOLVED')

    def test_ambiguous_target_is_not_chosen(self):
        target=record('pand','pand');other=copy.deepcopy(target);other['record_ref'][1]='different-snapshot'
        relations,_=official_relations([record('verblijfsobject','vbo',**{'pand.href':[href('pand','pand')]}),target,other])
        self.assertEqual(relations[0]['status'],'AMBIGUOUS')
        self.assertEqual(len(relations[0]['target_refs']),2)

    def test_bgt_sentinel_remains_unresolved_even_with_matching_registration(self):
        source=dict(source_contract='BGT/pand',source_id='bgt',record_ref=['BGT/pand','test','bgt'],properties_json=json.dumps({'bag_pnd':'0000000000000000'}))
        target=record('pand','pand');target['properties_json']=json.dumps({'identificatie':'0000000000000000'})
        relations,_=official_relations([source,target])
        self.assertEqual(relations[0]['status'],'UNRESOLVED')
        self.assertFalse(relations[0]['target_refs'])

    def test_no_synthetic_inverse_created(self):
        source=record('verblijfsobject','vbo',**{'pand.href':[href('pand','pand')]})
        target=record('pand','pand')
        relations,uncertainties=official_relations([source,target])
        self.assertEqual(len(relations),1)
        self.assertEqual(relations[0]['source_ref'],source['record_ref'])
        self.assertTrue(any(u['reason']=='RECIPROCAL_REFERENCE_NOT_CONFIRMED' for u in uncertainties))

    def test_invalid_attribute_with_href_fails_closed(self):
        for value in ('pand',[None],['']):
            relations,uncertainties=official_relations([record('verblijfsobject','vbo',pand=value,**{'pand.href':[href('pand','pand')]}),record('pand','pand')])
            self.assertFalse(relations)
            self.assertEqual(uncertainties[0]['reason'],'INVALID_OFFICIAL_ATTRIBUTE')
