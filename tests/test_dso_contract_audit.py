"""Synthetic contract cases and differential proof against the reviewed commit.

No DSO calls: sockets are blocked in parent and comparison subprocesses.
The small schema oracle is test-only and covers the fixture-reachable OAS subset.
"""
import ast
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '526a52312a518fa5d4ab27943b1f4984ed6b31e0'
MODULES = ('adapters.dso_diagnostics', 'adapters.dso_contract', 'adapters.dso_discovery',
           'adapters.dso_live', 'adapters.ow_document', 'application.dso_discovery',
           'application.ow_document')
sys.path.insert(0, str(ROOT / 'src'))


def baseline_modules():
    """Read tracked baseline code without checkout, reset, or temporary stores."""
    import importlib
    for suffix in MODULES:
        name = 'bvc_ai.' + suffix
        parent, attr = name.rsplit('.', 1)
        package = importlib.import_module(parent)
        path = 'src/' + name.replace('.', '/') + '.py'
        source = subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
        module = types.ModuleType(name)
        module.__file__ = str(ROOT / path)
        module.__package__ = parent
        sys.modules[name] = module
        setattr(package, attr, module)
        exec(compile(source, module.__file__, 'exec'), module.__dict__)


if __name__ == '__main__' and '--baseline' in sys.argv:
    baseline_modules()

from bvc_ai.adapters import dso_contract as dc, dso_discovery as dd, ow_document as ow
from bvc_ai.adapters.dso_diagnostics import report
from bvc_ai.adapters.dso_live import DSOLivePostTransport, DSOLiveOWTransport
from bvc_ai.application.ow_document import OWDocumentRetrievalService
from dso_fixtures import discovery_page, imro_document
from test_dso_discovery import response as discovery_response
from test_ow_document import DAY, AVAILABLE, URI, IDENTITY, discovery, fixtures, response
from test_dso_phase2_probe import probe


def schema_check(value, schema, spec):
    """Independent OAS fixture check; no production validator or network refs."""
    if '$ref' in schema:
        assert schema['$ref'].startswith('#/components/schemas/')
        return schema_check(value, spec['components']['schemas'][schema['$ref'].split('/')[-1]], spec)
    for part in schema.get('allOf', []):
        schema_check(value, part, spec)
    if value is None and schema.get('nullable'):
        return
    kind = schema.get('type')
    if kind == 'object':
        assert type(value) is dict
        assert set(schema.get('required', [])) <= value.keys()
        for key, item in value.items():
            child = schema.get('properties', {}).get(key, schema.get('additionalProperties', True))
            assert child is not False
            if isinstance(child, dict):
                schema_check(item, child, spec)
    elif kind == 'array':
        assert type(value) is list
        assert len(value) >= schema.get('minItems', 0)
        if schema.get('uniqueItems'):
            assert len({json.dumps(v, sort_keys=True) for v in value}) == len(value)
        for item in value:
            schema_check(item, schema['items'], spec)
    elif kind == 'string':
        assert type(value) is str
        if schema.get('format') in ('date', 'date-time'):
            from datetime import date, datetime
            (datetime if schema['format'] == 'date-time' else date).fromisoformat(value.replace('Z', '+00:00'))
    elif kind == 'integer':
        assert type(value) is int
    elif kind == 'number':
        assert type(value) in (int, float)
    elif kind == 'boolean':
        assert type(value) is bool
    else:
        assert kind is None and 'allOf' in schema, 'Unsupported fixture schema'
    if 'enum' in schema:
        assert value in schema['enum']


