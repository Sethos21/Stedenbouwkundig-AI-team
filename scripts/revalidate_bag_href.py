"""Revalidate archived Meppel evidence offline after the BAG href read-model correction.

The original ZIP, snapshot manifests, source records and old basis stay immutable.
Only a new derived relation view and validation report are written under runtime.
"""
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

from live_mastenbroekweg_2d import ROOT, Store, offline_proof, require
from bvc_ai.adapters.pdok_location import replay_address

PACKAGE = ROOT / 'docs/evidence/meppel-contract/meppel-live-evidence.zip'
PACKAGE_MANIFEST = ROOT / 'docs/evidence/meppel-contract/meppel-live-evidence-sha256.json'


def revalidate():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = ROOT / 'runtime/2d-live' / ('bag-href-' + stamp)
    directory.mkdir(parents=True, exist_ok=False)
    with ExitStack() as guards:
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            guards.enter_context(patch(name, side_effect=AssertionError('OFFLINE: NETWORK BLOCKED')))
        package_hash = hashlib.sha256(PACKAGE.read_bytes()).hexdigest()
        require(package_hash == json.loads(PACKAGE_MANIFEST.read_text())['sha256'], 'Package hash mismatch')
        with zipfile.ZipFile(PACKAGE) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            for name, metadata in manifest.items():
                payload = archive.read(name)
                require(len(payload) == metadata['bytes'] and hashlib.sha256(payload).hexdigest() == metadata['sha256'], 'Member hash mismatch')
            # Extract only the single known archive file into a fresh isolated directory.
            database = directory / 'archive/state.sqlite3'
            database.parent.mkdir()
            database.write_bytes(archive.read('archive/state.sqlite3'))
            old = json.loads(archive.read('source-basis.json'))
            live = json.loads(archive.read('report.json'))
            address = json.loads(archive.read('address-evidence.json'))
            require(replay_address(address).coordinates == tuple(live['coordinates']), 'Address replay mismatch')
        before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
        store = Store(database.parent)
        try:
            basis = offline_proof(store, directory, [c['snapshot_id'] for c in live['collections']])
        finally:
            store.close()
        require(hashlib.sha256(database.read_bytes()).hexdigest() == before_hash, 'Source archive changed')
        for key in set(old) | set(basis):
            if key not in ('relations', 'uncertainties', 'basis_hash'):
                require(old.get(key) == basis.get(key), 'Non-relation basis changed: ' + key)
        (directory / 'source-basis-href.json').write_text(json.dumps(basis, indent=2), encoding='utf-8')
        # Every new BAG edge must point to a literal field value; no synthetic inverse.
        records = {tuple(r['record_ref']): r for r in basis['records']}
        for relation in basis['relations']:
            props = json.loads(records[tuple(relation['source_ref'])]['properties_json'])
            values = props.get(relation['field'])
            require(relation['official_reference'] in (values if isinstance(values, list) else [values]),
                    'Relation lacks a literal source field')
        href_records, href_references = 0, 0
        for row in basis['records']:
            if row['source_contract'] not in ('BAG/pand','BAG/verblijfsobject'):
                continue
            field = 'verblijfsobject.href' if row['source_contract']=='BAG/pand' else 'pand.href'
            values = json.loads(row['properties_json']).get(field)
            if values:
                href_records += 1
                href_references += len(values)
        href_relations = [r for r in basis['relations'] if r['field'].endswith('.href')]
        unresolved = [r for r in basis['relations'] if r['status'] != 'RESOLVED']
        sentinels = [r for r in basis['relations'] if r['field']=='bag_pnd' and r['official_reference']=='0000000000000000']
        require(all(r['status']=='UNRESOLVED' and not r['target_refs'] for r in sentinels), 'Sentinel incorrectly resolved')
        no_reference = {tuple(u['record_ref']) for u in basis['uncertainties'] if u['reason'] in (
            'NO_OFFICIAL_REFERENCE_AVAILABLE','INVALID_OFFICIAL_HREF','INVALID_OFFICIAL_ATTRIBUTE','CONFLICTING_OFFICIAL_REFERENCES')}
        eligible = {tuple(r['record_ref']) for r in basis['records'] if r['source_contract'] in ('BAG/pand','BAG/verblijfsobject','BGT/pand')}
        with_resolved = {tuple(r['source_ref']) for r in basis['relations'] if r['status']=='RESOLVED'}
        result = dict(test='MEPPEL_BAG_HREF_CORRECTION', result='PASS_WITH_FINDINGS',
            source_package_sha256=package_hash, original_basis_hash=old['basis_hash'], derived_basis_hash=basis['basis_hash'],
            href_records_examined=href_records, href_references_examined=href_references,
            href_references_validly_processed=len(href_relations),
            href_relations_resolved=sum(r['status']=='RESOLVED' for r in href_relations),
            href_relations_unresolved=sum(r['status']!='RESOLVED' for r in href_relations),
            relations_resolved_total=sum(r['status']=='RESOLVED' for r in basis['relations']),
            remaining_unresolved_relations=len(unresolved),
            records_without_usable_official_relation=len(no_reference),
            usable_definition='At least one syntactically valid literal reference; target availability reported separately',
            relation_bearing_records_without_resolved_target=len(eligible-with_resolved),
            bgt_sentinel_relations=dict(count=len(sentinels),status='UNRESOLVED'),
            synthetic_relations_created=0, replay='PASS', reconstruction='PASS', address_replay='PASS',
            network='socket/connect/DNS blocked; no live fetch', source_archive_byte_identical=True,
            source_records_and_snapshot_hashes_unchanged=True, source_objects=len(basis['records']),
            collections=len(basis['sources']), human_approval=None,
            uncertainties=dict(Counter(u['reason'] for u in basis['uncertainties'])),
            unresolved_relations=unresolved,
            local_evidence_directory=str(directory.relative_to(ROOT)))
        (directory/'revalidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(revalidate(), indent=2))
