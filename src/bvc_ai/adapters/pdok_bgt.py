"""Bounded PDOK BGT JSON-FG fetching and mapping; no network, storage or promotion authority."""
import json
from dataclasses import dataclass, replace
from math import isfinite
import time
import re
from decimal import Decimal
from urllib.parse import quote, urlencode, urljoin, urlsplit, parse_qsl

from bvc_ai.adapters.source_transport import (
    CapturedResponse, GetRequest, GetTransport, HttpResponse, ResponseOrigin,
)
from bvc_ai.domain.models import now
from bvc_ai.domain.source_profiles import source_profile, check_feature_contract
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


@dataclass(frozen=True)
class FetchBudgets:
    max_pages: int = 100
    max_features: int = 100000
    max_bytes: int = 64 * 1024 * 1024
    max_seconds: float = 120.0
    request_timeout: float = 15.0
    max_retries: int = 2
    retry_delay: float = 0.25

    def __post_init__(self):
        for value in (self.max_pages, self.max_features, self.max_bytes):
            if type(value) is not int or value < 1:
                raise ValueError("Positive integer budget required")
        if type(self.max_retries) is not int or not 0 <= self.max_retries <= 10:
            raise ValueError("Retries must be in 0..10")
        for value in (self.max_seconds, self.request_timeout, self.retry_delay):
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError("Positive finite time budget required")


@dataclass(frozen=True)
class FetchResult:
    status: ImportStatus
    pagination_exhausted: bool
    pages: tuple[SourcePage, ...]
    features: tuple[SourceFeature, ...]
    geometries: tuple[GeometryRecord, ...]
    captures: tuple[CapturedResponse, ...]
    manifest_json: str
    failure_reason: str | None
    # Exhaustion is transport evidence, not validated completeness or a
    # point-in-time guarantee. No snapshot/publication capability is provided.


def _continuation(href, current_url, items_url=ITEMS_URL):
    required(href)
    if (any(ord(c) <= 32 or ord(c) >= 127 for c in href)
            or "\\" in href or "#" in href
            or re.search(r"%(?![0-9a-fA-F]{2})", href)):
        raise ValueError("Invalid continuation URL")
    raw = urlsplit(href)
    # Query-only references or the exact absolute endpoint. Never normalize
    # traversal/encoded path tricks into an apparently acceptable endpoint.
    if href.startswith("?"):
        return urljoin(current_url, href)
    if (raw.scheme == "https" and raw.netloc == "api.pdok.nl"
            and raw.path == urlsplit(items_url).path):
        return href
    raise ValueError("Continuation outside allowed PDOK pand items scope")


def _request_identity(url):
    parts = urlsplit(url)
    return parts.path, tuple(sorted(parse_qsl(parts.query, keep_blank_values=True)))

