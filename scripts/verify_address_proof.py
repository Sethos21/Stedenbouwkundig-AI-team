"""Verify an existing official-address proof entirely offline in isolated local storage."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

from live_mastenbroekweg_2d import ROOT, Store, SourceStore, offline_proof, require
from bvc_ai.adapters.pdok_location import replay_address
from bvc_ai.domain.source_hashing import raw_response_hash


def verify(directory):
    directory = Path(directory).resolve()
    require(directory.is_relative_to((ROOT / 'runtime/2d-live').resolve()), 'Proof must stay under runtime/2d-live')
    report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    evidence = json.loads((directory / 'address-evidence.json').read_text(encoding='utf-8'))
    original_basis = json.loads((directory / 'source-basis.json').read_text(encoding='utf-8'))
    target = directory / ('verification-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    target.mkdir(exist_ok=False)
    with ExitStack() as guards:
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guards.enter_context(patch(name, side_effect=AssertionError('OFFLINE: NETWORK BLOCKED')))
        location = replay_address(evidence)
        require(raw_response_hash((directory / 'address-response.raw').read_bytes()) == evidence['raw_sha256'],
                'Standalone address raw evidence mismatch')
        require(report['coordinates'] == list(location.coordinates), 'Reported coordinate mismatch')
        store = Store(directory / 'archive')
        try:
            basis = offline_proof(store, target, [c['snapshot_id'] for c in report['collections']])
            require(basis == original_basis, 'Source basis differs from archived report')
        finally:
            store.close()
    result = dict(result='PASS', address_replay='PASS', source_replay='PASS', reconstruction='PASS',
                  network='socket/connect/DNS blocked', basis_hash=basis['basis_hash'],
                  collections=len(report['collections']), source_objects=len(basis['records']),
                  human_approval=None, evidence_directory=str(directory), reconstruction_directory=str(target))
    (target / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    print(json.dumps(verify(parser.parse_args().directory), indent=2))
