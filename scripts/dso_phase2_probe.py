"""Trusted, read-only local probe. No network until explicit CLI opt-in."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from bvc_ai.adapters.dso_contract import date_value
from bvc_ai.adapters.dso_live import DSOLivePostTransport, DSOLiveOWTransport
from bvc_ai.adapters.ow_document import build_request
from bvc_ai.application.dso_discovery import DSODiscoveryService
from bvc_ai.application.ow_document import OWDocumentRetrievalService

ARCHIVE_HASH = '20c015742513def9e93709f0f563a158f71761761f388ae2fd49f672dc5830fb'
ADDRESS_HASH = 'b0d7f0157e244f20d70374e83de7b32bc26e9e873c26cdc27f9a35a89cf66e06'


def meppel_point():
    archive = ROOT / 'docs/evidence/meppel-contract/meppel-live-evidence.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_HASH:
        raise ValueError('Changed Meppel archive')
    with zipfile.ZipFile(archive) as source:
        raw = source.read('address-evidence.json')
    if hashlib.sha256(raw).hexdigest() != ADDRESS_HASH:
        raise ValueError('Changed Meppel address evidence')
    return json.loads(raw)['resolved']['coordinates']


def probe(day, available, identity=None, *, live=False):
    if live is not True:
        raise PermissionError('Explicit live opt-in required')
    date_value(day)
    build_request('_akn_nl_act_probe', 'metadata', day, available)
    discovery = DSODiscoveryService(DSOLivePostTransport(live_opt_in=True)).discover_point(
        meppel_point(), peildatum=day, beschikbaar_op=available)
    result = dict(status='DISCOVERY_VALIDATED', location='MEPPEL_TEST_POINT_ONLY',
                  peildatum=day, beschikbaar_op=available,
                  discovery_hash=discovery['discovery_hash'],
                  source_status=discovery['source_status'],
                  documents=[dict(identity=d['identificatie'], version=d['versie'])
                             for d in discovery['documents']],
                  retrieval='NOT_REQUESTED')
    if identity is not None:
        evidence = OWDocumentRetrievalService(DSOLiveOWTransport(live_opt_in=True)).retrieve(
            discovery, identity, expected_discovery_hash=discovery['discovery_hash'])
        result.update(status='DISCOVERY_AND_RETRIEVAL_VALIDATED', retrieval='VALIDATED',
                      evidence_hash=evidence['evidence_hash'],
                      captures=len(evidence['source_evidence']),
                      components=len(evidence['derived_structure']['components']))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--peildatum', required=True)
    parser.add_argument('--beschikbaar-op', required=True)
    parser.add_argument('--document-identity')
    args = parser.parse_args(argv)
    try:
        result = probe(args.peildatum, args.beschikbaar_op, args.document_identity, live=args.live)
        output = json.dumps(result, ensure_ascii=True, indent=2)
        # Defense in depth also covers caller-controlled input.
        import os
        key = os.environ.get('DSO_API_KEY')
        if key and (key in output or key in json.dumps(result, ensure_ascii=False)):
            raise ValueError('Credential reflection')
    except Exception:
        print('{"status":"FAILED_CLOSED","details":"SUPPRESSED"}')
        return 1
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
