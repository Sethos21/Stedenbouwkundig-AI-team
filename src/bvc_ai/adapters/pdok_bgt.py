"""Single-page PDOK BGT JSON-FG mapping; no network, storage or promotion authority."""
import json
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote, urlencode

from bvc_ai.adapters.source_transport import (
    CapturedResponse, GetRequest, GetTransport, HttpResponse, ResponseOrigin,
)
from bvc_ai.domain.models import now
from bvc_ai.domain.sources import (
    CRSMetadata, FetchExtent, GeometryRecord, GeometryRole, ImportStatus,
    RawResponse, SourceFeature, SourcePage, required,
)
from bvc_ai.domain.geometry_validation import validate_geometry_record
from bvc_ai.domain.source_hashing import (
    CANONICALIZATION_VERSION, geometry_structural_hash, normalize_crs_identifier,
    raw_response_hash, strict_json,
)

BASE_URL = "https://api.pdok.nl/lv/bgt/ogc/v1"
COLLECTION = "pand"
COLLECTION_URL = BASE_URL + "/collections/" + COLLECTION
ITEMS_URL = COLLECTION_URL + "/items"
RD_URI = "http://www.opengis.net/def/crs/EPSG/0/28992"
JSON_FG = "application/vnd.ogc.fg+json"
PARSER_VERSION = "pdok-bgt-jsonfg-page-v1"


def _json_text(value):
    """Ordinary JSON for existing contracts, retaining parsed Decimal precision.

    RawResponse always retains the original bytes; this is only the mapped
    record representation, not replacement source bytes or a new hash scheme.
    """
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Finite JSON number required")
        return str(value)
    if value is None or type(value) in (str, bool, int, float):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_json_text(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(key, ensure_ascii=False) + ":" + _json_text(item)
                              for key, item in value.items()) + "}"
    raise ValueError("Unsupported JSON value")


def _rd(identifier):
    if normalize_crs_identifier(identifier) != "EPSG:28992":
        raise ValueError("Native RD CRS evidence required")
    return identifier


