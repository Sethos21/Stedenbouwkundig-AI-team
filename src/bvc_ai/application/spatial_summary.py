"""Pure aggregations of existing A02 facts; no geometry or source reinterpretation."""
from collections import Counter
import json
from math import fsum

DISTRIBUTION_FIELDS = ('gebruiksdoel', 'fysiek_voorkomen', 'functie', 'status', 'bouwjaar')


def _literal_distribution(values):
    # Typed whole values: arrays stay arrays; no splitting, coercion or deduplication.
    counts = Counter(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                separators=(',', ':'), allow_nan=False) for value in values)
    return [dict(value=json.loads(value), count=counts[value]) for value in sorted(counts)]


def summarize(context):
    """Internal projection of a validated context, not a validation entrypoint.

    Source selectors refer to context.objects[].record_ref[0]; their facts carry
    the original provenance_ref. No combined BAG/BGT building count or area.
    """
    by_collection = {}
    for scope in sorted(context['scope'], key=lambda s: s['source_contract']):
        key = scope['source_contract']
        objects = sorted((o for o in context['objects'] if o['record_ref'][0] == key),
                         key=lambda o: tuple(o['record_ref']))
        facts = [f for o in objects for f in o['facts']]
        areas = [f['value'] for f in facts if f['name'] == 'source_geometry_area']
        attributes = {}
        for field in DISTRIBUTION_FIELDS:
            values = [f['value'] for f in facts
                      if f['name'] == 'source_attribute' and f['source_field'] == field]
            distribution = dict(present_count=len(values), absent_count=len(objects) - len(values),
                                values=_literal_distribution(values))
            if field == 'bouwjaar':
                years = [v for v in values if type(v) is int and v > 0]
                distribution['positive_integer_range'] = dict(
                    count=len(years), minimum=min(years) if years else None,
                    maximum=max(years) if years else None,
                    excluded_present_count=len(values) - len(years))
            attributes[field] = distribution
        by_collection[key] = dict(
            record_count=len(objects),
            source_geometry_area=dict(polygon_record_count=len(areas),
                                      sum_m2=fsum(areas) if areas else None),
            attributes=attributes,
            provenance_selector=dict(source_contract=key,
                                     input='objects[].facts; provenance_ref -> provenance'))
    categories = {}
    for category, refs in sorted(context['categories'].items()):
        counts = Counter(ref[0] for ref in refs)
        categories[category] = dict(collection_record_counts={
            key: counts[key] for key in sorted(counts)})
    return dict(
        method='A02_FACT_AGGREGATION_V1', basis_hash=context['basis_hash'],
        revision_id=context['revision_id'], by_collection=by_collection,
        by_category=categories,
        relations=dict(counting_unit='DIRECTED_OFFICIAL_REFERENCE_RECORD',
                       status_counts={status: sum(r['status'] == status for r in context['relations'])
                                      for status in ('RESOLVED', 'UNRESOLVED', 'AMBIGUOUS')},
                       provenance_selector='relations[].provenance_refs -> provenance'),
        semantics=[
            'COUNTS_ARE_SOURCE_RECORDS_NOT_UNIQUE_REAL_WORLD_OBJECTS',
            'NO_CROSS_COLLECTION_AREA_TOTALS',
            'AREA_SUM_IS_ARITHMETIC_SUM_OF_FULL_SOURCE_POLYGONS_WITH_HOLES_NOT_UNION_OR_SCOPE_COVERAGE',
            'NO_POLYGON_FACTS_MEANS_NULL_AREA_NOT_ZERO',
            'ATTRIBUTE_BUCKETS_PRESERVE_WHOLE_LITERAL_TYPED_VALUES',
            'ABSENT_ATTRIBUTES_ARE_NOT_INFERRED',
            'YEAR_RANGE_USES_POSITIVE_INTEGER_LITERALS_ONLY_OTHER_VALUES_REMAIN_IN_DISTRIBUTION'])
