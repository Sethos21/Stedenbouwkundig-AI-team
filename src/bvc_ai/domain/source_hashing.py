"""Versioned structural identity. No topology normalization or source mutation."""
import json
from decimal import Decimal
from hashlib import sha256

CANONICALIZATION_VERSION = "bvc-source-structural-v1"


def strict_json(value):
    """Keep decimal values exact; reject duplicate keys and non-JSON numbers."""
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = item
        return result

    def invalid(value):
        raise ValueError("Non-finite JSON number")

    if not isinstance(value, str):
        raise ValueError("JSON text required")
    try:
        return json.loads(value, parse_int=Decimal, parse_float=Decimal,
                          parse_constant=invalid, object_pairs_hook=pairs)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid JSON") from exc


def _canonical_tree(value):
    # Typed nodes prevent number/string and array/object collisions.
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is str:
        return ["string", value]
    if type(value) in (int, float, Decimal):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Finite canonical number required")
        sign, digits, exponent = number.as_tuple()
        coefficient = "".join(str(d) for d in digits)
        if number == 0:
            token = "0"
        else:
            while coefficient.endswith("0"):
                coefficient = coefficient[:-1]
                exponent += 1
            token = ("-" if sign else "") + coefficient + "e" + str(exponent)
        return ["number", token]
    if type(value) in (list, tuple):
        return ["array", [_canonical_tree(item) for item in value]]
    if type(value) is dict and all(type(k) is str for k in value):
        return ["object", [[key, _canonical_tree(value[key])] for key in sorted(value)]]
    raise ValueError("Unsupported canonical value")


def canonical_bytes(value):
    """UTF-8, sorted Unicode keys, exact decimals, array order retained."""
    try:
        return json.dumps(_canonical_tree(value), ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Cannot canonicalize input") from exc


def raw_response_hash(body):
    if type(body) is not bytes:
        raise ValueError("Exact response bytes required")
    return sha256(body).hexdigest()


def normalize_crs_identifier(crs):
    """Only explicit RD aliases; no coordinate inference or transformation."""
    if not isinstance(crs, str) or not crs.strip():
        raise ValueError("CRS identifier required")
    value = crs.strip()
    if value.lower() in {
        "epsg:28992", "urn:ogc:def:crs:epsg::28992",
        "http://www.opengis.net/def/crs/epsg/0/28992",
        "https://www.opengis.net/def/crs/epsg/0/28992",
    }:
        return "EPSG:28992"
    return value


def geometry_structural_hash(geometry_json, crs_metadata):
    """Hashing is not validation: other explicit CRSs can be fingerprinted."""
    from bvc_ai.domain.sources import CRSMetadata
    if not isinstance(crs_metadata, CRSMetadata):
        raise ValueError("Explicit CRS metadata required")
    crs_metadata.__post_init__()
    geometry = strict_json(geometry_json)
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        raise ValueError("Geometry type and coordinates required")
    payload = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "geometry": geometry,
        "crs": {
            "identifier": normalize_crs_identifier(crs_metadata.crs),
            "axis_order": crs_metadata.axis_order,
            "dimension": crs_metadata.dimension,
            "units": crs_metadata.units,
        },
    }
    return raw_response_hash(canonical_bytes(payload))


def snapshot_manifest_hash(snapshot, pages, features, geometries):
    """Hash explicit scope and archived content, excluding retrieval timestamps.

    Caller supplies geometry records including the analysis reference.
    This computes identity only; completeness must be validated separately.
    """
    geometry_by_ref = {}
    for geometry in geometries:
        if geometry.geometry_ref in geometry_by_ref:
            raise ValueError("Duplicate geometry reference")
        geometry_by_ref[geometry.geometry_ref] = geometry

    def geometry_identity(ref):
        if ref not in geometry_by_ref:
            raise ValueError("Missing geometry reference")
        geometry = geometry_by_ref[ref]
        return {
            "structural_hash": geometry_structural_hash(
                geometry.geometry_json, geometry.crs_metadata),
            "canonicalization_version": geometry.canonicalization_version,
        }

    # A Date header is retrieval metadata; ETag and Last-Modified identify content.
    relevant_headers = {"content-type", "content-crs", "etag", "last-modified"}
    page_content = []
    for page in sorted(pages, key=lambda p: p.page_number):
        headers = strict_json(page.response_headers_json)
        if not isinstance(headers, dict):
            raise ValueError("Header object required")
        normalized_headers = {}
        for name, value in headers.items():
            name = name.lower()
            if name in relevant_headers:
                if name in normalized_headers:
                    raise ValueError("Duplicate relevant response header")
                normalized_headers[name] = value
        page_content.append({
            "number": page.page_number, "raw_hash": page.raw_response_hash,
            "url": page.request_url, "parameters": strict_json(page.request_parameters_json),
            "media_type": page.media_type, "headers": normalized_headers,
            "response_crs": normalize_crs_identifier(page.response_crs),
            "http_status": page.http_status, "next_url": page.next_url, "cursor": page.cursor,
        })
    payload = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "provider": snapshot.provider, "dataset": snapshot.dataset,
        "collection": snapshot.collection, "endpoint": snapshot.endpoint,
        "extent": {"bbox": snapshot.fetch_extent.bbox,
                   "crs": normalize_crs_identifier(snapshot.fetch_extent.crs),
                   "analysis": geometry_identity(snapshot.fetch_extent.analysis_geometry_ref)},
        "request_crs": normalize_crs_identifier(snapshot.request_crs),
        "response_crs": normalize_crs_identifier(snapshot.response_crs),
        "parameters": strict_json(snapshot.request_parameters_json),
        "temporal_query": snapshot.temporal_query,
        "page_count": snapshot.page_count, "feature_count": snapshot.feature_count,
        "parser_version": snapshot.parser_version, "validator_version": snapshot.validator_version,
        "consistency": str(snapshot.point_in_time_consistency),
        "consistency_evidence": snapshot.consistency_evidence,
        "provenance": strict_json(snapshot.provenance_json),
        "pages": page_content,
        "features": [{
            "source_id": f.source_id, "source_version": f.source_version,
            "page": f.page_number, "geometry": geometry_identity(f.geometry_ref),
            "properties": strict_json(f.properties_json),
            "provenance": strict_json(f.provenance_json),
        } for f in sorted(features, key=lambda f: f.source_id)],
    }
    return raw_response_hash(canonical_bytes(payload))