def _header_crs(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Content-Crs required")
    value = value.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return _rd(value)


@dataclass(frozen=True)
class PageResult:
    status: ImportStatus
    capture: CapturedResponse | None
    page: SourcePage | None = None
    features: tuple[SourceFeature, ...] = ()
    geometries: tuple[GeometryRecord, ...] = ()
    metadata_json: str = "{}"
    failure_reason: str | None = None
    # Deliberately no COMPLETE flag or SourceSnapshot publication.


class PDOKBGTAdapter:
    def __init__(self, transport: GetTransport, *, collection_metadata_json: str, clock=now):
        """Collection metadata is supplied by the trusted caller, never inferred.

        Phase 3A does not fetch metadata or items over a real connection.
        Transport origin distinguishes synthetic test responses in provenance.
        """
        self.transport = transport
        self.clock = clock
        metadata = strict_json(collection_metadata_json)
        if not isinstance(metadata, dict) or metadata.get("id") != COLLECTION:
            raise ValueError("Explicit pand collection metadata required")
        crs_list = metadata.get("crs")
        if (not isinstance(crs_list, list) or not crs_list
                or not all(isinstance(crs, str) and crs.strip() for crs in crs_list)
                or not any(normalize_crs_identifier(crs) == "EPSG:28992" for crs in crs_list)):
            raise ValueError("Collection must explicitly support RD")
        if "storageCrs" in metadata:
            _rd(metadata["storageCrs"])
        self.collection_metadata_json = _json_text(metadata)

    def build_request(self, extent: FetchExtent, *, limit=1000):
        if not isinstance(extent, FetchExtent):
            raise ValueError("Explicit FetchExtent required")
        extent.__post_init__()
        _rd(extent.crs)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Limit must be an integer in 1..1000")
        parameters = (
            ("bbox", ",".join(str(number) for number in extent.bbox)),
            ("bbox-crs", RD_URI), ("crs", RD_URI), ("f", "jsonfg"), ("limit", str(limit)),
        )
        # No datetime/peildatum value is invented by this basic request profile.
        return GetRequest(ITEMS_URL + "?" + urlencode(parameters), parameters,
                          (("Accept", JSON_FG),))

    def fetch_page(self, snapshot_id: str, extent: FetchExtent, *, limit=1000):
        required(snapshot_id)
        request = self.build_request(extent, limit=limit)
        started = self.clock()
        try:
            response = self.transport.get(request)
        except (OSError, TimeoutError) as exc:
            return PageResult(ImportStatus.FAILED, None,
                              failure_reason="Transport failure: " + type(exc).__name__)
        if not isinstance(response, HttpResponse):
            raise ValueError("Transport must return HttpResponse")
        # Capture before reading content type, decoding JSON or mapping features.
        capture = CapturedResponse(
            request, response, RawResponse(raw_response_hash(response.body), response.body),
            started, self.clock())
        try:
            response.__post_init__()
            return self._parse(capture, snapshot_id, limit)
        except (ValueError, UnicodeError, RecursionError) as exc:
            # No partial page/features escape a failed mapping.
            return PageResult(ImportStatus.FAILED, capture, failure_reason=str(exc))

    def _parse(self, capture, snapshot_id, limit):
        response = capture.response
        if response.status != 200:
            raise ValueError("Expected HTTP 200; redirects and errors are not followed")
        headers = {}
        for name, value in response.headers:
            name = name.lower()
            if name in headers:
                raise ValueError("Duplicate response header")
            headers[name] = value
        content_type = headers.get("content-type", "")
        parts = content_type.split(";")
        if parts[0].strip().lower() != JSON_FG:
            raise ValueError("Expected JSON-FG Content-Type")
        for parameter in parts[1:]:
            if parameter.strip().lower() not in ('charset=utf-8', 'charset="utf-8"'):
                raise ValueError("Unsupported media type parameter")
        content_crs = _header_crs(headers.get("content-crs"))
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Encoded body unsupported by this raw JSON profile")
        document = strict_json(response.body.decode("utf-8"))
        if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
            raise ValueError("JSON-FG FeatureCollection required")
        document_crs = _rd(document.get("coordRefSys"))
        features = document.get("features")
        if not isinstance(features, list):
            raise ValueError("Feature array required")
        if len(features) > limit:
            raise ValueError("Response exceeds requested page limit")
        reported_count = document.get("numberReturned")
        if "numberReturned" in document:
            if (not isinstance(reported_count, Decimal) or reported_count < 0
                    or reported_count != reported_count.to_integral_value()
                    or reported_count != len(features)):
                raise ValueError("numberReturned does not match feature array")
        links = document.get("links", [])
        if not isinstance(links, list):
            raise ValueError("Links must be an array")
        next_url = None
        for link in links:
            if not isinstance(link, dict):
                raise ValueError("Malformed response link")
            required(link.get("rel"), link.get("href"))
            if link["rel"] == "next":
                if next_url is not None:
                    raise ValueError("Multiple next links")
                next_url = link["href"]  # Metadata only: never resolve or follow.
        metadata = {
            "provider": "PDOK", "dataset": "BGT", "collection": COLLECTION,
            "collection_metadata_url": COLLECTION_URL,
            "collection_metadata": strict_json(self.collection_metadata_json),
            "source_status": ResponseOrigin(response.origin).value,
            "parser_version": PARSER_VERSION,
            "request_url": capture.request.url,
            "request_parameters": dict(capture.request.parameters),
            "raw_response_hash": capture.raw.raw_response_hash,
            "content_type": content_type,
            "content_crs": headers["content-crs"], "coordRefSys": document_crs,
            "numberReturned": reported_count, "parsed_feature_count": len(features),
            "response_metadata": {key: value for key, value in document.items()
                                  if key != "features"},
        }
        parsed_features, geometries, identities = [], [], set()
        for feature in features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise ValueError("JSON-FG Feature required")
            identity = feature.get("id")
            required(identity)  # Never substitute properties or geometry hash for official id.
            if identity in identities:
                raise ValueError("Duplicate feature id within page")
            identities.add(identity)
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                raise ValueError("Feature properties object required")
            if "coordRefSys" in feature:
                _rd(feature["coordRefSys"])
            place = feature.get("place")
            if not isinstance(place, dict):
                raise ValueError("JSON-FG place geometry required; no geometry fallback")
            geometry_json = _json_text(place)
            provenance = dict(metadata, feature_id=identity, feature_metadata={
                key: value for key, value in feature.items() if key not in ("place", "properties")})
            evidence = _json_text({
                "request_crs": RD_URI, "bbox_crs": RD_URI, "Content-Crs": headers["content-crs"],
                "coordRefSys": document_crs, "feature_coordRefSys": feature.get("coordRefSys"),
                "collection_metadata": strict_json(self.collection_metadata_json),
                "source_status": ResponseOrigin(response.origin).value,
            })
            crs = CRSMetadata("EPSG:28992", ("easting", "northing"), 2, "metres", evidence)
            digest = geometry_structural_hash(geometry_json, crs)
            geometry_ref = ("pdok/bgt/pand/" + quote(identity, safe="") + "/"
                            + capture.raw.raw_response_hash + "/" + digest)
            record = GeometryRecord(geometry_ref, geometry_json, crs, digest,
                                    CANONICALIZATION_VERSION, GeometryRole.SOURCE_GEOMETRY,
                                    _json_text(provenance))
            validate_geometry_record(record, source_crs=content_crs)
            # No provider version field is guessed. All registration/temporal
            # properties remain intact for later explicit version mapping.
            parsed_features.append(SourceFeature(
                snapshot_id, identity, None, geometry_ref, 1, _json_text(properties),
                _json_text(provenance)))
            geometries.append(record)
        page = SourcePage(
            snapshot_id, 1, capture.raw.raw_response_hash, capture.request.url,
            _json_text(dict(capture.request.parameters)), capture.retrieval_finished_at,
            content_type, _json_text(headers), "EPSG:28992", response.status, next_url=next_url)
        return PageResult(ImportStatus.VALIDATING, capture, page,
                          tuple(parsed_features), tuple(geometries), _json_text(metadata))
