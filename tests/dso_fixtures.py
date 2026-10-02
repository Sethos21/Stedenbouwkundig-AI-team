"""Synthetic DSO discovery metadata; no credentials or official source captures."""
from bvc_ai.adapters.dso_discovery import ENDPOINT


def discovery_page():
    return {
        '_embedded': {'documenten': [{
            'identificatie': '/akn/nl/act/gm0000/2026/test',
            'uriIdentificatie': '_akn_nl_act_gm0000_2026_test',
            'versie': 1, 'titel': 'TESTDATA synthetic plan', 'type': 'Omgevingsplan',
            'aangeleverdDoorEen': {'bestuurslaag': 'GEMEENTE', 'code': 'gm0000', 'naam': 'TESTDATA'},
            'geometrieIdentificaties': ['TESTDATA-geometry-reference'],
            'heeftVectorTiles': False, 'geldigVanaf': '2026-01-01',
            'beschikbaarVanaf': '2026-01-01T00:00:00Z',
            'omgevingsdocumentMetadata': {
                'expressionId': '/akn/nl/act/gm0000/2026/test/nld@2026-01-01;1',
                'isBesluit': False, 'isOntwerp': False, 'isToekomstig': False,
                'publicatiedatum': '2026-01-01',
                'publicatieUrl': 'https://example.invalid/TESTDATA',
            },
            '_links': {'self': {'href': ENDPOINT + '/TESTDATA'}},
        }]},
        '_links': {'self': {'href': ENDPOINT}},
        'page': {'number': 0, 'size': 200, 'totalElements': 1, 'totalPages': 1},
    }


def imro_document():
    return dict(
        identificatie='NL.IMRO.0000.TESTDATA-0001', uriIdentificatie='NL.IMRO.0000.TESTDATA-0001',
        versie=1, titel='TESTDATA IMRO', type='bestemmingsplan',
        aangeleverdDoorEen=dict(bestuurslaag='GEMEENTE', code='gm0000', naam='TESTDATA'),
        geometrieIdentificaties=[], heeftVectorTiles=False,
        beschikbaarVanaf='2026-01-01T00:00:00Z',
        imroDocumentMetadata=dict(bekendmakingen=[], beroepEnBezwaar='nee', heeftPlankaart=False,
                                 imroVersie='IMRO2012', isHistorisch=False, isTamPlan=False,
                                 onderdelen=[], ondergronden=[], regelStatus=None,
                                 planstatusInfo=dict(datum='2026-01-01', planstatus='vastgesteld')),
        _links=dict(self=dict(href=ENDPOINT + '/TESTDATA')))
