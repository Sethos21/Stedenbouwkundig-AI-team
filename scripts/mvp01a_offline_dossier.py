"""Build a local dossier for the one pinned historical BAG/BGT archive."""
import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from verify_address_proof import ROOT, Store, SourceStore, require, verify
from bvc_ai.adapters.pdok_location import AddressInput
from bvc_ai.application.live_source_validation import (
    address_analysis, compare_address_evidence, replay_address_evidence,
)
from bvc_ai.application.source_basis import REQUIRED_CONTRACTS
from bvc_ai.application.spatial_context import SpatialContextService

PACKAGE = ROOT / 'docs/evidence/bag-api-bootstrap'
ARCHIVE = 'meppel-bag-api-live.zip'
ARCHIVE_SHA = '516d98777d00b61bedaca980d7372207c028b9624b04b97dec6b7ca29aaaf7bd'
SOURCE_COMMIT = '11bbdbdb96f9c048305c51ff999216dd6dbca152'
MEMBERS = {
    'address-evidence.json', 'address-response.raw', 'report.json', 'source-basis.json',
    'archive/state.sqlite3', 'baseline-address-evidence.json',
    'verification-20260930T143332737175Z/verification.json',
}


def block_network(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('Offline dossier: socket and DNS access blocked')


def verified_members():
    manifest = json.loads((PACKAGE / 'archive-manifest.json').read_bytes())
    require(manifest['archive'] == ARCHIVE and manifest['sha256'] == ARCHIVE_SHA
            and set(manifest['files']) == MEMBERS, 'Unexpected archive manifest')
    archive = (PACKAGE / ARCHIVE).read_bytes()
    require(sha256(archive).hexdigest() == ARCHIVE_SHA, 'Archive hash mismatch')
    with ZipFile(BytesIO(archive)) as zipped:
        require(sorted(zipped.namelist()) == sorted(MEMBERS | {'manifest.json'}), 'Unexpected archive members')
        members = {name: zipped.read(name) for name in MEMBERS}
    for name, value in members.items():
        require(sha256(value).hexdigest() == manifest['files'][name], 'Archive member hash mismatch')
    return members


def bind_address(text, primary, baseline, report):
    address = AddressInput.parse(text)
    require((primary['contract'], baseline['contract']) ==
            ('BAG_INDIVIDUAL_ADDRESS_V2_V1', 'PDOK_LOCATIESERVER_ADDRESS_V1'),
            'Unexpected address evidence contracts')
    require(text == primary['address_input'], 'Input does not exactly match the archived address')
    baseline_address = AddressInput.parse(baseline['address_input'])
    require(address == replace(baseline_address, text=text), 'Address parts differ between archives')
    comparison = compare_address_evidence(primary, baseline)
    location = replay_address_evidence(primary)
    extent, geometry = address_analysis(primary)
    identifiers = report['official_identifiers']
    require(report['coordinates'] == list(location.coordinates)
            and report['coordinate_crs'] == location.coordinate_crs
            and identifiers['nummeraanduiding_id'] == location.nummeraanduiding_id
            and identifiers['adresseerbaarobject_id'] == location.adresseerbaarobject_id,
            'Reported address identity or RD point mismatch')
    require(report['bbox'] == list(extent.bbox) and report['crs'] == extent.crs
            and report['analysis_geometry'] == json.loads(geometry.provenance_json),
            'Reported analysis extent or CRS mismatch')
    return location, comparison, extent, geometry


def bind_collections(basis, report):
    expected = {(row['source_contract'], row['snapshot_id']) for row in basis['sources']}
    actual = {(row['source_contract'], row['snapshot_id']) for row in report['collections']}
    require(basis['complete'] and len(report['collections']) == len(expected)
            and {contract for contract, _ in expected} == set(REQUIRED_CONTRACTS)
            and len(expected) == len(REQUIRED_CONTRACTS) and actual == expected,
            'Report does not match the eight archived collections')
    require(basis['revision_id'] == report['revision_id']
            and basis['basis_hash'] == report['basis_hash'], 'Stale report revision or basis')
    return expected


def build_dossier(text):
    members = verified_members()
    primary = json.loads(members['address-evidence.json'])
    baseline = json.loads(members['baseline-address-evidence.json'])
    report = json.loads(members['report.json'])
    basis = json.loads(members['source-basis.json'])
    location, comparison, extent, geometry = bind_address(text, primary, baseline, report)
    collections = bind_collections(basis, report)
    require(sha256(members['address-response.raw']).hexdigest() == primary['raw_sha256'],
            'Standalone address evidence hash mismatch')
    runtime = ROOT / 'runtime/2d-live'
    runtime.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='mvp01a-', dir=runtime) as scratch:
        directory = Path(scratch)
        for name, value in members.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        checked = verify(directory)
        require(checked['result'] == 'PASS' and checked['basis_hash'] == basis['basis_hash']
                and checked['collections'] == len(collections), 'Offline verifier mismatch')
        store = Store(directory / 'archive')
        try:
            sources = SourceStore(store)
            for _, snapshot_id in sorted(collections):
                snapshot = sources.snapshot(snapshot_id)
                require(snapshot.fetch_extent == extent
                        and sources.geometry(extent.analysis_geometry_ref) == geometry,
                        'Snapshot extent, CRS or analysis geometry mismatch')
            service = SpatialContextService(store)
            context = service.build(basis['task_id'], expected_revision=basis['revision_id'])
            require(service.verify(context) == context and context['basis_hash'] == basis['basis_hash'],
                    'Repeated context or basis differs')
        finally:
            store.close()
        require((directory / 'archive/state.sqlite3').read_bytes() == members['archive/state.sqlite3'],
                'Copied database changed during verification')
    require(sha256((PACKAGE / ARCHIVE).read_bytes()).hexdigest() == ARCHIVE_SHA,
            'Original archive changed during verification')
    return {
        'format': 'MVP01A_HISTORICAL_OFFLINE_DOSSIER_V1',
        'source_commit': SOURCE_COMMIT, 'archive_sha256': ARCHIVE_SHA,
        'address_captured_at': primary['finished'], 'report_timestamp': report['timestamp'],
        'address': {'input': text, 'official': location.official_address,
                    'nummeraanduiding_id': location.nummeraanduiding_id,
                    'adresseerbaarobject_id': location.adresseerbaarobject_id,
                    'rd_point': list(location.coordinates), 'crs': location.coordinate_crs,
                    'contract': primary['contract'], 'baseline_contract': baseline['contract'],
                    'raw_sha256': primary['raw_sha256'], 'comparison': comparison},
        'analysis_scope': {'bbox': list(extent.bbox), 'crs': extent.crs,
                           'geometry_hash': geometry.geometry_structural_hash,
                           'boundary_status': 'DERIVED_TEST_ANALYSIS_NOT_A_PROJECT_OR_PROPERTY_BOUNDARY'},
        'task_id': basis['task_id'], 'revision_id': basis['revision_id'],
        'task_context': report['task_context'], 'source_status': basis['source_status'],
        'basis_hash': basis['basis_hash'], 'context_hash': context['context_hash'],
        'sources': basis['sources'], 'uncertainties': dict(Counter(item['reason'] for item in context['uncertainties'])),
        'limitations': ['Historical archive only', *context['limitations']],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True)
    args = parser.parse_args()
    sys.addaudithook(block_network)
    try:
        dossier = build_dossier(args.address)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        parser.exit(1, f'Offline dossier failed: {exc}\n')
    print(json.dumps(dossier, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