def cases():
    request = dd.build_request([155000, 463000], DAY, AVAILABLE)
    result = []
    def add(name, data, accepted, code=None, schema_valid=False):
        result.append((name, lambda data=data: dd.parse_response(discovery_response(data), request),
                       accepted, code, (data, dc.contract(), 'Documenten') if schema_valid else None))
    add('discovery_base', discovery_page(), True, schema_valid=True)
    for mode in ('extra', 'empty', 'zero', 'pages', 'required', 'type', 'enum', 'imro',
                 'bad_imro', 'identity', 'families', 'interval', 'page_optional', 'nullable'):
        data = discovery_page()
        doc = data['_embedded']['documenten'][0]
        accepted, code, valid = False, None, False
        if mode == 'extra':
            doc['syntheticExtension'] = 'TESTDATA'; code = 'UNKNOWN_PROPERTY'; valid = True
        elif mode == 'empty':
            doc['omgevingsdocumentMetadata']['officieleTitel'] = ''; code = 'EMPTY_STRING'; valid = True
        elif mode == 'zero':
            data['_embedded']['documenten'] = []; data['page'].update(totalElements=0, totalPages=0)
            accepted = valid = True
        elif mode == 'pages':
            data['page'].update(totalElements=201, totalPages=2); code = 'PAGINATION'; valid = True
        elif mode == 'required':
            del doc['identificatie']; code = 'REQUIRED_FIELD'
        elif mode == 'type':
            doc['versie'] = True; code = 'RESPONSE_STRUCTURE'
        elif mode == 'enum':
            doc['aangeleverdDoorEen']['bestuurslaag'] = 'TESTDATA_INVALID'; code = 'VALUE_CONSTRAINT'
        elif mode in ('imro', 'bad_imro', 'nullable'):
            data['_embedded']['documenten'] = [imro_document()]; accepted = valid = True
            if mode == 'bad_imro':
                data['_embedded']['documenten'][0]['uriIdentificatie'] = 'TESTDATA_OTHER'
                accepted = False; code = 'DOCUMENT_IDENTITY'
            elif mode == 'nullable':
                data['_embedded']['documenten'][0]['imroDocumentMetadata']['regelStatus'] = None
        elif mode == 'identity':
            doc['omgevingsdocumentMetadata']['expressionId'] = 'TESTDATA_OTHER'; code = 'DOCUMENT_IDENTITY'; valid = True
        elif mode == 'families':
            del doc['omgevingsdocumentMetadata']; code = 'DOCUMENT_FAMILY'; valid = True
        elif mode == 'interval':
            doc['geldigTot'] = '2025-01-01'; code = 'TEMPORAL_INTERVAL'; valid = True
        elif mode == 'page_optional':
            data['page'] = {}; code = 'PAGINATION'; valid = True
        add('discovery_' + mode, data, accepted, code, valid)
    for name, original, parser in (
        ('discovery', discovery_response(), lambda r: dd.parse_response(r, request)),
        ('ow', response(fixtures()[0]), lambda r: ow.parse_response(
            r, ow.build_request(URI, 'metadata', DAY, AVAILABLE), 'metadata', discovery()['documents'][0]))):
        for mode in ('content_type', 'version', 'json', 'duplicate', 'encoding'):
            headers = dict(original.headers)
            body = original.body
            code = 'UNKNOWN'
            if mode == 'content_type': headers['Content-Type'] = 'text/plain'; code = 'CONTENT_TYPE'
            if mode == 'version': headers['API-Version'] = '9.9.9'
            if mode == 'encoding': headers['Content-Encoding'] = 'gzip'
            if mode == 'json': body = b'{'; code = 'RESPONSE_STRUCTURE'
            if mode == 'duplicate': body = b'{"a":1,"a":2}'; code = 'RESPONSE_STRUCTURE'
            changed = replace(original, headers=tuple(headers.items()), body=body)
            result.append((name + '_' + mode, lambda r=changed, p=parser: p(r), False, code, None))
    for i, kind in enumerate(('metadata', 'structure', 'rule_annotations')):
        data = fixtures()[i]
        result.append(('ow_base_' + kind, lambda d=data, k=kind: ow.parse_response(
            response(d), ow.build_request(URI, k, DAY, AVAILABLE), k, discovery()['documents'][0]),
            True, None, (data, ow.contract(), ow.SCHEMAS[kind])))
    for mode in ('extra', 'empty', 'required', 'type', 'identity', 'time'):
        data = fixtures()[0]; accepted = False; valid = False
        if mode == 'extra': data['syntheticExtension'] = 'TESTDATA'; code = 'UNKNOWN_PROPERTY'; valid = True
        if mode == 'empty': data['citeerTitel'] = ''; code = None; accepted = valid = True
        if mode == 'required': del data['geregistreerdMet']; code = 'REQUIRED_FIELD'
        if mode == 'type': data['officieleTitel'] = 42; code = 'RESPONSE_STRUCTURE'
        if mode == 'identity': data['expressionId'] = 'TESTDATA_OTHER'; code = 'DOCUMENT_IDENTITY'; valid = True
        if mode == 'time': data['geregistreerdMet']['beginGeldigheid'] = '2025-01-01'; code = 'TEMPORAL_INTERVAL'; valid = True
        result.append(('ow_' + mode, lambda d=data: ow.parse_response(response(d),
            ow.build_request(URI, 'metadata', DAY, AVAILABLE), 'metadata', discovery()['documents'][0]),
            accepted, code, (data, ow.contract(), 'Regeling') if valid else None))
    def retrieval():
        transport = Mock(); transport.get.side_effect = [response(d) for d in fixtures()]
        selected = discovery()
        return OWDocumentRetrievalService(transport, clock=lambda: AVAILABLE).retrieve(
            selected, IDENTITY, expected_discovery_hash=selected['discovery_hash'])
    result.append(('full_retrieval', retrieval, True, None, None))
    def network_case(get, mode):
        connection, http = Mock(), Mock(status=401 if mode == 'auth' else 200)
        connection.getresponse.return_value = http
        http.getheaders.return_value = [('Content-Type','application/hal+json'), ('API-Version','8.2.5' if get else '2.13.1')]
        http.read1.side_effect = io.BytesIO(b'{' if mode == 'json' else b'{"value":"synthetic-only-secret"}').read1
        if mode == 'network': connection.connect.side_effect = OSError('provider-private')
        with patch.dict(os.environ, {'DSO_API_KEY':'synthetic-only-secret'}), patch(
                'bvc_ai.adapters.dso_live.http.client.HTTPSConnection', return_value=connection):
            if get: return DSOLiveOWTransport(live_opt_in=True).get(ow.build_request(URI,'metadata',DAY,AVAILABLE))
            return DSOLivePostTransport(live_opt_in=True).post(request)
    for get in (False, True):
        for mode in ('auth','network','reflection','json'):
            result.append(('transport_' + str(get) + '_' + mode,
                           lambda g=get,m=mode: network_case(g,m), False,
                           'RESPONSE_STRUCTURE' if mode == 'json' else 'UNKNOWN', None))
    return result


