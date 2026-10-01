"""Closed BAG Individual Queries v2 bootstrap; no import/approval capability."""
import base64
from dataclasses import dataclass, asdict
from decimal import Decimal
import http.client
import json
import math
import os
import queue
import re
import socket
import threading
import time
from urllib.parse import urlencode, urlsplit, parse_qsl, quote

from bvc_ai.adapters.pdok_location import AddressInput, ResolvedOfficialLocation, normalized
from bvc_ai.adapters.source_transport import GetRequest, HttpResponse, ResponseOrigin
from bvc_ai.domain.models import now
from bvc_ai.domain.source_hashing import strict_json, raw_response_hash

HOST = 'api.bag.kadaster.nl'
ENDPOINT = 'https://' + HOST + '/lvbag/individuelebevragingen/v2/adressenuitgebreid'
CONTRACT = 'BAG_INDIVIDUAL_ADDRESS_V2_V1'
HEADERS = (('Accept', 'application/hal+json'), ('Accept-Crs', 'epsg:28992'))
MAX_BYTES = 256 * 1024
TIMEOUT = 20.0


def require(condition, code):
    if not condition:
        raise ValueError(code)


def request_for(address):
    address = AddressInput.parse(address.text)
    pairs = [('postcode', address.postcode), ('huisnummer', str(address.number))]
    suffix = address.suffix
    if suffix:
        if re.fullmatch('[A-Za-z]', suffix):
            pairs.append(('huisletter', suffix))
        elif re.fullmatch('[A-Za-z]-[A-Za-z0-9]{1,4}', suffix):
            pairs.extend([('huisletter', suffix[0]), ('huisnummertoevoeging', suffix[2:])])
        else:
            value = suffix.removeprefix('-')
            require(bool(re.fullmatch('[A-Za-z0-9]{1,4}', value)), 'BAG_UNSUPPORTED_SUFFIX')
            pairs.append(('huisnummertoevoeging', value))
    pairs.extend([('exacteMatch','true'),('inclusiefEindStatus','false'),('page','1'),('pageSize','10')])
    return GetRequest(ENDPOINT + '?' + urlencode(pairs), tuple(pairs), HEADERS, TIMEOUT, MAX_BYTES)


def validate_request(request):
    require(isinstance(request, GetRequest), 'BAG_REQUEST_INVALID')
    parts = urlsplit(request.url)
    pairs = tuple(parse_qsl(parts.query, keep_blank_values=True))
    params = dict(pairs)
    require(request.url == ENDPOINT + '?' + urlencode(request.parameters)
        and pairs == request.parameters and len(params) == len(pairs)
        and request.headers == HEADERS and request.timeout_seconds == TIMEOUT
        and request.max_response_bytes == MAX_BYTES, 'BAG_REQUEST_OUTSIDE_ALLOWLIST')
    allowed = {'postcode','huisnummer','huisletter','huisnummertoevoeging','exacteMatch','inclusiefEindStatus','page','pageSize'}
    require(set(params) <= allowed and re.fullmatch('[1-9][0-9]{3}[A-Z]{2}',params.get('postcode',''))
        and re.fullmatch('[1-9][0-9]{0,4}',params.get('huisnummer',''))
        and all(params.get(k)==v for k,v in (('exacteMatch','true'),('inclusiefEindStatus','false'),('page','1'),('pageSize','10')))
        and ('huisletter' not in params or re.fullmatch('[A-Za-z]',params['huisletter']))
        and ('huisnummertoevoeging' not in params or re.fullmatch('[A-Za-z0-9]{1,4}',params['huisnummertoevoeging'])), 'BAG_QUERY_INVALID')


class BAGTransportError(ValueError):
    """Only static error codes cross this boundary, never upstream error text."""


