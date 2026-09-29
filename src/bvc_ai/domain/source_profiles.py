"""Closed official source contracts. No caller-defined endpoints or geometry rules."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SourceProfile:
    key: str | None
    dataset: str
    collection: str
    base_url: str
    geometry_type: str | None

    @property
    def collection_url(self):
        return self.base_url + '/collections/' + self.collection

    @property
    def items_url(self):
        return self.collection_url + '/items'

    @property
    def parser_version(self):
        return 'pdok-jsonfg-2d-v1' if self.key else 'pdok-bgt-jsonfg-page-v1'


BGT_COLLECTIONS = ('pand', 'wegdeel', 'ondersteunendwegdeel', 'waterdeel',
                   'begroeidterreindeel', 'onbegroeidterreindeel')
LEGACY = SourceProfile(None, 'BGT', 'pand', 'https://api.pdok.nl/lv/bgt/ogc/v1', None)
_PROFILES = {('BGT/' + c): SourceProfile('BGT/' + c, 'BGT', c,
             'https://api.pdok.nl/kadaster/bgt/ogc/v1',
             'MultiPolygon' if c == 'pand' else 'Polygon') for c in BGT_COLLECTIONS}

BAG_COLLECTIONS = ('pand', 'verblijfsobject')
_PROFILES.update({('BAG/' + c): SourceProfile('BAG/' + c, 'BAG', c,
                  'https://api.pdok.nl/kadaster/bag/ogc/v2',
                  'Polygon' if c == 'pand' else 'Point') for c in BAG_COLLECTIONS})


def source_profile(key=None):
    if key is None:
        return LEGACY
    if type(key) is not str or key not in _PROFILES:
        raise ValueError('Unknown official source contract')
    return _PROFILES[key]


def check_feature_contract(profile, properties, place):
    if profile.key is None:
        return  # Preserve the accepted 2C parser contract exactly.
    if place.get('type') != profile.geometry_type:
        raise ValueError('Geometry type does not match collection contract')
    if profile.dataset == 'BAG':
        identity = properties.get('identificatie')
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError('Explicit BAG registration identity required')
        for key in ('status', 'gebruiksdoel', 'hoofdadres_identificatie', 'postcode',
                    'openbare_ruimte_naam', 'huisletter', 'toevoeging', 'woonplaats_naam'):
            if key in properties and properties[key] is not None and not isinstance(properties[key], str):
                raise ValueError('BAG property type mismatch: ' + key)
        for key in ('bouwjaar', 'aantal_verblijfsobjecten', 'oppervlakte', 'huisnummer'):
            if key in properties and properties[key] is not None and (
                    type(properties[key]) not in (int, Decimal) or properties[key] < 0
                    or properties[key] != int(properties[key])):
                raise ValueError('BAG nonnegative integer required: ' + key)
        relation = 'verblijfsobject' if profile.collection == 'pand' else 'pand'
        if relation in properties and properties[relation] is not None:
            refs = properties[relation]
            if not isinstance(refs, list) or any(not isinstance(r, str) or not r.strip() for r in refs):
                raise ValueError('BAG explicit reference array required')
        return
    if not isinstance(properties.get('version'), str) or not properties['version'].strip():
        raise ValueError('BGT version required by official schema')
    for key in ('bronhouder', 'lokaal_id', 'status', 'in_onderzoek', 'functie',
                'fysiek_voorkomen', 'bag_pnd'):
        if key in properties and properties[key] is not None and not isinstance(properties[key], str):
            raise ValueError('BGT property type mismatch: ' + key)
