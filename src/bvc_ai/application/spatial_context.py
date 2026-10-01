"""Deterministic, read-only A02 facts derived from the validated source basis."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from shapely.geometry import shape

from bvc_ai.application.source_basis import SourceBasisService
from bvc_ai.application.spatial_summary import summarize
from bvc_ai.infrastructure.source_store import SourceStore

CATEGORIES = {
    'BGT/pand': 'bebouwing', 'BAG/pand': 'bebouwing',
    'BAG/verblijfsobject': 'verblijfsobjecten',
    'BGT/wegdeel': 'wegen_verharding',
    'BGT/ondersteunendwegdeel': 'wegen_verharding',
    'BGT/begroeidterreindeel': 'groen_begroeid_terrein',
    'BGT/onbegroeidterreindeel': 'onbegroeid_terrein',
    'BGT/waterdeel': 'water',
}
# Only literal descriptive attributes; no free-form interpretation or LLM.
ATTRIBUTES = ('identificatie', 'lokaal_id', 'status', 'plus_status', 'bouwjaar',
              'gebruiksdoel', 'oppervlakte', 'aantal_verblijfsobjecten',
              'functie', 'plus_functie', 'fysiek_voorkomen', 'plus_fysiek_voorkomen',
              'type', 'plus_type', 'relatieve_hoogteligging', 'op_talud',
              'in_onderzoek', 'geconstateerd')


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class SpatialContextService:
    """Local trusted reader; downstream agents receive JSON, never this service/store.

    The basis validates immutable source records and geometry. A final basis check
    rejects a changed active revision during derivation. No publication/approval.
    """
    def __init__(self, store):
        self._basis = SourceBasisService(store)
        self._sources = SourceStore(store)

    def build(self, task_id, *, expected_revision=None):
        basis = self._basis.build(task_id, expected_revision=expected_revision)
        sources = {s['source_contract']: s for s in basis['sources']}
        objects, provenance = [], []
        provenance_ids = {}
        for record in basis['records']:
            key = record['source_contract']
            if key not in CATEGORIES:
                raise ValueError('Unsupported spatial source contract')
            geometry = self._sources.geometry(record['geometry_ref'])
            data = json.loads(geometry.geometry_json)
            spatial = shape(data)
            pid = len(provenance)
            provenance_ids[tuple(record['record_ref'])] = pid
            provenance.append(dict(
                record_ref=record['record_ref'], origin=record['origin'],
                raw_response_hash=record['raw_response_hash'],
                snapshot_manifest_hash=sources[key]['manifest_hash'],
                import_revision_id=sources[key]['import_revision_id'],
                geometry_ref=geometry.geometry_ref,
                geometry_structural_hash=geometry.geometry_structural_hash,
                crs=asdict(geometry.crs_metadata)))
            facts = []

            def fact(name, value, method, field=None, unit=None):
                facts.append(dict(name=name, value=value, method=method, provenance_ref=pid,
                                  **({'source_field': field} if field else {}),
                                  **({'unit': unit} if unit else {})))

            fact('category', CATEGORIES[key], 'SOURCE_COLLECTION_MAPPING_V1')
            fact('geometry_type', data['type'], 'SOURCE_GEOMETRY_TYPE')
            fact('bounds', list(spatial.bounds), 'SOURCE_GEOMETRY_ENVELOPE', unit='metres')
            if data['type'] == 'Point':
                fact('position', data['coordinates'], 'SOURCE_COORDINATES', unit='metres')
            elif data['type'] in ('Polygon', 'MultiPolygon'):
                fact('source_geometry_area', spatial.area, 'PLANAR_AREA_WITH_HOLES', unit='m2')
            props = json.loads(record['properties_json'])
            # Preserve supplied code-system and absence indicators alongside values.
            fields = [name for field in ATTRIBUTES
                      for name in (field, field + '_codespace', field + '_leeg')]
            for field in fields:
                if field in props and props[field] is not None:
                    fact('source_attribute', props[field], 'LITERAL_SOURCE_ATTRIBUTE', field=field)
            objects.append(dict(record_ref=record['record_ref'], facts=facts))

        def evidence(row, source_key):
            refs = [row[source_key]] + row.get('target_refs', [])
            if 'target_ref' in row:
                refs.append(row['target_ref'])
            return dict(deepcopy(row), provenance_refs=[provenance_ids[tuple(r)] for r in refs])

        result = dict(
            format='BVC_A02_SPATIAL_CONTEXT_V1', task_id=task_id,
            revision_id=basis['revision_id'], basis_hash=basis['basis_hash'],
            source_status=basis['source_status'], complete=basis['complete'],
            scope=[dict(source_contract=key,
                        fetch_extent=asdict(self._sources.snapshot(s['snapshot_id']).fetch_extent))
                   for key, s in sorted(sources.items())],
            categories={category: [o['record_ref'] for o in objects
                                   if CATEGORIES[o['record_ref'][0]] == category]
                        for category in sorted(set(CATEGORIES.values()))},
            objects=objects, provenance=provenance,
            relations=[evidence(r, 'source_ref') for r in basis['relations']],
            uncertainties=[evidence(u, 'record_ref') for u in basis['uncertainties']],
            limitations=[
                'FETCH_EXTENT_IS_ANALYSIS_SCOPE_NOT_PROJECT_BOUNDARY',
                'COMPLETE_MEANS_REQUIRED_SOURCE_COLLECTIONS_NOT_REAL_WORLD_COMPLETENESS',
                'POINT_IN_TIME_CONSISTENCY_NOT_GUARANTEED',
                'BAG_AND_BGT_RECORDS_NOT_DEDUPLICATED',
                'AREAS_ARE_FULL_SOURCE_GEOMETRIES_NOT_CLIPPED_OR_UNIONED',
                'ROAD_CATEGORY_DOES_NOT_ASSERT_PAVING',
                'MISSING_ATTRIBUTES_UNKNOWN_NOT_INFERRED',
                'NO_DESIGN_POLICY_ENVIRONMENT_OR_SUITABILITY_CONCLUSIONS'],
            interpretation='FACTS_AND_EXPLICIT_OFFICIAL_REFERENCES; NO_DESIGN_OR_POLICY')
        self._basis.verify(basis)
        # JSON-native arrays also in the Python API: identical after CLI round-trip.
        result = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
        result['summary'] = summarize(result)
        result['context_hash'] = _hash(result)
        return result

    def verify(self, context):
        current = self.build(context['task_id'], expected_revision=context['revision_id'])
        if current != context:
            raise ValueError('Changed spatial context')
        return current
