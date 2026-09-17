"""Offline synthetic TESTDATA only; no PDOK payloads or location claims."""
import copy
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256

import numpy
import shapely

from bvc_ai.domain.sources import (
    CRSMetadata, FetchExtent, GeometryRecord, GeometryRole, RawResponse,
    SourceSnapshot, SourcePage, SourceFeature, ImportStatus, PointInTimeConsistency,
)
from bvc_ai.domain.geometry_validation import (
    VALIDATOR_VERSION, validate_crs, validate_geometry, validate_geometry_record,
)
from bvc_ai.domain.source_hashing import (
    CANONICALIZATION_VERSION, canonical_bytes, geometry_structural_hash,
    raw_response_hash, snapshot_manifest_hash, strict_json,
)
from bvc_ai.domain.source_validation import validate_completeness

PROVENANCE = '{"source_status":"TESTDATA","fixture":"synthetic phase2; no location claim"}'
RD = CRSMetadata("EPSG:28992", ("easting", "northing"), 2, "metres",
                 "Synthetic explicit CRS declaration; not an official response")
SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[2, 2], [2, 4], [4, 4], [4, 2], [2, 2]]
SECOND = [[20, 0], [30, 0], [30, 10], [20, 10], [20, 0]]


def js(value):
    return json.dumps(value, separators=(",", ":"))


def geometry(kind="Point", coordinates=None, *, crs=RD, ref="synthetic/geometry"):
    if coordinates is None:
        coordinates = [1, 2]
    payload = js({"type": kind, "coordinates": coordinates})
    return GeometryRecord(ref, payload, crs, geometry_structural_hash(payload, crs),
                          CANONICALIZATION_VERSION, GeometryRole.SOURCE_GEOMETRY,
                          PROVENANCE)


