"""Closed OW regeling retrieval profile, pinned to official Presenteren 8.2.5."""
from copy import deepcopy
from datetime import timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

from bvc_ai.adapters.dso_contract import canonical, date_value, digest, read_json, reject
from bvc_ai.adapters.dso_discovery import HOST
from bvc_ai.adapters.source_transport import GetRequest, HttpResponse, ResponseOrigin

BASE = 'https://' + HOST + '/publiek/omgevingsdocumenten/api/presenteren/v8'
CONTRACT_URL = 'https://developer.omgevingswet.overheid.nl/publish/pages/166112/omgevingsdocumenten-presenteren-v8.json'
VERSION = '8.2.5'
CONTRACT_HASH = '37d70096ae6bd338a6b7824da12512a6375644bf20171613da4fbc8843a2105d'
KINDS = {'metadata': '', 'structure': '/documentstructuur',
         'rule_annotations': '/regeltekstannotaties', 'division_annotations': '/divisieannotaties'}
SCHEMAS = {'metadata': 'Regeling', 'structure': 'Documentstructuur',
           'rule_annotations': 'RegeltekstannotatiesVastgesteld',
           'division_annotations': 'DivisieannotatiesVastgesteld'}


def contract():
    raw = (Path(__file__).resolve().parents[3] / 'docs/contracts/dso/presenteren-v8.openapi.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_HASH:
        raise ValueError('Changed Presenteren contract')
    return json.loads(raw)


def _schema(schema, spec):
    if '$ref' in schema:
        return _schema(spec['components']['schemas'][schema['$ref'].split('/')[-1]], spec)
    result = {k: deepcopy(v) for k, v in schema.items() if k != 'allOf'}
    properties, required = {}, []
    for part in schema.get('allOf', []):
        child = _schema(part, spec)
        properties.update(child.get('properties', {}))
        required.extend(child.get('required', []))
        result.setdefault('type', child.get('type'))
    properties.update(result.get('properties', {}))
    required.extend(result.get('required', []))
    if properties:
        result['properties'] = properties
        result['required'] = list(set(required))
    return result


def _validate(value, schema, spec, depth=0):
    if depth > 80:
        reject()
    schema = _schema(schema, spec)
    kind = schema.get('type')
    if kind == 'object':
        if type(value) is not dict or not set(schema.get('required', [])) <= value.keys():
            reject()
        props = schema.get('properties', {})
        if set(value) - props.keys():
            reject()
        for key, item in value.items():
            if key in ('geometry', 'geometrie', 'boundingBox'):
                raise ValueError('Geometry payload outside OW retrieval scope')
            _validate(item, props[key], spec, depth + 1)
    elif kind == 'array':
        if type(value) is not list or len(value) < schema.get('minItems', 0):
            reject()
        for item in value:
            _validate(item, schema['items'], spec, depth + 1)
    elif kind == 'string':
        if type(value) is not str:
            reject()
        if schema.get('format') in ('date', 'date-time'):
            date_value(value, timestamp=schema['format'] == 'date-time')
    elif kind == 'boolean':
        if type(value) is not bool:
            reject()
    elif kind in ('integer', 'number'):
        if type(value) not in ((int,) if kind == 'integer' else (int, float)) or not math.isfinite(value):
            reject()
    else:
        reject()
    if 'enum' in schema and value not in schema['enum']:
        reject()


def build_request(uri, kind, day, available):
    if type(uri) is not str or not re.fullmatch(r'_akn_nl_act_[A-Za-z0-9_]+', uri) or kind not in KINDS:
        raise ValueError('Unsupported OW retrieval identity or endpoint')
    date_value(day)
    stamp = date_value(available, timestamp=True)
    # Presenteren rounds availability upward to whole seconds. No implicit rounding.
    fraction = re.search(r'\.(\d+)', available)
    if fraction and any(c != '0' for c in fraction[1]):
        raise ValueError('Whole-second discovery availability required for OW retrieval')
    available = stamp.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    parameters = [('geldigOp', day), ('inWerkingOp', day), ('beschikbaarOp', available)]
    if kind != 'structure':
        parameters.append(('_expand', 'false'))
    parameters = tuple(parameters)
    return GetRequest(BASE + '/regelingen/' + uri + KINDS[kind] + '?' + urlencode(parameters),
                      parameters, (('Accept', 'application/hal+json'),),
                      timeout_seconds=15, max_response_bytes=4 * 1024 * 1024)


def validate_request(request):
    if type(request) is not GetRequest:
        reject()
    try:
        path = urlsplit(request.url).path
        match = re.fullmatch(r'/publiek/omgevingsdocumenten/api/presenteren/v8/regelingen/([^/]+)(/.*)?', path)
        if match is None:
            reject()
        kind = next(k for k, suffix in KINDS.items() if suffix == (match[2] or ''))
        params = dict(request.parameters)
        expected = build_request(match[1], kind, params['geldigOp'], params['beschikbaarOp'])
    except (ValueError, KeyError, TypeError, StopIteration):
        raise ValueError('Invalid OW retrieval request') from None
    if (request.url != expected.url or request.parameters != expected.parameters
            or request.headers != expected.headers or request.method != 'GET'
            or type(request.timeout_seconds) not in (int, float)
            or not 0 < request.timeout_seconds <= 15
            or type(request.max_response_bytes) is not int
            or not 0 < request.max_response_bytes <= 4 * 1024 * 1024):
        raise ValueError('Invalid OW retrieval request')


def _link(href, uri, suffix, parameters):
    """Validate same document/time coordinates; links are never used as requests."""
    parts = urlsplit(href)
    expected = BASE + '/regelingen/' + uri + suffix
    if parts.scheme + '://' + parts.netloc + parts.path != expected or parts.fragment:
        raise ValueError('Conflicting OW identity link')
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    if len(pairs) != len(dict(pairs)):
        reject()
    params = dict(pairs)
    expected_params = dict(parameters)
    for name in ('geldigOp', 'inWerkingOp', 'beschikbaarOp'):
        if name not in params:
            raise ValueError('Missing OW temporal link binding')
        if name == 'beschikbaarOp':
            if date_value(params[name], timestamp=True) != date_value(expected_params[name], timestamp=True):
                reject()
        elif params[name] != expected_params[name]:
            reject()
    if set(params) - (set(expected_params) | {'_expand'}):
        reject()
    if '_expand' in params and params['_expand'] != 'false':
        reject()


def parse_response(response, request, kind, selected):
    validate_request(request)
    if type(response) is not HttpResponse or response.status != 200 or len(response.body) > request.max_response_bytes:
        reject()
    headers = {}
    for name, value in response.headers:
        if name.lower() in headers:
            reject()
        headers[name.lower()] = value
    if (headers.get('api-version') != VERSION
            or headers.get('content-type', '').split(';')[0].strip() != 'application/hal+json'
            or headers.get('content-encoding', 'identity') != 'identity'):
        reject()
    data = read_json(response.body)
    spec = contract()
    _validate(data, spec['components']['schemas'][SCHEMAS[kind]], spec)
    uri = selected['identificatie'].replace('/', '_').replace('-', '_')
    if '_links' not in data:
        raise ValueError('Incomplete OW response binding')
    links = data['_links']
    _link(links['self']['href'], uri, KINDS[kind], request.parameters)
    if kind == 'metadata':
        registration = data['geregistreerdMet']
        if (data['identificatie'] != selected['identificatie']
                or data.get('expressionId') != selected['omgevingsdocumentMetadata']['expressionId']
                or registration.get('versie') != selected['versie']
                or data['type']['waarde'] != selected['type']
                or data['aangeleverdDoorEen']['code'] != selected['aangeleverdDoorEen']['code']):
            raise ValueError('OW discovery identity/version mismatch')
        for discovery_field, source_field, timestamp in (
                ('geldigVanaf', 'beginGeldigheid', False), ('inwerkingVanaf', 'beginInwerking', False),
                ('beschikbaarVanaf', 'tijdstipRegistratie', True), ('geldigTot', 'eindGeldigheid', False),
                ('beschikbaarTot', 'eindRegistratie', True)):
            if discovery_field in selected and (
                    source_field not in registration or
                    date_value(selected[discovery_field], timestamp=timestamp) !=
                    date_value(registration[source_field], timestamp=timestamp)):
                raise ValueError('OW discovery temporal metadata mismatch')
        _link(links['documentstructuur']['href'], uri, '/documentstructuur', request.parameters)
    else:
        _link(links['regeling']['href'], uri, '', request.parameters)
    if kind == 'structure':
        seen = set()
        def visit(nodes):
            if not nodes:
                raise ValueError('Empty or incomplete OW document structure')
            for node in nodes:
                if not node['identificatie'].strip() or not node['expressie'].strip() or node['identificatie'] in seen:
                    raise ValueError('Ambiguous OW component identity')
                seen.add(node['identificatie'])
                children = node.get('_embedded', {}).get('documentComponenten', [])
                if children:
                    visit(children)
                elif not node.get('inhoud') and not node.get('gereserveerd') and not node.get('vervallen'):
                    raise ValueError('Incomplete OW leaf component')
        visit(data['_embedded']['documentComponenten'])
    if kind.endswith('annotations'):
        if not any(k != '_links' for k in data):
            raise ValueError('Incomplete OW annotations')
        _link(links['documentstructuur']['href'], uri, '/documentstructuur', request.parameters)
    return data


class OWDocumentAdapter:
    def __init__(self, transport, clock):
        self._transport, self._clock = transport, clock

    def fetch(self, selected, kind, day, available):
        uri = selected['identificatie'].replace('/', '_').replace('-', '_')
        request = build_request(uri, kind, day, available)
        started = self._clock()
        date_value(started, timestamp=True)
        response = self._transport.get(request)
        parsed = parse_response(response, request, kind, selected)
        finished = self._clock()
        if date_value(finished, timestamp=True) < date_value(started, timestamp=True):
            reject()
        return dict(source=parsed, raw_response_utf8=response.body.decode('utf-8'),
                    provenance=dict(endpoint=request.url, method='GET', query_parameters=dict(request.parameters),
                                    request_headers=dict(request.headers),
                                    request_hash=digest(dict(url=request.url, headers=request.headers)),
                                    response_hash=hashlib.sha256(response.body).hexdigest(),
                                    api_version=VERSION, contract_sha256=CONTRACT_HASH, contract_url=CONTRACT_URL,
                                    source_status=ResponseOrigin(response.origin).value,
                                    retrieval_started_at=started, retrieval_finished_at=finished))