def snapshot():
    results = {}
    with ExitStack() as stack:
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            stack.enter_context(patch(name, side_effect=AssertionError('OFFLINE')))
        for name, operation, accepted, code, schema in cases():
            try:
                value = operation()
                results[name] = dict(accepted=True, digest=dc.digest(value))
            except Exception as error:
                data = report(error)
                data.pop('validation_error_code', None)
                results[name] = dict(accepted=False, exception=type(error).__name__,
                                     message=str(error), diagnostic=data)
    return results


class ContractAuditTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE'))
            guard.start(); self.addCleanup(guard.stop)

    def test_schema_conformity_codes_and_suppressed_cli(self):
        for name, operation, accepted, code, schema in cases():
            with self.subTest(case=name):
                if schema:
                    data, spec, key = schema
                    schema_check(data, spec['components']['schemas'][key], spec)
                if accepted:
                    operation()
                    continue
                with self.assertRaises(Exception) as caught:
                    operation()
                self.assertEqual(report(caught.exception)['validation_error_code'], code)
                stream = io.StringIO()
                with patch.object(probe, 'probe', side_effect=caught.exception), redirect_stdout(stream):
                    self.assertEqual(probe.main(['--peildatum', DAY, '--beschikbaar-op', AVAILABLE]), 1)
                output = json.loads(stream.getvalue())
                self.assertEqual(set(output), {'status','details','phase','category','http_status',
                                               'contract_version','validation_error_code'})
                self.assertEqual(output['status'], 'FAILED_CLOSED')
                self.assertEqual(output['details'], 'SUPPRESSED')
                self.assertEqual(output['validation_error_code'], code)
                for secret in ('TESTDATA', IDENTITY, 'provider-private', 'synthetic-only-secret', 'X-API-Key'):
                    self.assertNotIn(secret, stream.getvalue())

    def test_exact_baseline_behavior_and_evidence(self):
        actual = snapshot()
        completed = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--baseline'],
                                   cwd=ROOT, capture_output=True, text=True, check=True, timeout=60)
        self.assertEqual(completed.stderr, '')
        self.assertEqual(actual, json.loads(completed.stdout))
        self.assertGreaterEqual(len(actual), 40)

    def test_validation_predicates_match_reviewed_source(self):
        class RemoveDiagnostics(ast.NodeTransformer):
            def visit_ImportFrom(self, node):
                node.names = [item for item in node.names
                              if item.name not in ('validation_error', 'validation_code')]
                return node if node.names else None

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == 'validation_error':
                    return self.visit(node.args[0])
                node = self.generic_visit(node)
                if isinstance(node.func, ast.Name) and node.func.id == 'reject':
                    node.args = []
                return node

            def visit_Expr(self, node):
                if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == 'validation_error'):
                    return None
                return self.generic_visit(node)

            def visit_FunctionDef(self, node):
                if node.name == 'reject':
                    node.args.args = []
                    node.args.defaults = []
                return self.generic_visit(node)

        for suffix in MODULES[1:]:
            with self.subTest(module=suffix):
                path = 'src/bvc_ai/' + suffix.replace('.', '/') + '.py'
                before = subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
                after = (ROOT / path).read_bytes()
                def normalized(source):
                    return ast.dump(RemoveDiagnostics().visit(ast.parse(source)), include_attributes=False)
                self.assertEqual(normalized(before), normalized(after))

    def test_closed_code_vocabulary_no_exception_parsing(self):
        from bvc_ai.adapters.dso_diagnostics import validation_error, VALIDATION_CODES
        for code in (*VALIDATION_CODES, 'provider-private', {}, ['CONTENT_TYPE'], None):
            error = ValueError('provider-private CONTENT_TYPE REQUIRED_FIELD /secret/path')
            validation_error(error, code)
            self.assertEqual(report(error)['validation_error_code'],
                             code if type(code) is str and code in VALIDATION_CODES else 'UNKNOWN')
        self.assertEqual(report(ValueError('CONTENT_TYPE'))['validation_error_code'], 'UNKNOWN')


if __name__ == '__main__':
    if '--baseline' in sys.argv:
        print(json.dumps(snapshot(), sort_keys=True))
    else:
        unittest.main()
