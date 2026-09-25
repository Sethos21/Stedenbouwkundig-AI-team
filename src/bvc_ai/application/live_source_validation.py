"""Trusted Phase 6 evidence checks, shared by import and offline replay."""
from dataclasses import replace
import json

from bvc_ai.adapters.pdok_bgt import JSON_FG, RD_URI, _continuation
from bvc_ai.adapters.pdok_live import BBOX, validate_live_request
from bvc_ai.adapters.source_transport import ResponseOrigin
from bvc_ai.domain.sources import GeometryRole, FetchExtent, CRSMetadata, GeometryRecord
from bvc_ai.domain.source_hashing import strict_json, geometry_structural_hash, CANONICALIZATION_VERSION
from bvc_ai.domain.geometry_validation import validate_geometry_record

LIVE_PROFILE = 'PDOK_PAND_MASTENBROEKWEG_MINIMAL_PROOF'
PURPOSE = 'MILESTONE_2C_MINIMAL_PROOF'
ANALYSIS_ORIGIN = 'USER_SUPPLIED_TESTCASE'


def validate_live_analysis(analysis, extent):
    bounds = tuple(map(float, BBOX.split(',')))
    x1, y1, x2, y2 = bounds
    expected = {'type': 'Polygon', 'coordinates': [[[x1, y1], [x2, y1],
                 [x2, y2], [x1, y2], [x1, y1]]]}
    provenance = json.loads(analysis.provenance_json)
    if (extent.bbox != bounds or extent.crs != 'EPSG:28992'
            or analysis.geometry_ref != extent.analysis_geometry_ref
            or analysis.role != GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY
            or json.loads(analysis.geometry_json) != expected
            or provenance.get('purpose') != PURPOSE
            or provenance.get('source_status') != ANALYSIS_ORIGIN):
        raise ValueError('Exact user-supplied Mastenbroekweg testcase geometry required')
    validate_geometry_record(analysis, source_crs=extent.crs)


def validate_live_capture(capture, expected_url, *, replay=False):
    # Replay has no outgoing headers in the Phase 5 archive. This fixed Accept
    # is used solely to check URL scope, never asserted as archived evidence.
    request = replace(capture.request, headers=(('Accept', JSON_FG),)) if replay else capture.request
    validate_live_request(request)
    capture.raw.__post_init__()
    capture.response.__post_init__()
    if (capture.request.url != expected_url
            or capture.response.origin != ResponseOrigin.PROVIDER_RESPONSE
            or capture.raw.body != capture.response.body):
        raise ValueError('Live capture origin/bytes/request chain mismatch')


def validate_live_fetch(fetched, adapter, extent, analysis, limit):
    validate_live_analysis(analysis, extent)
    expected_url = adapter.build_request(extent, limit=limit).url
    pages, features, geometries = [], [], []
    reported_totals = []
    for capture in fetched.captures:
        validate_live_capture(capture, expected_url)
        if capture.response.status == 429 or 500 <= capture.response.status <= 599:
            continue
        parsed = adapter._parse(capture, fetched.pages[0].snapshot_id, limit)
        document = strict_json(capture.raw.body.decode('utf-8'))
        if 'numberMatched' in document:
            reported_totals.append(document['numberMatched'])
        number = len(pages) + 1
        outgoing = parsed.page.next_url
        expected_url = _continuation(outgoing, capture.request.url) if outgoing is not None else None
        pages.append(replace(parsed.page, page_number=number, next_url=expected_url))
        features.extend(replace(f, page_number=number) for f in parsed.features)
        geometries.extend(parsed.geometries)
    if (expected_url is not None or tuple(pages) != fetched.pages
            or tuple(features) != fetched.features or tuple(geometries) != fetched.geometries
            or any(total != len(features) for total in reported_totals)):
        raise ValueError('Live parsing/query completeness evidence mismatch')


def mastenbroekweg_analysis():
    bounds = tuple(map(float, BBOX.split(',')))
    extent = FetchExtent(bounds, 'EPSG:28992', 'Mastenbroekweg/testcase')
    x1, y1, x2, y2 = bounds
    payload = json.dumps({'type': 'Polygon', 'coordinates': [[[x1,y1],[x2,y1],
                         [x2,y2],[x1,y2],[x1,y1]]]})
    crs = CRSMetadata('EPSG:28992', ('easting','northing'), 2, 'metres',
                      json.dumps({'source_status': ANALYSIS_ORIGIN, 'crs': RD_URI}))
    analysis = GeometryRecord(extent.analysis_geometry_ref, payload, crs,
        geometry_structural_hash(payload, crs), CANONICALIZATION_VERSION,
        GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY,
        json.dumps({'source_status': ANALYSIS_ORIGIN, 'purpose': PURPOSE,
                    'address': 'Mastenbroekweg 2, 6006 PT Weert, Nederland',
                    'user_supplied_bag_centroid_rd': [176742.301, 360855.561],
                    'boundary_status': 'NOT_A_PROJECT_PROPERTY_CADASTRAL_DESIGN_OR_POLICY_BOUNDARY'}))
    return extent, analysis
