"""Closed point-discovery profile for the official DSO Ontsluiten v2 API."""
from copy import deepcopy
from bvc_ai.adapters.dso_diagnostics import mark, response_validation, validation_error
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import math
from typing import Protocol
from urllib.parse import urlencode

from bvc_ai.adapters.dso_contract import (
    CONTRACT_URL, CONTRACT_VERSION, CONTRACT_SHA256, canonical, contract,
    date_value, digest, read_json, reject, validate,
)
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin

HOST = 'service.omgevingswet.overheid.nl'
PATH = '/publiek/omgevingsinformatie/api/ontsluiten/v2/documenten/_zoek'
ENDPOINT = 'https://' + HOST + PATH
CRS = 'http://www.opengis.net/def/crs/EPSG/0/28992'
HEADERS = (('Accept', 'application/hal+json'), ('Content-Type', 'application/json'), ('Content-Crs', CRS))
PAGE_SIZE = 200


@dataclass(frozen=True)
class DiscoveryRequest:
    url: str
    parameters: tuple[tuple[str, str], ...]
    body: bytes
    headers: tuple[tuple[str, str], ...] = HEADERS
    timeout_seconds: float = 15.0
    max_response_bytes: int = 4 * 1024 * 1024
    method: str = field(default='POST', init=False)


class DiscoveryTransport(Protocol):
    def post(self, request: DiscoveryRequest) -> HttpResponse:
        """Trusted transport: bounded total deadline/bytes; no redirects or secret output."""
        ...


def build_request(point_rd, peildatum, beschikbaar_op):
    date_value(peildatum)
    date_value(beschikbaar_op, timestamp=True)
    if type(point_rd) not in (tuple, list) or len(point_rd) != 2:
        reject()
    for n, low, high in zip(point_rd, (-7000, 289000), (300000, 629000)):
        if (type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high
                or Decimal(str(n)) % Decimal('0.001') != 0):
            reject()
    params = (('geldigOp', peildatum), ('beschikbaarOp', beschikbaar_op),
              ('inclusiefToekomstigGeldig', 'false'), ('page', '0'),
              ('size', str(PAGE_SIZE)), ('_sort', 'ASC'))
    body = canonical(dict(geometrie=dict(type='Point', coordinates=list(point_rd)))).encode()
    return DiscoveryRequest(ENDPOINT + '?' + urlencode(params), params, body)


