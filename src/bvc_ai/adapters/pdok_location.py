"""Narrow official address resolution. No storage, import or approval capability."""
import base64
from dataclasses import dataclass, asdict
from decimal import Decimal
import json
import re
import time
import unicodedata
from urllib.parse import urlencode

from bvc_ai.adapters.pdok_live import PDOKLiveGetTransport
from bvc_ai.adapters.source_transport import GetRequest, HttpResponse, ResponseOrigin
from bvc_ai.domain.models import now
from bvc_ai.domain.source_hashing import raw_response_hash, strict_json

ENDPOINT = 'https://api.pdok.nl/bzk/locatieserver/search/v3_1/free'
CONTRACT = 'PDOK_LOCATIESERVER_ADDRESS_V1'
MAX_BYTES = 128 * 1024
TIMEOUT = 20.0
FIELDS = ('id,bron,type,weergavenaam,straatnaam,huisnummer,huisletter,'
          'huisnummertoevoeging,postcode,woonplaatsnaam,nummeraanduiding_id,'
          'adresseerbaarobject_id,centroide_rd')


def normalized(value):
    if not isinstance(value, str):
        raise ValueError('Address text required')
    return ''.join(c for c in unicodedata.normalize('NFC', value).casefold() if c.isalnum())


@dataclass(frozen=True)
class AddressInput:
    text: str
    street: str
    number: int
    suffix: str
    postcode: str
    city: str

    @classmethod
    def parse(cls, text):
        if not isinstance(text, str) or not 1 <= len(text) <= 300:
            raise ValueError('Bounded Dutch address text required')
        if any(ord(c) < 32 and c not in '\r\n\t' for c in text):
            raise ValueError('Control characters forbidden')
        clean = ' '.join(text.replace(',', ' ').split())
        clean = re.sub(r'\s+Nederland$', '', clean, flags=re.I)
        m = re.fullmatch(r"(.+?)\s+([1-9][0-9]{0,4})\s*([A-Za-z]?(?:-?[A-Za-z0-9]{1,4})?)\s+([1-9][0-9]{3})\s*([A-Za-z]{2})\s+(.+)", clean)
        if not m:
            raise ValueError('Street, house number, postcode and city required')
        street, number, suffix, digits, letters, city = m.groups()
        for value in (street, city):
            if not any(c.isalpha() for c in value) or any(not (c.isalnum() or c in " .'-’") for c in value):
                raise ValueError('Unsupported street/city syntax')
        return cls(text, street, int(number), suffix, digits + letters.upper(), city)


def address_request(address):
    # Parsed fields plus independent fixed filters confine the search to BAG addresses.
    address = AddressInput.parse(address.text)
    q = f'{address.street} {address.number}{address.suffix} {address.postcode} {address.city}'
    pairs = (('q', q), ('fq', f'type:adres AND bron:BAG AND postcode:{address.postcode} AND huisnummer:{address.number}'),
             ('fl', FIELDS), ('rows', '2'), ('start', '0'), ('wt', 'json'))
    return GetRequest(ENDPOINT + '?' + urlencode(pairs), pairs,
                      (('Accept', 'application/json'),), TIMEOUT, MAX_BYTES)


def validate_address_request(request):
    if not isinstance(request, GetRequest):
        raise ValueError('GET request required')
    try:
        q = dict(request.parameters)['q']
        expected = address_request(AddressInput.parse(q))
    except (KeyError, TypeError):
        raise ValueError('Invalid address request') from None
    if request != expected:
        raise ValueError('Exact allowlisted address request and budgets required')


class PDOKLocationTransport(PDOKLiveGetTransport):
    def __init__(self):
        pass

    def _validate_request(self, request):
        validate_address_request(request)


@dataclass(frozen=True)
class ResolvedOfficialLocation:
    official_address: str
    location_id: str
    nummeraanduiding_id: str
    adresseerbaarobject_id: str
    coordinates: tuple[float, float]
    coordinate_crs: str = 'EPSG:28992'
    coordinate_source: str = 'PDOK_LOCATIESERVER.centroide_rd'