class GeometryTests(unittest.TestCase):
    def invalid(self, kind, coordinates):
        with self.assertRaises(ValueError):
            validate_geometry(js({"type": kind, "coordinates": coordinates}))

    def test_null_geometry(self):
        with self.assertRaises(ValueError):
            validate_geometry("null")

    def test_null_input(self):
        with self.assertRaises(ValueError):
            validate_geometry(None)

    def test_empty_geometry(self):
        for kind in ("Point", "LineString", "Polygon", "MultiPolygon"):
            with self.subTest(kind=kind):
                self.invalid(kind, [])

    def test_nan(self):
        self.invalid("Point", [float("nan"), 2])

    def test_infinity(self):
        for value in (float("inf"), -float("inf")):
            self.invalid("Point", [value, 2])

    def test_numeric_overflow(self):
        with self.assertRaises(ValueError):
            validate_geometry('{"type":"Point","coordinates":[1e999,2]}')

    def test_numeric_underflow(self):
        with self.assertRaises(ValueError):
            validate_geometry('{"type":"Point","coordinates":[1e-999,2]}')

    def test_boolean_and_string_coordinates(self):
        for value in (True, False, "1", None):
            self.invalid("Point", [value, 2])

    def test_unsupported_type(self):
        for kind in ("MultiPoint", "GeometryCollection", "polygon", None, []):
            self.invalid(kind, [1, 2])

    def test_wrong_nesting(self):
        for kind, coords in (("Point", [[1, 2]]), ("LineString", [1, 2]),
                             ("Polygon", SQUARE), ("MultiPolygon", [SQUARE])):
            self.invalid(kind, coords)

    def test_too_short_linestring(self):
        self.invalid("LineString", [[1, 2]])

    def test_collapsed_linestring(self):
        self.invalid("LineString", [[1, 2], [1, 2]])

    def test_three_dimensional_coordinate_rejected(self):
        self.invalid("Point", [1, 2, 3])

    def test_unclosed_ring(self):
        self.invalid("Polygon", [SQUARE[:-1]])

    def test_too_short_ring(self):
        self.invalid("Polygon", [[[0, 0], [1, 1], [0, 0]]])

    def test_self_intersection(self):
        self.invalid("Polygon", [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]])

    def test_hole_outside_shell(self):
        self.invalid("Polygon", [SQUARE, SECOND])

    def test_intersecting_holes(self):
        self.invalid("Polygon", [SQUARE, HOLE, HOLE])

    def test_hole_crosses_shell(self):
        self.invalid("Polygon", [SQUARE, [[8, 2], [12, 2], [12, 4], [8, 4], [8, 2]]])

    def test_invalid_multipolygon_overlap(self):
        self.invalid("MultiPolygon", [[SQUARE], [SQUARE]])

    def test_multipolygon_empty_member(self):
        self.invalid("MultiPolygon", [[SQUARE], []])

    def test_valid_point(self):
        self.assertEqual(validate_geometry_record(geometry()).geometry_type, "Point")

    def test_valid_linestring(self):
        self.assertEqual(validate_geometry_record(geometry("LineString", [[0, 0], [1, 2]])).geometry_type, "LineString")

    def test_valid_polygon_with_hole(self):
        self.assertEqual(validate_geometry_record(geometry("Polygon", [SQUARE, HOLE])).geometry_type, "Polygon")

    def test_valid_multipolygon(self):
        self.assertEqual(validate_geometry_record(geometry("MultiPolygon", [[SQUARE, HOLE], [SECOND]])).geometry_type, "MultiPolygon")

    def test_source_is_not_rewritten(self):
        record = geometry("Polygon", [list(reversed(SQUARE)), HOLE])
        before = copy.deepcopy(record)
        result = validate_geometry_record(record)
        self.assertEqual(record, before)
        self.assertEqual(result.geos_version, shapely.geos_version_string)
        self.assertFalse(hasattr(result, "promote"))

    def test_invalid_source_is_not_repaired(self):
        record = geometry("Polygon", [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]])
        before = copy.deepcopy(record)
        with self.assertRaises(ValueError):
            validate_geometry_record(record)
        self.assertEqual(record, before)

    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError):
            validate_geometry('{"type":"LineString","type":"Point","coordinates":[1,2]}')

    def test_extra_geometry_members(self):
        with self.assertRaises(ValueError):
            validate_geometry('{"type":"Point","coordinates":[1,2],"crs":"EPSG:28992"}')

    def test_geometry_hash_mismatch(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_geometry_record(replace(geometry(), geometry_structural_hash="0" * 64))

    def test_unknown_canonicalization_version(self):
        with self.assertRaises(ValueError):
            validate_geometry_record(replace(geometry(), canonicalization_version="future"))

    def test_pinned_engine_imports(self):
        self.assertEqual(shapely.__version__, "2.1.2")
        self.assertEqual(numpy.__version__, "2.2.6")
        self.assertTrue(shapely.geos_version_string)


class CRSTests(unittest.TestCase):
    def test_missing_crs(self):
        with self.assertRaises(ValueError):
            validate_crs(None)
        with self.assertRaises(ValueError):
            replace(RD, crs="")

    def test_wrong_crs(self):
        with self.assertRaises(ValueError):
            validate_crs(replace(RD, crs="EPSG:4326"))

    def test_crs84(self):
        with self.assertRaises(ValueError):
            validate_crs(replace(RD, crs="OGC:CRS84"))

    def test_axis_order_swapped(self):
        with self.assertRaises(ValueError):
            validate_crs(replace(RD, axis_order=("northing", "easting")))

    def test_ambiguous_xy_metadata(self):
        with self.assertRaises(ValueError):
            validate_crs(replace(RD, axis_order=("x", "y")))

    def test_wrong_units(self):
        for units in ("degrees", "feet", "metre", "m"):
            with self.assertRaises(ValueError):
                validate_crs(replace(RD, units=units))

    def test_wrong_dimension(self):
        with self.assertRaises(ValueError):
            replace(RD, dimension=3)
        with self.assertRaises(ValueError):
            replace(RD, dimension=True)

    def test_missing_crs_evidence(self):
        with self.assertRaises(ValueError):
            replace(RD, evidence=" ")

    def test_explicit_aliases(self):
        for crs in ("epsg:28992", "urn:ogc:def:crs:EPSG::28992",
                    "http://www.opengis.net/def/crs/EPSG/0/28992",
                    "https://www.opengis.net/def/crs/EPSG/0/28992"):
            self.assertEqual(validate_crs(replace(RD, crs=crs)), "EPSG:28992")

    def test_no_coordinate_based_crs_guessing(self):
        # RD-like numbers do not rescue an explicit WGS84 declaration.
        with self.assertRaises(ValueError):
            validate_geometry_record(geometry(coordinates=[150000, 400000],
                                             crs=replace(RD, crs="EPSG:4326")))

    def test_wrong_label_detected_from_response_evidence(self):
        with self.assertRaises(ValueError):
            validate_geometry_record(geometry(), source_crs="OGC:CRS84")

    def test_numeric_swap_alone_is_not_claimed_detectable(self):
        # Neither of these is asserted to be a real geographical location.
        self.assertEqual(validate_geometry_record(geometry(coordinates=[1, 2])).canonical_crs, "EPSG:28992")
        self.assertEqual(validate_geometry_record(geometry(coordinates=[2, 1])).canonical_crs, "EPSG:28992")

    def test_small_numbers_do_not_trigger_inference(self):
        self.assertEqual(validate_geometry_record(geometry(coordinates=[5, 52])).canonical_crs, "EPSG:28992")


class HashTests(unittest.TestCase):
    def test_identical_geometry(self):
        self.assertEqual(geometry().geometry_structural_hash, geometry().geometry_structural_hash)

    def test_coordinate_change(self):
        self.assertNotEqual(geometry().geometry_structural_hash,
                            geometry(coordinates=[1, 3]).geometry_structural_hash)

    def test_coordinate_order_change(self):
        self.assertNotEqual(geometry("LineString", [[0, 0], [1, 2]]).geometry_structural_hash,
                            geometry("LineString", [[1, 2], [0, 0]]).geometry_structural_hash)

    def test_ring_rotation_changes_structural_identity(self):
        rotated = SQUARE[1:-1] + [SQUARE[0], SQUARE[1]]
        self.assertNotEqual(geometry("Polygon", [SQUARE]).geometry_structural_hash,
                            geometry("Polygon", [rotated]).geometry_structural_hash)

    def test_other_crs_changes_hash_without_making_it_valid(self):
        other = geometry(crs=replace(RD, crs="EPSG:4326"))
        self.assertNotEqual(geometry().geometry_structural_hash, other.geometry_structural_hash)
        with self.assertRaises(ValueError):
            validate_geometry_record(other)

    def test_crs_alias_same_hash(self):
        self.assertEqual(geometry().geometry_structural_hash,
                         geometry(crs=replace(RD, crs="urn:ogc:def:crs:EPSG::28992")).geometry_structural_hash)

    def test_run_timestamp_not_geometry_identity(self):
        record = replace(geometry(), provenance_json='{"run_timestamp":"2099-01-01"}')
        self.assertEqual(validate_geometry_record(record).structural_hash,
                         validate_geometry_record(geometry()).structural_hash)

    def test_geometry_type_and_nesting_part_of_identity(self):
        point = geometry().geometry_structural_hash
        nested = geometry("LineString", [[1, 2]]).geometry_structural_hash
        self.assertNotEqual(point, nested)
        self.assertNotEqual(geometry("Polygon", [SQUARE]).geometry_structural_hash,
                            geometry("MultiPolygon", [[SQUARE]]).geometry_structural_hash)

    def test_decimal_serialization(self):
        left = '{"type":"Point","coordinates":[1.00,2e0]}'
        right = '{ "coordinates": [1,2.0], "type":"Point" }'
        self.assertEqual(geometry_structural_hash(left, RD), geometry_structural_hash(right, RD))
        self.assertEqual(canonical_bytes(Decimal("-0.00")), canonical_bytes(0))

    def test_precision_not_silently_rounded_in_hash(self):
        left = '{"type":"Point","coordinates":[1.00000000000000001,2]}'
        right = '{"type":"Point","coordinates":[1.00000000000000002,2]}'
        self.assertNotEqual(geometry_structural_hash(left, RD), geometry_structural_hash(right, RD))

    def test_typed_serialization_no_number_string_collision(self):
        self.assertNotEqual(canonical_bytes(1), canonical_bytes("1"))
        self.assertNotEqual(canonical_bytes(True), canonical_bytes(1))
        self.assertNotEqual(canonical_bytes({"a": 1}), canonical_bytes([["a", 1]]))

    def test_canonical_known_bytes_and_raw_sha256(self):
        self.assertEqual(canonical_bytes({"a": Decimal("1.20")}),
                         b'["object",[["a",["number","12e-1"]]]]')
        self.assertEqual(raw_response_hash(b"abc"),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_raw_byte_change(self):
        self.assertNotEqual(raw_response_hash(b"abc"), raw_response_hash(b"abc\n"))
        with self.assertRaises(ValueError):
            raw_response_hash("abc")

    def test_nonfinite_canonical_values(self):
        for number in (float("nan"), float("inf"), Decimal("NaN")):
            with self.assertRaises(ValueError):
                canonical_bytes(number)


class CompletenessTests(unittest.TestCase):
    def setUp(self):
        self.geometry = geometry()
        self.analysis = replace(geometry("Polygon", [SQUARE], ref="synthetic/scope"),
                                role=GeometryRole.TESTCASE_ONLY_ANALYSIS_GEOMETRY)
        self.geometries = [self.geometry, self.analysis]
        body = js({"source_status": "TESTDATA", "features": [
            {"id": "synthetic/feature", "geometry": json.loads(self.geometry.geometry_json)}]}).encode()
        self.raws = [RawResponse(raw_response_hash(body), body)]
        self.snapshot = SourceSnapshot(
            "synthetic/snapshot", "TESTDATA", "synthetic", "points", "https://example.invalid/items",
            FetchExtent((0, 0, 10, 10), RD.crs, self.analysis.geometry_ref), RD.crs, RD.crs,
            '{"limit":1}', "current", "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z",
            ImportStatus.VALIDATING, PointInTimeConsistency.UNKNOWN, "No provider guarantee",
            1, 1, "0" * 64, CANONICALIZATION_VERSION, "synthetic-parser-v1", VALIDATOR_VERSION,
            PROVENANCE)
        self.pages = [SourcePage(
            self.snapshot.snapshot_id, 1, self.raws[0].raw_response_hash,
            self.snapshot.endpoint, '{"limit":1}', "2026-01-01T00:00:00Z", "application/json",
            '{"Content-Type":"application/json","Content-Crs":"EPSG:28992"}', RD.crs, 200)]
        self.features = [SourceFeature(self.snapshot.snapshot_id, "synthetic/feature", None,
                                       self.geometry.geometry_ref, 1, "{}", PROVENANCE)]
        self.rehash()

    def rehash(self):
        self.snapshot = replace(self.snapshot, snapshot_manifest_hash=snapshot_manifest_hash(
            self.snapshot, self.pages, self.features, self.geometries))

    def check(self, **kwargs):
        return validate_completeness(self.snapshot, self.pages, self.features,
                                     self.geometries, self.raws, **kwargs)

    def add_page(self, *, cursor=False):
        if cursor:
            self.pages[0] = replace(self.pages[0], cursor="token-2")
            url, params = self.snapshot.endpoint, '{"limit":1,"cursor":"token-2"}'
        else:
            self.pages[0] = replace(self.pages[0], next_url=self.snapshot.endpoint + "?page=2")
            url, params = self.pages[0].next_url, '{"limit":1,"page":2}'
        body = b'{"source_status":"TESTDATA","features":[]}'
        raw = RawResponse(raw_response_hash(body), body)
        self.raws.append(raw)
        self.pages.append(replace(self.pages[0], page_number=2, raw_response_hash=raw.raw_response_hash,
                                  request_url=url, request_parameters_json=params, next_url=None, cursor=None))
        self.snapshot = replace(self.snapshot, page_count=2)
        self.rehash()

    def test_complete_query_consistency_unknown_preserved(self):
        before = copy.deepcopy((self.snapshot, self.pages, self.features, self.geometries, self.raws))
        result = self.check()
        self.assertTrue(result.query_scope_complete)
        self.assertEqual(result.point_in_time_consistency, PointInTimeConsistency.UNKNOWN)
        self.assertEqual((self.snapshot, self.pages, self.features, self.geometries, self.raws), before)
        self.assertEqual(self.snapshot.status, ImportStatus.VALIDATING)
        self.assertFalse(hasattr(result, "promote"))

    def test_not_guaranteed_never_upgraded(self):
        self.snapshot = replace(self.snapshot, point_in_time_consistency=PointInTimeConsistency.NOT_GUARANTEED)
        self.rehash()
        self.assertEqual(self.check().point_in_time_consistency, PointInTimeConsistency.NOT_GUARANTEED)

    def test_missing_raw_page(self):
        self.raws = []
        with self.assertRaisesRegex(ValueError, "Missing raw"):
            self.check()

    def test_corrupt_raw_bytes(self):
        # Frozen contract bypass simulates corrupt archive bytes at validation boundary.
        object.__setattr__(self.raws[0], "body", b"corrupt")
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_page(self):
        self.pages = []
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_feature(self):
        self.features = []
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_feature_page_reference(self):
        self.features[0] = replace(self.features[0], page_number=2)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "feature/page"):
            self.check()

    def test_missing_geometry_reference(self):
        self.geometries = [self.analysis]
        with self.assertRaisesRegex(ValueError, "feature/geometry"):
            self.check()

    def test_missing_scope_geometry(self):
        self.geometries = [self.geometry]
        with self.assertRaisesRegex(ValueError, "analysis geometry"):
            self.check()

    def test_unresolved_next(self):
        self.pages[0] = replace(self.pages[0], next_url="https://example.invalid/next")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Unresolved"):
            self.check()

    def test_unresolved_cursor(self):
        self.pages[0] = replace(self.pages[0], cursor="not-processed")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Unresolved"):
            self.check()

    def test_incomplete_marker(self):
        with self.assertRaises(ValueError):
            self.check(failure_markers=("feature budget reached",))

    def test_failed_and_incomplete_status(self):
        for status in (ImportStatus.FAILED, ImportStatus.INCOMPLETE):
            self.snapshot = replace(self.snapshot, status=status)
            with self.assertRaises(ValueError):
                self.check()

    def test_invalid_geometry(self):
        self.geometries[0] = geometry("Polygon", [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]])
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Invalid geometry"):
            self.check()

    def test_invalid_geometry_crs(self):
        self.geometries[0] = geometry(crs=replace(RD, crs="EPSG:4326"))
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()

    def test_invalid_page_crs(self):
        self.pages[0] = replace(self.pages[0], response_crs="OGC:CRS84")
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()

    def test_wrong_label_detected_from_header(self):
        self.pages[0] = replace(self.pages[0], response_headers_json='{"Content-Crs":"OGC:CRS84"}')
        self.rehash()
        with self.assertRaisesRegex(ValueError, "contradicts"):
            self.check()

    def test_missing_provenance(self):
        for target in (self.snapshot, self.features[0], self.geometries[0]):
            before = target.provenance_json
            object.__setattr__(target, "provenance_json", "{}")
            with self.assertRaises(ValueError):
                self.check()
            object.__setattr__(target, "provenance_json", before)

    def test_missing_page_provenance(self):
        object.__setattr__(self.pages[0], "request_url", "")
        with self.assertRaises(ValueError):
            self.check()

    def test_http_failure(self):
        self.pages[0] = replace(self.pages[0], http_status=500)
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()

    def test_duplicate_feature_id(self):
        self.features.append(self.features[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.check()

    def test_duplicate_page(self):
        self.pages.append(self.pages[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.check()

    def test_cross_snapshot_reference(self):
        self.features[0] = replace(self.features[0], snapshot_id="other")
        with self.assertRaises(ValueError):
            self.check()

    def test_analysis_cannot_be_source(self):
        self.features[0] = replace(self.features[0], geometry_ref=self.analysis.geometry_ref)
        with self.assertRaisesRegex(ValueError, "source geometry"):
            self.check()

    def test_project_geometry_cannot_be_scope(self):
        self.geometries[1] = replace(self.analysis, role=GeometryRole.PROJECT_GEOMETRY)
        with self.assertRaises(ValueError):
            self.check()

    def test_valid_two_page_next_chain(self):
        self.add_page()
        self.assertEqual(self.check().page_count, 2)

    def test_valid_two_page_cursor_chain(self):
        self.add_page(cursor=True)
        self.assertEqual(self.check().page_count, 2)

    def test_broken_middle_next(self):
        self.add_page()
        self.pages[0] = replace(self.pages[0], next_url="https://example.invalid/missing")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Unresolved"):
            self.check()

    def test_broken_cursor_chain(self):
        self.add_page(cursor=True)
        self.pages[0] = replace(self.pages[0], cursor="other")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Unresolved cursor"):
            self.check()

    def test_unproven_page_chain(self):
        self.add_page()
        self.pages[0] = replace(self.pages[0], next_url=None)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Unproven"):
            self.check()

    def test_request_cycle(self):
        self.add_page()
        self.pages[0] = replace(self.pages[0], next_url=self.pages[0].request_url)
        self.pages[1] = replace(self.pages[1], request_url=self.pages[0].request_url,
                                request_parameters_json=self.pages[0].request_parameters_json)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.check()

    def test_empty_cursor_not_silently_ignored(self):
        self.pages[0] = replace(self.pages[0], cursor="")
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()

    def test_invalid_query_crs(self):
        self.snapshot = replace(self.snapshot, request_crs="EPSG:4326")
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()

    def test_zero_page_snapshot_not_complete(self):
        self.snapshot = replace(self.snapshot, page_count=0, feature_count=0)
        self.pages, self.features, self.raws = [], [], []
        self.geometries = [self.analysis]
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()

    def test_empty_result_page_can_be_complete(self):
        self.features = []
        self.geometries = [self.analysis]
        body = b'{"source_status":"TESTDATA","features":[]}'
        self.raws = [RawResponse(raw_response_hash(body), body)]
        self.pages[0] = replace(self.pages[0], raw_response_hash=self.raws[0].raw_response_hash)
        self.snapshot = replace(self.snapshot, feature_count=0)
        self.rehash()
        self.assertTrue(self.check().query_scope_complete)

    def test_manifest_hash_mismatch(self):
        self.snapshot = replace(self.snapshot, snapshot_manifest_hash="f" * 64)
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            self.check()

    def test_manifest_content_change(self):
        before = self.snapshot.snapshot_manifest_hash
        self.features[0] = replace(self.features[0], properties_json='{"changed":true}')
        self.rehash()
        self.assertNotEqual(before, self.snapshot.snapshot_manifest_hash)

    def test_manifest_scope_and_temporal_query_change(self):
        before = self.snapshot.snapshot_manifest_hash
        self.snapshot = replace(self.snapshot, temporal_query="2000-01-01")
        self.rehash()
        self.assertNotEqual(before, self.snapshot.snapshot_manifest_hash)
        before = self.snapshot.snapshot_manifest_hash
        self.snapshot = replace(self.snapshot, fetch_extent=replace(self.snapshot.fetch_extent, bbox=(0, 0, 11, 11)))
        self.rehash()
        self.assertNotEqual(before, self.snapshot.snapshot_manifest_hash)

    def test_manifest_runtime_timestamps_excluded(self):
        before = self.snapshot.snapshot_manifest_hash
        self.snapshot = replace(self.snapshot, snapshot_id="new-run",
                                retrieval_started_at="2099-01-01", retrieval_finished_at="2099-01-02")
        self.pages[0] = replace(self.pages[0], snapshot_id="new-run", retrieved_at="2099-01-01",
                                response_headers_json='{"Content-Type":"application/json","Content-Crs":"EPSG:28992","Date":"2099-01-01"}')
        self.features[0] = replace(self.features[0], snapshot_id="new-run")
        self.rehash()
        self.assertEqual(before, self.snapshot.snapshot_manifest_hash)
        self.assertTrue(self.check().query_scope_complete)

    def test_manifest_input_collection_order_is_irrelevant(self):
        self.add_page()
        before = self.snapshot.snapshot_manifest_hash
        self.pages.reverse()
        self.geometries.reverse()
        self.rehash()
        self.assertEqual(before, self.snapshot.snapshot_manifest_hash)
        self.assertTrue(self.check().query_scope_complete)

    def test_response_content_metadata_affects_manifest(self):
        before = self.snapshot.snapshot_manifest_hash
        self.pages[0] = replace(self.pages[0], response_headers_json='{"ETag":"version-2"}')
        self.rehash()
        self.assertNotEqual(before, self.snapshot.snapshot_manifest_hash)

    def test_geometry_hash_corruption_blocks_complete(self):
        self.geometries[0] = replace(self.geometry, geometry_structural_hash="f" * 64)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.check()

    def test_unknown_validator_version(self):
        self.snapshot = replace(self.snapshot, validator_version="future")
        self.rehash()
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main()