class PDOKBGTAdapter:
    def __init__(self, transport: GetTransport, *, collection_metadata_json: str, clock=now, source_contract=None):
        """Collection metadata is supplied by the trusted caller, never inferred.

        Phase 3A does not fetch metadata or items over a real connection.
        Transport origin distinguishes synthetic test responses in provenance.
        """
        self.profile = source_profile(source_contract)
        self.transport = transport
        self.clock = clock
        metadata = strict_json(collection_metadata_json)
        if not isinstance(metadata, dict) or metadata.get("id") != self.profile.collection:
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
        return GetRequest(self.profile.items_url + "?" + urlencode(parameters), parameters,
                          (("Accept", JSON_FG),))

    def continuation(self, href, current_url, extent, limit):
        url = _continuation(href, current_url, self.profile.items_url)
        if self.profile.key:
            # Enforce fixed scope before the next transport call, including fake transports.
            pairs = tuple(parse_qsl(urlsplit(url).query, keep_blank_values=True))
            params = dict(pairs)
            expected = dict(self.build_request(extent, limit=limit).parameters)
            if (len(params) != len(pairs) or any(params.get(k) != v for k, v in expected.items())
                    or set(params) - (set(expected) | {'cursor'})
                    or ('cursor' in params and not params['cursor'])):
                raise ValueError('Continuation changed source query scope')
        return url

    def fetch_page(self, snapshot_id: str, extent: FetchExtent, *, limit=1000):
        required(snapshot_id)
        request = self.build_request(extent, limit=limit)
        started = self.clock()
        tick = time.monotonic()
        try:
            response = self.transport.get(request)
        except (OSError, TimeoutError) as exc:
            return PageResult(ImportStatus.FAILED, None,
                              failure_reason="Transport failure: " + type(exc).__name__)
        if not isinstance(response, HttpResponse) or type(response.body) is not bytes:
            return PageResult(ImportStatus.FAILED, None,
                              failure_reason="Invalid transport response")
        # Capture before reading content type, decoding JSON or mapping features.
        capture = CapturedResponse(
            request, response, RawResponse(raw_response_hash(response.body), response.body),
            started, self.clock())
        try:
            response.__post_init__()
            if len(response.body) > request.max_response_bytes:
                raise ValueError("Byte budget exceeded")
            if time.monotonic() - tick >= request.timeout_seconds:
                raise ValueError("Request timeout exceeded")
            parsed = self._parse(capture, snapshot_id, limit)
            if time.monotonic() - tick >= request.timeout_seconds:
                raise ValueError("Request timeout exceeded")
            return parsed
        except (ValueError, UnicodeError, RecursionError) as exc:
            # No partial page/features escape a failed mapping.
            return PageResult(ImportStatus.FAILED, capture, failure_reason=str(exc))

    def fetch(self, snapshot_id: str, extent: FetchExtent, *, limit=1000,
              budgets=None, monotonic=time.monotonic, sleep=time.sleep):
        """Bounded query traversal. Successful results remain VALIDATING.

        Partial pages/captures are evidence; failed fetches expose no feature or
        geometry bundle for downstream use. Existing archive completeness
        validation remains mandatory in a future trusted import service.
        """
        required(snapshot_id)
        budgets = budgets if budgets is not None else FetchBudgets()
        if not isinstance(budgets, FetchBudgets):
            raise ValueError("FetchBudgets required")
        budgets.__post_init__()
        request = self.build_request(extent, limit=limit)
        start = monotonic()
        pages, features, geometries, captures, attempts = [], [], [], [], []
        seen, seen_cursors, identities = set(), set(), set()
        received_bytes = 0
        continuation = None

        def remaining():
            return budgets.max_seconds - (monotonic() - start)

        def finish(reason=None):
            return FetchResult(
                ImportStatus.INCOMPLETE if reason else ImportStatus.VALIDATING,
                reason is None, tuple(pages), () if reason else tuple(features),
                () if reason else tuple(geometries), tuple(captures),
                _json_text({"attempts": attempts, "page_count": len(pages),
                            "feature_count": len(features), "received_bytes": received_bytes,
                            "pending_continuation": continuation, "failure_reason": reason,
                            "pagination_exhausted": reason is None,
                            "point_in_time_consistency": "NOT_GUARANTEED"}), reason)

        while True:
            if remaining() <= 0:
                return finish("Time budget exceeded")
            if len(pages) >= budgets.max_pages:
                return finish("Page budget exceeded")
            if received_bytes >= budgets.max_bytes:
                return finish("Byte budget exceeded")
            if len(features) >= budgets.max_features:
                return finish("Feature budget exceeded with pending continuation")
            identity = _request_identity(request.url)
            if identity in seen:
                return finish("Continuation cycle")
            cursor_values = tuple(sorted(v for k, v in request.parameters if k == "cursor"))
            if cursor_values and cursor_values in seen_cursors:
                return finish("Continuation cursor cycle")
            if cursor_values:
                seen_cursors.add(cursor_values)
            seen.add(identity)
            parsed = None
            for retry in range(budgets.max_retries + 1):
                available = remaining()
                if available <= 0:
                    return finish("Time budget exceeded")
                if received_bytes >= budgets.max_bytes:
                    return finish("Byte budget exceeded")
                request = replace(request, timeout_seconds=min(budgets.request_timeout, available),
                                  max_response_bytes=budgets.max_bytes - received_bytes)
                attempt = {"page_number": len(pages) + 1, "retry": retry,
                           "request_url": request.url, "incoming_continuation": continuation,
                           "timeout_seconds": request.timeout_seconds,
                           "max_response_bytes": request.max_response_bytes}
                attempts.append(attempt)
                started = self.clock()
                tick = monotonic()
                try:
                    response = self.transport.get(request)
                except (OSError, TimeoutError) as exc:
                    attempt["failure"] = type(exc).__name__
                    return finish("Transport failure: " + type(exc).__name__)
                if not isinstance(response, HttpResponse) or type(response.body) is not bytes:
                    attempt["failure"] = "Invalid transport response"
                    return finish(attempt["failure"])
                # Preserve every received body, including errors, before parsing.
                capture = CapturedResponse(
                    request, response, RawResponse(raw_response_hash(response.body), response.body),
                    started, self.clock())
                captures.append(capture)
                received_bytes += len(response.body)
                attempt.update(http_status=response.status, raw_response_hash=capture.raw.raw_response_hash,
                               response_bytes=len(response.body))
                if remaining() <= 0:
                    return finish("Time budget exceeded")
                if monotonic() - tick >= request.timeout_seconds:
                    return finish("Request timeout exceeded")
                if received_bytes > budgets.max_bytes:
                    return finish("Byte budget exceeded")
                try:
                    response.__post_init__()
                    if response.status == 429 or 500 <= response.status <= 599:
                        if retry == budgets.max_retries:
                            return finish("Retry exhaustion: HTTP " + str(response.status))
                        delay = budgets.retry_delay * (2 ** retry)
                        retry_after = [v for k, v in response.headers if k.lower() == "retry-after"]
                        if retry_after:
                            # Deliberately narrow offline profile: unsupported dates
                            # fail closed instead of guessing provider timing.
                            if len(retry_after) != 1 or not re.fullmatch(r"[0-9]{1,9}", retry_after[0]):
                                return finish("Unsupported Retry-After")
                            delay = max(delay, int(retry_after[0]))
                        attempt["retry_delay_seconds"] = delay
                        if delay >= remaining():
                            return finish("Time budget insufficient for retry")
                        sleep(delay)
                        continue
                    parsed = self._parse(capture, snapshot_id, limit)
                except (ValueError, UnicodeError, RecursionError) as exc:
                    attempt["failure"] = str(exc)
                    return finish("Response validation failure: " + str(exc))
                break
            if remaining() <= 0:
                return finish("Time budget exceeded")
            if monotonic() - tick >= request.timeout_seconds:
                return finish("Request timeout exceeded")
            outgoing = parsed.page.next_url
            continuation = outgoing
            attempt["next_link"] = outgoing
            attempt["page_metadata"] = strict_json(parsed.metadata_json)
            # Retain failed/unresolved links in the manifest and raw capture.
            try:
                next_url = self.continuation(outgoing, request.url, extent, limit) if outgoing is not None else None
            except ValueError as exc:
                return finish(str(exc))
            page_number = len(pages) + 1
            pages.append(replace(parsed.page, page_number=page_number, next_url=next_url))
            attempt["resolved_next_url"] = next_url
            if len(features) + len(parsed.features) > budgets.max_features:
                return finish("Feature budget exceeded")
            for feature in parsed.features:
                if feature.source_id in identities:
                    return finish("Duplicate feature id across pages")
                identities.add(feature.source_id)
            features.extend(replace(feature, page_number=page_number) for feature in parsed.features)
            geometries.extend(parsed.geometries)
            if remaining() <= 0:
                return finish("Time budget exceeded")
            if next_url is None:
                return finish()
            request = GetRequest(next_url, tuple(parse_qsl(urlsplit(next_url).query,
                                                          keep_blank_values=True)), request.headers)

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
            "provider": "PDOK", "dataset": self.profile.dataset, "collection": self.profile.collection,
            "collection_metadata_url": self.profile.collection_url,
            "collection_metadata": strict_json(self.collection_metadata_json),
            "source_status": ResponseOrigin(response.origin).value,
            "parser_version": self.profile.parser_version,
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
            check_feature_contract(self.profile, properties, place)
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
            geometry_ref = ("pdok/" + self.profile.dataset.lower() + "/" + self.profile.collection + "/" + quote(identity, safe="") + "/"
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
