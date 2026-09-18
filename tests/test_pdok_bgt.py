"""Phase 3A: synthetic JSON-FG fixtures and fake GET only; no live provider calls."""
import copy
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bvc_ai.adapters.pdok_bgt import (
    BASE_URL, COLLECTION_URL, ITEMS_URL, JSON_FG, RD_URI, PDOKBGTAdapter,
)
from bvc_ai.adapters.source_transport import GetRequest, HttpResponse, ResponseOrigin
from bvc_ai.domain.sources import FetchExtent, ImportStatus
from bvc_ai.domain.source_hashing import raw_response_hash, strict_json
from bvc_ai.domain.geometry_validation import validate_geometry_record


METADATA = {"id": "pand", "title": "SYNTHETIC TESTDATA pand",
            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84", RD_URI],
            "storageCrs": RD_URI}
EXTENT = FetchExtent((0, 0, 10, 10), "EPSG:28992", "TESTDATA/analysis")
DOCUMENT = {
    "type": "FeatureCollection", "coordRefSys": RD_URI, "numberReturned": 1,
    "features": [{
        "type": "Feature", "id": "synthetic-provider-id-1",
        "place": {"type": "Polygon", "coordinates": [
            [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
        "geometry": None,
        "properties": {"source_status": "TESTDATA", "lokaal_id": "synthetic-local-id",
                       "bronhouder": "TEST", "tijdstip_registratie": "2026-01-01T00:00:00Z",
                       "eind_registratie": None, "custom_source_version": "synthetic-v1"},
    }],
    "links": [],
}


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def get(self, request):
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class PDOKBasisTests(unittest.TestCase):
    def setUp(self):
        self.document = copy.deepcopy(DOCUMENT)
        self.headers = (("Content-Type", JSON_FG), ("Content-Crs", "<" + RD_URI + ">"))
        self.response = HttpResponse(200, self.headers, json.dumps(self.document).encode(),
                                     ResponseOrigin.TESTDATA)
        self.transport = FakeTransport(self.response)
        self.times = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"))
        self.adapter = PDOKBGTAdapter(self.transport,
                                     collection_metadata_json=json.dumps(METADATA),
                                     clock=lambda: next(self.times))

    def fetch(self, *, document=None, response=None, limit=1000):
        if document is not None:
            self.transport.response = replace(self.response, body=json.dumps(document).encode())
        if response is not None:
            self.transport.response = response
        return self.adapter.fetch_page("synthetic/snapshot", EXTENT, limit=limit)

    def assertFailed(self, result):
        self.assertEqual(result.status, ImportStatus.FAILED)
        self.assertIsNotNone(result.failure_reason)
        self.assertEqual(result.features, ())
        self.assertEqual(result.geometries, ())
        self.assertIsNone(result.page)

    def test_get_only_official_endpoint_collection_and_parameters(self):
        request = self.adapter.build_request(EXTENT, limit=25)
        self.assertEqual(request.method, "GET")
        parts = urlsplit(request.url)
        self.assertEqual(parts.scheme, "https")
        self.assertEqual(parts.netloc, "api.pdok.nl")
        self.assertEqual(parts.path, "/lv/bgt/ogc/v1/collections/pand/items")
        self.assertEqual(ITEMS_URL, BASE_URL + "/collections/pand/items")
        self.assertEqual(dict(request.parameters), {
            "bbox": "0,0,10,10", "bbox-crs": RD_URI, "crs": RD_URI, "f": "jsonfg", "limit": "25"})
        self.assertEqual(parse_qs(parts.query), {k: [v] for k, v in request.parameters})
        self.assertEqual(dict(request.headers), {"Accept": JSON_FG})
        self.assertNotIn("datetime", dict(request.parameters))
        with self.assertRaises(TypeError):
            GetRequest(request.url, request.parameters, request.headers, method="POST")

    def test_limit_upper_boundary(self):
        self.assertEqual(dict(self.adapter.build_request(EXTENT, limit=1000).parameters)["limit"], "1000")

    def test_invalid_limit_rejected_before_transport(self):
        for limit in (0, -1, 1001, True, 1.5, "1000"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.adapter.fetch_page("synthetic/snapshot", EXTENT, limit=limit)
        self.assertEqual(self.transport.requests, [])

    def test_explicit_native_rd_extent_required(self):
        for extent in (None, replace(EXTENT, crs="EPSG:4326")):
            with self.assertRaises(ValueError):
                self.adapter.fetch_page("synthetic/snapshot", extent)
        self.assertEqual(self.transport.requests, [])

    def test_valid_jsonfg_maps_existing_contracts(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            result = self.fetch()
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertIsNone(result.failure_reason)
        self.assertEqual(len(result.features), 1)
        self.assertEqual(result.page.snapshot_id, "synthetic/snapshot")
        self.assertEqual(result.features[0].geometry_ref, result.geometries[0].geometry_ref)
        self.assertEqual(result.features[0].page_number, result.page.page_number)
        self.assertEqual(result.page.page_number, 1)
        self.assertEqual(len(self.transport.requests), 1)

    def test_place_used_instead_of_geojson_geometry(self):
        self.document["features"][0]["geometry"] = {"type": "Point", "coordinates": [5, 52]}
        result = self.fetch(document=self.document)
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertEqual(json.loads(result.geometries[0].geometry_json),
                         self.document["features"][0]["place"])

    def test_feature_identity_properties_and_provenance_preserved(self):
        result = self.fetch()
        feature = result.features[0]
        self.assertEqual(feature.source_id, DOCUMENT["features"][0]["id"])
        self.assertEqual(json.loads(feature.properties_json), DOCUMENT["features"][0]["properties"])
        self.assertIsNone(feature.source_version)  # No guessed registration-to-version mapping.
        provenance = json.loads(feature.provenance_json)
        self.assertEqual(provenance["provider"], "PDOK")
        self.assertEqual(provenance["dataset"], "BGT")
        self.assertEqual(provenance["collection"], "pand")
        self.assertEqual(provenance["source_status"], "TESTDATA")
        self.assertEqual(provenance["collection_metadata"], METADATA)
        self.assertEqual(provenance["collection_metadata_url"], COLLECTION_URL)
        self.assertEqual(provenance["feature_id"], feature.source_id)
        self.assertEqual(provenance["raw_response_hash"], result.capture.raw.raw_response_hash)

    def test_raw_bytes_and_timing_are_exact(self):
        body = (" \n" + json.dumps(self.document, indent=3) + "\n ").encode()
        response = replace(self.response, body=body)
        result = self.fetch(response=response)
        self.assertEqual(result.capture.raw.body, body)
        self.assertEqual(result.capture.response.body, body)
        self.assertEqual(result.capture.raw.raw_response_hash, raw_response_hash(body))
        self.assertEqual(result.page.raw_response_hash, raw_response_hash(body))
        self.assertEqual(result.capture.response.headers, self.headers)
        self.assertEqual(result.capture.retrieval_started_at, "2026-01-01T00:00:00Z")
        self.assertEqual(result.capture.retrieval_finished_at, "2026-01-01T00:00:01Z")
        self.assertEqual(result.page.request_url, self.transport.requests[0].url)
        self.assertEqual(json.loads(result.page.request_parameters_json),
                         dict(self.transport.requests[0].parameters))

    def test_crs_evidence_retained_and_existing_validator_called(self):
        with patch("bvc_ai.adapters.pdok_bgt.validate_geometry_record",
                   wraps=validate_geometry_record) as validate:
            result = self.fetch()
        validate.assert_called_once()
        metadata = result.geometries[0].crs_metadata
        self.assertEqual(metadata.crs, "EPSG:28992")
        self.assertEqual(metadata.axis_order, ("easting", "northing"))
        self.assertEqual(metadata.units, "metres")
        self.assertEqual(metadata.dimension, 2)
        evidence = json.loads(metadata.evidence)
        self.assertEqual(evidence["request_crs"], RD_URI)
        self.assertEqual(evidence["bbox_crs"], RD_URI)
        self.assertEqual(evidence["Content-Crs"], "<" + RD_URI + ">")
        self.assertEqual(evidence["coordRefSys"], RD_URI)
        self.assertEqual(json.loads(result.page.response_headers_json)["content-crs"], "<" + RD_URI + ">")

    def test_missing_content_crs_fails_with_raw_capture(self):
        response = replace(self.response, headers=(("Content-Type", JSON_FG),))
        result = self.fetch(response=response)
        self.assertFailed(result)
        self.assertEqual(result.capture.raw.body, response.body)

    def test_missing_coord_ref_sys_fails(self):
        del self.document["coordRefSys"]
        self.assertFailed(self.fetch(document=self.document))

    def test_conflicting_header_crs_fails(self):
        response = replace(self.response, headers=(("Content-Type", JSON_FG),
                                                    ("Content-Crs", "OGC:CRS84")))
        self.assertFailed(self.fetch(response=response))

    def test_conflicting_document_crs_fails(self):
        self.document["coordRefSys"] = "EPSG:4326"
        self.assertFailed(self.fetch(document=self.document))

    def test_conflicting_feature_crs_fails(self):
        self.document["features"][0]["coordRefSys"] = "EPSG:4326"
        self.assertFailed(self.fetch(document=self.document))

    def test_matching_feature_crs_preserved(self):
        self.document["features"][0]["coordRefSys"] = RD_URI
        result = self.fetch(document=self.document)
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        evidence = json.loads(result.geometries[0].crs_metadata.evidence)
        self.assertEqual(evidence["feature_coordRefSys"], RD_URI)

    def test_collection_evidence_required_before_request(self):
        cases = ({}, {"id": "other", "crs": [RD_URI]}, {"id": "pand"},
                 {"id": "pand", "crs": ["EPSG:4326"]},
                 dict(METADATA, storageCrs="EPSG:4326"))
        for metadata in cases:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                PDOKBGTAdapter(self.transport, collection_metadata_json=json.dumps(metadata))
        self.assertEqual(self.transport.requests, [])

    def test_invalid_json_and_empty_body_preserve_received_bytes(self):
        # Each failure must retain its own received response without parsing repair.
        for body in (b"", b"not json", b'{"features":', b"\xff"):
            adapter = PDOKBGTAdapter(FakeTransport(replace(self.response, body=body)),
                                     collection_metadata_json=json.dumps(METADATA))
            result = adapter.fetch_page("synthetic/snapshot", EXTENT)
            self.assertFailed(result)
            self.assertEqual(result.capture.raw.body, body)

    def test_wrong_root_and_features_contract(self):
        for document in (None, [], {}, {"type": "FeatureCollection", "coordRefSys": RD_URI},
                         dict(DOCUMENT, features={}), dict(DOCUMENT, type="Feature")):
            response = replace(self.response, body=json.dumps(document).encode())
            adapter = PDOKBGTAdapter(FakeTransport(response), collection_metadata_json=json.dumps(METADATA))
            self.assertFailed(adapter.fetch_page("synthetic/snapshot", EXTENT))

    def test_malformed_feature_and_missing_place_no_geometry_fallback(self):
        cases = [None, {}, dict(DOCUMENT["features"][0], place=None)]
        fallback = copy.deepcopy(DOCUMENT["features"][0])
        fallback["geometry"] = fallback.pop("place")
        cases.append(fallback)
        for feature in cases:
            response = replace(self.response, body=json.dumps(dict(DOCUMENT, features=[feature])).encode())
            adapter = PDOKBGTAdapter(FakeTransport(response), collection_metadata_json=json.dumps(METADATA))
            self.assertFailed(adapter.fetch_page("synthetic/snapshot", EXTENT))

    def test_missing_id_never_replaced_by_local_id_or_geometry_hash(self):
        del self.document["features"][0]["id"]
        result = self.fetch(document=self.document)
        self.assertFailed(result)
        self.assertIsNotNone(result.capture)

    def test_invalid_id_and_properties_fail(self):
        for change in ({"id": ""}, {"id": 123}, {"properties": None}):
            document = copy.deepcopy(DOCUMENT)
            document["features"][0].update(change)
            adapter = PDOKBGTAdapter(FakeTransport(replace(self.response, body=json.dumps(document).encode())),
                                     collection_metadata_json=json.dumps(METADATA))
            self.assertFailed(adapter.fetch_page("synthetic/snapshot", EXTENT))

    def test_invalid_geometry_uses_existing_validation_gate(self):
        self.document["features"][0]["place"]["coordinates"][0].pop()
        self.assertFailed(self.fetch(document=self.document))

    def test_second_bad_feature_never_exposes_partial_mapping(self):
        self.document["features"].append(dict(self.document["features"][0], id="second", place=None))
        self.document["numberReturned"] = 2
        self.assertFailed(self.fetch(document=self.document))

    def test_count_mismatch_fails(self):
        self.document["numberReturned"] = 2
        self.assertFailed(self.fetch(document=self.document))

    def test_count_absent_is_recorded_as_unknown_not_invented(self):
        del self.document["numberReturned"]
        result = self.fetch(document=self.document)
        metadata = json.loads(result.metadata_json)
        self.assertIsNone(metadata["numberReturned"])
        self.assertEqual(metadata["parsed_feature_count"], 1)

    def test_duplicate_provider_id_rejected(self):
        self.document["features"].append(copy.deepcopy(self.document["features"][0]))
        self.document["numberReturned"] = 2
        self.assertFailed(self.fetch(document=self.document))

    def test_wrong_content_type_fails(self):
        self.assertFailed(self.fetch(response=replace(
            self.response, headers=(("Content-Type", "application/json"), ("Content-Crs", RD_URI)))))

    def test_duplicate_crs_headers_rejected(self):
        self.assertFailed(self.fetch(response=replace(
            self.response, headers=self.headers + (("content-crs", "EPSG:4326"),))))

    def test_http_failure_and_redirect_capture_without_follow_or_retry(self):
        for status in (302, 404, 429, 500):
            fake = FakeTransport(replace(self.response, status=status, body=b"failure",
                                        headers=self.headers + (("Location", "https://example.invalid/"),)))
            adapter = PDOKBGTAdapter(fake, collection_metadata_json=json.dumps(METADATA))
            result = adapter.fetch_page("synthetic/snapshot", EXTENT)
            self.assertFailed(result)
            self.assertEqual(result.capture.raw.body, b"failure")
            self.assertEqual(result.capture.response.status, status)
            self.assertEqual(len(fake.requests), 1)

    def test_transport_failure_not_retried(self):
        result = self.fetch(response=TimeoutError("synthetic timeout"))
        self.assertFailed(result)
        self.assertIsNone(result.capture)
        self.assertEqual(len(self.transport.requests), 1)

    def test_next_metadata_kept_but_never_followed_or_marked_complete(self):
        self.document["links"] = [{"rel": "next", "href": "?cursor=opaque%2Btoken"}]
        result = self.fetch(document=self.document)
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertEqual(result.page.next_url, "?cursor=opaque%2Btoken")
        self.assertEqual(len(self.transport.requests), 1)
        self.assertEqual(json.loads(result.metadata_json)["response_metadata"]["links"],
                         self.document["links"])

    def test_empty_page_not_published_as_complete(self):
        self.document["features"] = []
        self.document["numberReturned"] = 0
        result = self.fetch(document=self.document)
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertEqual(result.features, ())
        self.assertIsNone(result.page.next_url)

    def test_decimal_precision_survives_adapter_mapping(self):
        body = json.dumps(self.document).replace("[0, 0]", "[0.000000000000000001, 0]")
        result = self.fetch(response=replace(self.response, body=body.encode()))
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        value = strict_json(result.geometries[0].geometry_json)["coordinates"][0][0][0]
        self.assertEqual(value, Decimal("0.000000000000000001"))
        self.assertEqual(result.capture.raw.body, body.encode())

    def test_no_storage_or_publication_capability(self):
        result = self.fetch()
        self.assertEqual(result.status, ImportStatus.VALIDATING)
        self.assertFalse(hasattr(self.adapter, "store"))
        self.assertFalse(hasattr(self.adapter, "promote"))
        self.assertFalse(hasattr(result, "snapshot"))


if __name__ == "__main__":
    unittest.main()