class BAGLiveTransport:
    def get(self, request):
        validate_request(request)  # Reject scope before looking up any credential.
        secret = os.environ.get('BAG_API_KEY')
        if not secret or not secret.isascii() or any(c.isspace() or ord(c)<33 for c in secret):
            raise BAGTransportError('BAG_CREDENTIAL_UNAVAILABLE')
        deadline = time.monotonic() + TIMEOUT
        result = queue.Queue(maxsize=1)
        cancelled = threading.Event()
        conn = http.client.HTTPSConnection(HOST, timeout=TIMEOUT)
        conn.set_debuglevel(0)
        def remaining():
            left = deadline-time.monotonic()
            if cancelled.is_set() or left <= 0:
                raise TimeoutError()
            return left
        def receive():
            try:
                conn.connect()
                conn.sock.settimeout(remaining())
                parts = urlsplit(request.url)
                conn.request('GET',parts.path+'?'+parts.query,headers={
                    **dict(HEADERS),'Accept-Encoding':'identity','X-Api-Key':secret})
                conn.sock.settimeout(remaining())
                response = conn.getresponse()
                headers = tuple(response.getheaders())
                chunks, size = [], 0
                while True:
                    if conn.sock is not None: conn.sock.settimeout(remaining())
                    chunk = response.read1(min(65536,MAX_BYTES-size+1))
                    remaining()
                    if not chunk: break
                    size += len(chunk)
                    if size > MAX_BYTES: raise ValueError()
                    chunks.append(chunk)
                body = b''.join(chunks)
                # Discard complete responses that echo credentials; never modify raw evidence.
                wire = body + json.dumps(headers).encode()
                for token in (secret.encode(),quote(secret,safe='').encode(),base64.b64encode(secret.encode())):
                    if token in wire: raise ValueError()
                lengths = [v for k,v in headers if k.lower()=='content-length']
                if lengths and (len(lengths)!=1 or not lengths[0].isdigit() or int(lengths[0])!=size): raise ValueError()
                safe = tuple((k,v) for k,v in headers if k.lower() in {
                    'content-type','content-crs','content-length','content-encoding','api-version','date',
                    'x-pagination-page','x-pagination-limit'})
                result.put(HttpResponse(response.status,safe,body,ResponseOrigin.PROVIDER_RESPONSE))
            except Exception:
                result.put(None)  # Never expose an exception containing header/credential values.
            finally:
                conn.close()
        threading.Thread(target=receive,name='bag-bounded-get',daemon=True).start()
        try:
            response = result.get(timeout=remaining())
            remaining()
            if response is None: raise BAGTransportError('BAG_TRANSPORT_FAILED')
            return response
        except (queue.Empty,TimeoutError):
            raise BAGTransportError('BAG_REQUEST_DEADLINE') from None
        finally:
            cancelled.set()
            if conn.sock is not None:
                try: conn.sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            conn.close()


@dataclass(frozen=True)
class BAGLocation(ResolvedOfficialLocation):
    pand_ids: tuple[str, ...] = ()
    openbare_ruimte_id: str = ''
    woonplaats_id: str = ''
    source_coordinates: tuple[float, ...] = ()


def parse_response(address, response):
    response.__post_init__()
    headers = {}
    for k,v in response.headers:
        k = k.lower()
        require(k not in headers,'BAG_DUPLICATE_RESPONSE_HEADER')
        headers[k] = v
    require(response.status==200 and response.origin==ResponseOrigin.PROVIDER_RESPONSE
        and len(response.body)<=MAX_BYTES and headers.get('content-type','').split(';')[0]=='application/hal+json'
        and headers.get('content-encoding','identity')=='identity', 'BAG_RESPONSE_INVALID')
    # The official v2 contract defines native RD; Accept-Crs is deprecated in that contract.
    require(headers.get('content-crs','epsg:28992').lower()=='epsg:28992','BAG_CRS_UNEXPECTED')
    if 'api-version' in headers: require(headers['api-version'].split('.')[0]=='2','BAG_VERSION_UNEXPECTED')
    if 'x-pagination-page' in headers: require(headers['x-pagination-page']=='1','BAG_PAGE_UNEXPECTED')
    data = strict_json(response.body.decode('utf-8'))
    require(isinstance(data,dict) and not any(k in data for k in ('error','crs','coordRefSys')),'BAG_DOCUMENT_INVALID')
    links = data.get('_links',{})
    require(isinstance(links,dict) and not any(k in links for k in ('next','previous')),'BAG_INCOMPLETE_SEARCH')
    docs = data.get('_embedded',{}).get('adressen')
    require(isinstance(docs,list) and len(docs)==1,'BAG_ADDRESS_NOT_UNIQUE')
    doc = docs[0]
    require(isinstance(doc,dict),'BAG_ADDRESS_INVALID')
    for source,expected in (('openbareRuimteNaam',address.street),('woonplaatsNaam',address.city),('postcode',address.postcode)):
        require(normalized(doc.get(source))==normalized(expected),'BAG_ADDRESS_MISMATCH')
    require(type(doc.get('huisnummer')) is Decimal and doc['huisnummer']==address.number,'BAG_NUMBER_MISMATCH')
    suffix = ''.join(doc.get(k) or '' for k in ('huisletter','huisnummertoevoeging'))
    require(normalized(suffix)==normalized(address.suffix),'BAG_SUFFIX_MISMATCH')
    require(doc.get('typeAdresseerbaarObject')=='Verblijfsobject','BAG_POINT_BOOTSTRAP_REQUIRES_VERBLIJFSOBJECT')
    def identity(field,pattern):
        value=doc.get(field)
        require(isinstance(value,str) and re.fullmatch(pattern,value),'BAG_ID_INVALID')
        return value
    num=identity('nummeraanduidingIdentificatie',r'[0-9]{4}20[0-9]{10}')
    obj=identity('adresseerbaarObjectIdentificatie',r'[0-9]{4}01[0-9]{10}')
    public=identity('openbareRuimteIdentificatie',r'[0-9]{4}30[0-9]{10}')
    city=identity('woonplaatsIdentificatie',r'[0-9]{4}')
    pand=doc.get('pandIdentificaties')
    require(isinstance(pand,list) and pand and all(isinstance(v,str) and re.fullmatch(r'[0-9]{4}10[0-9]{10}',v) for v in pand)
        and len(set(pand))==len(pand),'BAG_PAND_IDS_INVALID')
    research=doc.get('inonderzoek',{})
    require(isinstance(research,dict) and all(v is False for v in research.values()),'BAG_ADDRESS_UNDER_INVESTIGATION')
    geometry=doc.get('adresseerbaarObjectGeometrie',{})
    require(isinstance(geometry,dict) and set(geometry)=={'punt'},'BAG_OFFICIAL_POINT_REQUIRED')
    point=geometry['punt']
    require(isinstance(point,dict) and set(point)=={'type','coordinates'} and point['type']=='Point','BAG_POINT_INVALID')
    coords=point['coordinates']
    require(isinstance(coords,list) and len(coords) in (2,3) and all(type(n) is Decimal and n.is_finite() for n in coords),'BAG_COORDINATES_INVALID')
    require(all(math.isfinite(float(n)) for n in coords),'BAG_COORDINATES_INVALID')
    require(0<=coords[0]<=300000 and 280000<=coords[1]<=625000,'BAG_COORDINATES_OUT_OF_SCOPE')
    display=f"{doc['openbareRuimteNaam']} {address.number}{suffix}, {doc['postcode']} {doc['woonplaatsNaam']}"
    return BAGLocation(display,num,num,obj,tuple(float(n) for n in coords[:2]),
        coordinate_source='BAG_INDIVIDUAL_V2.adresseerbaarObjectGeometrie.punt',
        pand_ids=tuple(pand),openbare_ruimte_id=public,woonplaats_id=city,source_coordinates=tuple(float(n) for n in coords))


