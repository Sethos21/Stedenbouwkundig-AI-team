"""Issue #6: synthetic TESTDATA; run through scripts/run_a06_identity.py."""
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch
from dso_fixtures import discovery_page
from test_dso_discovery import response as discovery_response
from test_ow_document import DAY, AVAILABLE, IDENTITY, URI, fixtures, response
from bvc_ai.adapters import dso_discovery as dd, ow_document as ow
from bvc_ai.adapters.dso_contract import digest
from bvc_ai.adapters.dso_diagnostics import report
from bvc_ai.application.dso_discovery import DSODiscoveryService
from bvc_ai.application.ow_document import OWDocumentRetrievalService


def document(identity=IDENTITY, version=1, expression=None):
    doc = discovery_page()['_embedded']['documenten'][0]
    doc.update(identificatie=identity, uriIdentificatie=identity.replace('/', '_'), versie=version)
    doc['omgevingsdocumentMetadata']['expressionId'] = expression or identity + '/nld@2026-01-01;1'
    return doc


def page(*docs):
    data = discovery_page()
    data['_embedded']['documenten'] = list(docs)
    data['page']['totalElements'] = len(docs)
    return data


def discovery(*docs):
    transport = Mock()
    transport.post.return_value = discovery_response(page(*docs))
    return DSODiscoveryService(transport, clock=lambda: AVAILABLE).discover_point(
        [155000, 463000], peildatum=DAY, beschikbaar_op=AVAILABLE)


def bound_responses(doc):
    """Rebind synthetic fixtures only; no production normalization helper."""
    data = fixtures()
    uri = doc['identificatie'].replace('/', '_').replace('-', '_')
    for row in data:
        row['_links'] = {key: dict(link, href=link['href'].replace(
            '/regelingen/' + URI, '/regelingen/' + uri)) for key, link in row['_links'].items()}
    for row in (data[0], data[3]):
        row['identificatie'] = doc['identificatie']
        row['expressionId'] = doc['omgevingsdocumentMetadata']['expressionId']
        row['geregistreerdMet']['versie'] = doc['versie']
    return data


class IdentityCharacterizationTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('OFFLINE IDENTITY TEST'))
            guard.start()
            self.addCleanup(guard.stop)

    def reject(self, operation, message, code='DOCUMENT_IDENTITY'):
        with self.assertRaisesRegex(ValueError, message) as caught:
            operation()
        diagnostic = report(caught.exception)
        self.assertEqual(diagnostic['validation_error_code'], code)
        self.assertNotIn('message', diagnostic)

    def parse(self, *docs):
        return dd.parse_response(discovery_response(page(*docs)),
                                 dd.build_request([155000, 463000], DAY, AVAILABLE))

    def retrieve(self, package, identity, rows):
        self.transport = Mock()
        self.transport.get.side_effect = [response(row) for row in rows]
        return OWDocumentRetrievalService(self.transport, clock=lambda: AVAILABLE).retrieve(
            package, identity, expected_discovery_hash=package['discovery_hash'])

    def test_slash_only_discovery_preserves_hyphen_and_source(self):
        doc = document(IDENTITY + '-deel')
        original = deepcopy(doc)
        self.assertEqual(self.parse(doc), [original])
        self.assertEqual(doc, original)
        changed = deepcopy(doc)
        changed['uriIdentificatie'] = changed['uriIdentificatie'].replace('-', '_')
        self.reject(lambda: self.parse(changed), 'Ambiguous DSO expression identity')

    def test_presenteren_hyphen_endpoint_and_full_binding(self):
        doc = document(IDENTITY + '-deel')
        rows = bound_responses(doc)
        result = self.retrieve(discovery(doc), doc['identificatie'], rows)
        self.assertEqual(result['selected_discovery_document'], doc)
        self.assertEqual([e['source'] for e in result['source_evidence']], rows)
        self.assertEqual(self.transport.get.call_count, 4)
        self.assertIn('/regelingen/' + URI + '_deel?', self.transport.get.call_args_list[0].args[0].url)
        self.reject(lambda: ow.build_request(doc['uriIdentificatie'], 'metadata', DAY, AVAILABLE),
                    'Unsupported OW retrieval identity or endpoint')

    def test_discovery_duplicate_identity_even_with_other_version(self):
        for version in (1, 2):
            with self.subTest(version=version):
                self.reject(lambda: self.parse(document(), document(version=version)),
                            'Ambiguous DSO document identity')

    def test_discovery_slash_underscore_collision_is_rejected(self):
        left, right = document(IDENTITY + '/deel'), document(IDENTITY + '_deel')
        self.assertNotEqual(left['identificatie'], right['identificatie'])
        self.assertEqual(left['uriIdentificatie'], right['uriIdentificatie'])
        for docs in ((left, right), (right, left)):
            with self.subTest(order=[d['identificatie'] for d in docs]):
                self.reject(lambda: self.parse(*docs), 'Ambiguous DSO document identity')

    def test_discovery_duplicate_expression_with_distinct_work_prefixes(self):
        expression = IDENTITY + '/deel/nld@2026-01-01;1'
        left, right = document(expression=expression), document(IDENTITY + '/deel', expression=expression)
        self.assertEqual(self.parse(left), [left])
        self.assertEqual(self.parse(right), [right])
        self.reject(lambda: self.parse(left, right), 'Ambiguous DSO expression identity')

    def test_discovery_expression_is_prefix_check_not_version_parser(self):
        for expression in (IDENTITY + '/arbitrary-TESTDATA', IDENTITY + '/nld@2026-01-01;999'):
            with self.subTest(expression=expression):
                doc = document(expression=expression)
                self.assertEqual(self.parse(doc), [doc])
        self.reject(lambda: self.parse(document(expression=IDENTITY + '-other/nld@2026-01-01;1')),
                    'Ambiguous DSO expression identity')

    def test_discovery_negative_version_and_zero(self):
        self.assertEqual(self.parse(document(version=0))[0]['versie'], 0)
        self.reject(lambda: self.parse(document(version=-1)), 'Ambiguous DSO document identity')

    def test_presenteren_hyphen_underscore_collision_keeps_exact_selection(self):
        left, right = document(IDENTITY + '-deel'), document(IDENTITY + '_deel')
        package = discovery(left, right)
        self.assertEqual(len(package['documents']), 2)
        endpoints = []
        for doc in (left, right):
            result = self.retrieve(package, doc['identificatie'], bound_responses(doc))
            self.assertEqual(result['selected_discovery_document'], doc)
            endpoints.append(self.transport.get.call_args_list[0].args[0].url)
        self.assertEqual(*endpoints)
        self.reject(lambda: self.retrieve(package, left['identificatie'], bound_responses(right)),
                    'OW discovery identity/version mismatch')
        self.assertEqual(self.transport.get.call_count, 1)

    def test_presenteren_exact_expression_and_version_not_normalized(self):
        doc = document()
        for field in ('expression', 'version', 'missing_expression', 'missing_version'):
            with self.subTest(field=field):
                rows = bound_responses(doc)
                if field == 'expression':
                    rows[0]['expressionId'] = IDENTITY + '/nld@2026-01-01;2'
                elif field == 'version':
                    rows[0]['geregistreerdMet']['versie'] = 2
                elif field == 'missing_expression':
                    del rows[0]['expressionId']
                else:
                    del rows[0]['geregistreerdMet']['versie']
                self.reject(lambda: self.retrieve(discovery(doc), IDENTITY, rows),
                            'OW discovery identity/version mismatch')

    def test_hal_conflicting_document_in_each_response_kind(self):
        for index, relation in ((0, 'self'), (0, 'documentstructuur'),
                                (1, 'regeling'), (2, 'regeling'), (2, 'documentstructuur')):
            with self.subTest(index=index, relation=relation):
                rows = fixtures()
                rows[index]['_links'][relation]['href'] = rows[index]['_links'][relation]['href'].replace(
                    '/regelingen/' + URI, '/regelingen/' + URI + '_other')
                self.reject(lambda: self.retrieve(discovery(document()), IDENTITY, rows),
                            'Conflicting OW identity link')
                self.assertEqual(self.transport.get.call_count, index + 1)

    def test_hal_annotation_document_conflict_stops_before_structure(self):
        rows = fixtures()
        rows[0]['_links']['annotaties']['href'] = rows[0]['_links']['annotaties']['href'].replace(
            '/regelingen/' + URI, '/regelingen/' + URI + '_other')
        self.reject(lambda: self.retrieve(discovery(document()), IDENTITY, rows),
                    'Unsupported official annotation endpoint')
        self.assertEqual(self.transport.get.call_count, 1)

    def test_hal_same_document_wrong_time_is_temporal_not_identity(self):
        rows = fixtures()
        rows[0]['_links']['self']['href'] = rows[0]['_links']['self']['href'].replace(DAY, '2026-10-01')
        self.reject(lambda: self.retrieve(discovery(document()), IDENTITY, rows),
                    'Invalid or unsupported DSO contract data', 'TEMPORAL_INTERVAL')

    def test_duplicate_component_and_annotation_identity(self):
        for kind in ('component', 'annotation'):
            with self.subTest(kind=kind):
                rows = fixtures()
                if kind == 'component':
                    nodes = rows[1]['_embedded']['documentComponenten']
                    nodes.append(deepcopy(nodes[0]))
                    message = 'Ambiguous OW component identity'
                else:
                    rows[2]['locaties'][0]['identificatie'] = rows[2]['regelteksten'][0]['identificatie']
                    message = 'Ambiguous OW annotation identity'
                self.reject(lambda: self.retrieve(discovery(document()), IDENTITY, rows), message)

    def test_discovery_pin_and_replay_conflict_before_transport(self):
        for rehash in (False, True):
            with self.subTest(rehash=rehash):
                package = discovery(document())
                package['documents'][0]['versie'] = 2
                if rehash:
                    package['discovery_hash'] = digest({k: v for k, v in package.items() if k != 'discovery_hash'})
                self.reject(lambda: self.retrieve(package, IDENTITY, fixtures()),
                            'Discovery package cannot be replayed' if rehash else 'Changed discovery binding')
                self.transport.get.assert_not_called()

    def test_unselected_identity_is_not_replaced_by_normalized_alias(self):
        self.reject(lambda: self.retrieve(discovery(document(IDENTITY + '-deel')),
                                         IDENTITY + '_deel', fixtures()),
                    'Explicit unique discovery document identity required')
        self.transport.get.assert_not_called()

    def test_metadata_bracket_detects_nonidentity_drift(self):
        rows = fixtures()
        rows[3]['officieleTitel'] = 'TESTDATA changed title'
        self.reject(lambda: self.retrieve(discovery(document()), IDENTITY, rows),
                    'OW metadata changed during retrieval')
        self.assertEqual(self.transport.get.call_count, 4)

    def test_first_failure_is_schema_before_identity(self):
        doc = document(expression='TESTDATA-conflict')
        del doc['titel']
        self.reject(lambda: self.parse(doc), 'Invalid or unsupported DSO contract data', 'REQUIRED_FIELD')


if __name__ == '__main__':
    unittest.main()