def validate_request(request):
    if type(request) is not DiscoveryRequest:
        reject()
    try:
        data = read_json(request.body)
        params = dict(request.parameters)
        expected = build_request(data['geometrie']['coordinates'], params['geldigOp'], params['beschikbaarOp'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Invalid DSO discovery request') from None
    if (request.url != expected.url or request.parameters != expected.parameters
            or request.body != expected.body or request.headers != HEADERS or request.method != 'POST'
            or type(request.timeout_seconds) not in (float, int)
            or not math.isfinite(request.timeout_seconds) or not 0 < request.timeout_seconds <= 15
            or type(request.max_response_bytes) is not int or not 0 < request.max_response_bytes <= 4 * 1024 * 1024):
        raise ValueError('Invalid DSO discovery request')


@response_validation
def parse_response(response, request):
    validate_request(request)
    if type(response) is not HttpResponse or response.status != 200 or len(response.body) > request.max_response_bytes:
        reject()
    headers = {}
    for name, value in response.headers:
        name = name.lower()
        if name in headers:
            reject()
        headers[name] = value
    if headers.get('api-version') != CONTRACT_VERSION:
        raise mark(ValueError('DSO API version mismatch'), 'validatie', 'CONTRACT_VERSION_MISMATCH')
    if (headers.get('content-type', '').split(';')[0].strip() != 'application/hal+json'
            or headers.get('api-version') != CONTRACT_VERSION
            or headers.get('content-encoding', 'identity') != 'identity'):
        reject('CONTENT_TYPE' if headers.get('content-type', '').split(';')[0].strip() != 'application/hal+json' else 'UNKNOWN')
    data = read_json(response.body)
    spec = contract()
    validate(data, spec['components']['schemas']['Documenten'], spec)
    page = data['page']
    docs = data['_embedded']['documenten']
    # Never publish a truncated result. No server-controlled continuation requests.
    if (set(page) != {'number', 'size', 'totalElements', 'totalPages'}
            or page['number'] != 0 or page['size'] != PAGE_SIZE
            or page['totalElements'] != len(docs) or len(docs) > PAGE_SIZE
            or page['totalPages'] != (1 if docs else 0)
            or 'next' in data['_links']):
        raise validation_error(ValueError('Incomplete or ambiguous DSO discovery page'), 'PAGINATION')
    ids, uris, expressions = set(), set(), set()
    for doc in docs:
        identity, uri = doc['identificatie'], doc['uriIdentificatie']
        if identity in ids or uri in uris or doc['versie'] < 0:
            raise validation_error(ValueError('Ambiguous DSO document identity'), 'DOCUMENT_IDENTITY')
        ids.add(identity)
        uris.add(uri)
        for start, end, timestamp in (('geldigVanaf', 'geldigTot', False),
                                      ('inwerkingVanaf', 'inwerkingTot', False),
                                      ('beschikbaarVanaf', 'beschikbaarTot', True)):
            if start in doc and end in doc and date_value(doc[start], timestamp=timestamp) >= date_value(doc[end], timestamp=timestamp):
                raise validation_error(ValueError('Ambiguous DSO temporal interval'), 'TEMPORAL_INTERVAL')
        ow = 'omgevingsdocumentMetadata' in doc
        imro = 'imroDocumentMetadata' in doc
        if ow == imro:
            raise validation_error(ValueError('Ambiguous DSO document family'), 'DOCUMENT_FAMILY')
        if ow:
            expression = doc['omgevingsdocumentMetadata']['expressionId']
            if (not identity.startswith('/akn/nl/') or uri != identity.replace('/', '_')
                    or not expression.startswith(identity + '/') or expression in expressions):
                raise validation_error(ValueError('Ambiguous DSO expression identity'), 'DOCUMENT_IDENTITY')
            expressions.add(expression)
        elif not identity.startswith('NL.IMRO.') or uri != identity:
            raise validation_error(ValueError('Ambiguous DSO IMRO identity'), 'DOCUMENT_IDENTITY')
    # All candidates retained; no relevance ranking, legal interpretation or selection.
    return sorted(deepcopy(docs), key=lambda d: (d['identificatie'], d['versie']))


class DSODiscoveryAdapter:
    def __init__(self, transport):
        self._transport = transport

    def discover(self, point_rd, *, peildatum, beschikbaar_op, clock):
        request = build_request(point_rd, peildatum, beschikbaar_op)
        started = clock()
        date_value(started, timestamp=True)
        response = self._transport.post(request)
        documents = parse_response(response, request)
        finished = clock()
        if date_value(finished, timestamp=True) < date_value(started, timestamp=True):
            reject()
        return dict(
            documents=documents, source_status=ResponseOrigin(response.origin).value,
            provenance=dict(
                endpoint=ENDPOINT, method='POST', query_parameters=dict(request.parameters),
                request_body=read_json(request.body), request_headers=dict(request.headers),
                request_hash=digest(dict(url=request.url, body=read_json(request.body), headers=request.headers)),
                source_contract='DSO_OMGEVINGSINFORMATIE_ONTSLUITEN_V2',
                api_version=CONTRACT_VERSION, contract_url=CONTRACT_URL, contract_sha256=CONTRACT_SHA256,
                retrieval_started_at=started, retrieval_finished_at=finished,
                raw_response_sha256=hashlib.sha256(response.body).hexdigest()),
            # Exact accepted bytes, so parsing can be reproduced without a new live call.
            raw_response_utf8=response.body.decode('utf-8'))
