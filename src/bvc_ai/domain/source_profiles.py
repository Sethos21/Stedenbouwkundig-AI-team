"""Closed official source contracts. No caller-defined endpoints or geometry rules."""
from dataclasses import dataclass


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
    if not isinstance(properties.get('version'), str) or not properties['version'].strip():
        raise ValueError('BGT version required by official schema')
    for key in ('bronhouder', 'lokaal_id', 'status', 'in_onderzoek', 'functie',
                'fysiek_voorkomen', 'bag_pnd'):
        if key in properties and properties[key] is not None and not isinstance(properties[key], str):
            raise ValueError('BGT property type mismatch: ' + key)