def parse_response(address, response):
    response.__post_init__()
    headers = {}
    for key, value in response.headers:
        key = key.lower()
        if key in headers and key in ('content-type', 'content-encoding', 'content-crs'):
            raise ValueError('Duplicate response metadata')
        headers[key] = value
    if (response.status != 200 or response.origin != ResponseOrigin.PROVIDER_RESPONSE
            or len(response.body) > MAX_BYTES
            or headers.get('content-type', '').split(';')[0].strip() != 'application/json'
            or headers.get('content-encoding', 'identity') != 'identity'):
        raise ValueError('Invalid official address response metadata/budget')
    if 'content-crs' in headers and headers['content-crs'].strip('<>') not in (
            'EPSG:28992', 'http://www.opengis.net/def/crs/EPSG/0/28992'):
        raise ValueError('Unexpected coordinate CRS')
    d = strict_json(response.body.decode('utf-8'))
    if not isinstance(d, dict) or 'error' in d or any(k in d for k in ('crs', 'coordRefSys')):
        raise ValueError('Unexpected response or CRS declaration')
    if 'responseHeader' in d and (not isinstance(d['responseHeader'], dict)
            or d['responseHeader'].get('status') != 0 or d['responseHeader'].get('partialResults', False) is not False):
        raise ValueError('Partial or failed search')
    result = d.get('response')
    if (not isinstance(result, dict) or type(result.get('numFound')) is not Decimal
            or result['numFound'] != 1 or type(result.get('start')) is not Decimal or result['start'] != 0
            or result.get('numFoundExact') is not True
            or not isinstance(result.get('docs'), list) or len(result['docs']) != 1):
        raise ValueError('Exactly one unambiguous official address required')
    doc = result['docs'][0]
    if not isinstance(doc, dict) or doc.get('type') != 'adres' or doc.get('bron') != 'BAG':
        raise ValueError('Official BAG address source required')
    if any(k in doc for k in ('crs', 'coordRefSys')):
        raise ValueError('Unexpected coordinate CRS declaration')
    if (normalized(doc.get('straatnaam')) != normalized(address.street)
            or type(doc.get('huisnummer')) is not Decimal or doc['huisnummer'] != address.number
            or normalized(doc.get('postcode')) != normalized(address.postcode)
            or normalized(doc.get('woonplaatsnaam')) != normalized(address.city)):
        raise ValueError('Official address differs from supplied address')
    for key in ('huisletter', 'huisnummertoevoeging'):
        if doc.get(key) is not None and not isinstance(doc[key], str):
            raise ValueError('Text house suffix required')
    suffix = (doc.get('huisletter') or '') + (doc.get('huisnummertoevoeging') or '')
    if normalized(suffix) != normalized(address.suffix):
        raise ValueError('House suffix differs; no best-match guessing')
    for key in ('nummeraanduiding_id', 'adresseerbaarobject_id'):
        if not isinstance(doc.get(key), str) or not re.fullmatch(r'[0-9]{16}', doc[key]):
            raise ValueError('Official BAG identification missing')
    for key in ('id', 'weergavenaam'):
        if not isinstance(doc.get(key), str) or not doc[key].strip():
            raise ValueError('Official address identity/display missing')
    # The documented centroide_rd field is explicitly RD New; never infer CRS from values.
    point_text = doc.get('centroide_rd')
    if not isinstance(point_text, str):
        raise ValueError('Official 2D centroide_rd required')
    point = re.fullmatch(r'POINT\(([+-]?[0-9]+(?:\.[0-9]+)?) ([+-]?[0-9]+(?:\.[0-9]+)?)\)', point_text)
    if not point:
        raise ValueError('Official 2D centroide_rd required')
    x, y = map(Decimal, point.groups())
    if not (0 <= x <= 300000 and 280000 <= y <= 625000):
        raise ValueError('Coordinate outside bounded Dutch RD scope')
    return ResolvedOfficialLocation(doc['weergavenaam'], doc['id'], doc['nummeraanduiding_id'],
                                    doc['adresseerbaarobject_id'], (float(x), float(y)))


class AddressResolutionError(ValueError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def resolve_address(text, transport, *, live_opt_in=False):
    evidence = dict(contract=CONTRACT, address_input=text, status='BLOCKED', started=now())
    try:
        if live_opt_in is not True:
            raise ValueError('Explicit live address opt-in required')
        address = AddressInput.parse(text)
        request = address_request(address)
        evidence['request_url'] = request.url
        start = time.monotonic()
        response = transport.get(request)
        evidence.update(http_status=response.status, headers=response.headers, origin=response.origin,
                        raw_base64=base64.b64encode(response.body).decode('ascii'),
                        raw_sha256=raw_response_hash(response.body), finished=now())
        if time.monotonic() - start > TIMEOUT:
            raise TimeoutError('Address resolution budget exceeded')
        location = parse_response(address, response)
        evidence.update(status='RESOLVED', resolved=asdict(location))
        return location, evidence
    except Exception as exc:
        evidence.update(status='BLOCKED', error_type=type(exc).__name__, reason=str(exc), finished=now())
        raise AddressResolutionError(str(exc), evidence) from exc


def replay_address(evidence):
    if evidence.get('contract') != CONTRACT or evidence.get('status') != 'RESOLVED':
        raise ValueError('Successful address evidence required')
    address = AddressInput.parse(evidence['address_input'])
    if evidence['request_url'] != address_request(address).url:
        raise ValueError('Address evidence request mismatch')
    encoded = evidence['raw_base64']
    if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_BYTES + 2) // 3):
        raise ValueError('Address evidence byte budget exceeded')
    body = base64.b64decode(encoded, validate=True)
    if raw_response_hash(body) != evidence['raw_sha256']:
        raise ValueError('Address raw hash mismatch')
    response = HttpResponse(evidence['http_status'], tuple(tuple(p) for p in evidence['headers']),
                            body, ResponseOrigin(evidence['origin']))
    location = parse_response(address, response)
    if json.loads(json.dumps(asdict(location))) != json.loads(json.dumps(evidence['resolved'])):
        raise ValueError('Resolved location differs from official raw evidence')
    return location
