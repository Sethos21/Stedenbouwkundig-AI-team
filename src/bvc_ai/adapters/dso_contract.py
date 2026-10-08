"""Pinned official Ontsluiten 2.13.1 contract; no runtime schema download."""
from datetime import date, datetime
import hashlib
import json
import re
from pathlib import Path
from bvc_ai.adapters.dso_diagnostics import mark

CONTRACT_URL = 'https://service.omgevingswet.overheid.nl/publiek/omgevingsinformatie/api/ontsluiten/v2/openapi.json'
CONTRACT_VERSION = '2.13.1'
CONTRACT_SHA256 = '4b2c33dc2a91a8c9073042978636f5222802395c3f1664b82c0c425eb126e0b4'


def reject():
    raise ValueError('Invalid or unsupported DSO contract data')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def date_value(value, *, timestamp=False):
    if type(value) is not str:
        reject()
    if timestamp and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})', value):
        reject()
    try:
        parsed = datetime.fromisoformat(value) if timestamp else date.fromisoformat(value)
        valid = (parsed.tzinfo is not None and 'T' in value) if timestamp else parsed.isoformat() == value
    except (ValueError, TypeError):
        reject()
    if not valid:
        reject()
    return parsed


def read_json(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                reject()
            result[key] = value
        return result
    def constant(_):
        reject()
    try:
        return json.loads(body, object_pairs_hook=unique, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('Invalid DSO JSON') from None


def contract():
    path = Path(__file__).resolve().parents[3] / 'docs/contracts/dso/ontsluiten-v2.openapi.json'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise mark(ValueError('Changed pinned DSO contract'), 'validatie', 'CONTRACT_VERSION_MISMATCH')
    return json.loads(raw)


def validate(value, schema, spec):
    """Strict supported object subset of the pinned OAS (no remote refs).

    Unknown properties fail closed even where OAS leaves them open. The discovery
    response uses refs, objects, arrays, scalar types, enums and date formats only.
    """
    if '$ref' in schema:
        ref = schema['$ref'].split('/')
        if ref[:3] != ['#', 'components', 'schemas']:
            reject()
        return validate(value, spec['components']['schemas'][ref[3]], spec)
    if value is None and schema.get('nullable'):
        return
    kind = schema.get('type', 'object' if 'properties' in schema else None)
    if kind == 'object':
        if type(value) is not dict or not set(schema.get('required', [])) <= value.keys():
            reject()
        properties = schema.get('properties', {})
        for key, item in value.items():
            child = properties.get(key, schema.get('additionalProperties'))
            if type(child) is not dict:
                reject()
            validate(item, child, spec)
    elif kind == 'array':
        if type(value) is not list or len(value) < schema.get('minItems', 0):
            reject()
        if schema.get('uniqueItems') and len({canonical(v) for v in value}) != len(value):
            reject()
        for item in value:
            validate(item, schema['items'], spec)
    elif kind == 'string':
        if type(value) is not str or not value.strip():
            reject()
        if schema.get('format') in ('date', 'date-time'):
            date_value(value, timestamp=schema['format'] == 'date-time')
    elif kind == 'integer':
        if type(value) is not int:
            reject()
    elif kind == 'boolean':
        if type(value) is not bool:
            reject()
    else:
        reject()
    if 'enum' in schema and value not in schema['enum']:
        reject()