def resolve_address(text, transport, *, live_opt_in=False):
    evidence=dict(contract=CONTRACT,address_input=text,status='BLOCKED',started=now())
    try:
        require(live_opt_in is True,'BAG_LIVE_OPT_IN_REQUIRED')
        address=AddressInput.parse(text)
        request=request_for(address)
        response=transport.get(request)
        evidence.update(request_url=request.url,http_status=response.status,headers=response.headers,origin=response.origin,
            raw_base64=base64.b64encode(response.body).decode(),raw_sha256=raw_response_hash(response.body),finished=now())
        location=parse_response(address,response)
        evidence.update(status='RESOLVED',resolved=asdict(location))
        return location,evidence
    except Exception as exc:
        # No arbitrary exception text (including fake transport exceptions) crosses to logs.
        from bvc_ai.adapters.pdok_location import AddressResolutionError
        code = str(exc) if isinstance(exc,BAGTransportError) and str(exc) in {'BAG_CREDENTIAL_UNAVAILABLE', 'BAG_TRANSPORT_FAILED', 'BAG_REQUEST_DEADLINE'} else 'BAG_BOOTSTRAP_VALIDATION_FAILED'
        evidence.update(status='BLOCKED',reason=code,finished=now())
        raise AddressResolutionError(code,evidence) from None


def replay_address(evidence):
    require(evidence.get('contract')==CONTRACT and evidence.get('status')=='RESOLVED','BAG_EVIDENCE_INVALID')
    address=AddressInput.parse(evidence['address_input'])
    require(request_for(address).url==evidence['request_url'],'BAG_EVIDENCE_SCOPE_MISMATCH')
    require(isinstance(evidence['raw_base64'],str) and len(evidence['raw_base64'])<=4*((MAX_BYTES+2)//3),'BAG_EVIDENCE_BUDGET')
    raw=base64.b64decode(evidence['raw_base64'],validate=True)
    require(raw_response_hash(raw)==evidence['raw_sha256'],'BAG_RAW_HASH_MISMATCH')
    response=HttpResponse(evidence['http_status'],tuple(tuple(h) for h in evidence['headers']),raw,ResponseOrigin(evidence['origin']))
    location=parse_response(address,response)
    require(json.loads(json.dumps(asdict(location)))==json.loads(json.dumps(evidence['resolved'])),'BAG_EVIDENCE_RESULT_MISMATCH')
    return location
