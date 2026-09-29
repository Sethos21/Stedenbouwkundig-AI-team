"""Read-only A02 source view. Neither publication nor promotion capability."""
import hashlib
import json
from bvc_ai.domain.design import current_output
from bvc_ai.domain.source_profiles import source_profile, BGT_COLLECTIONS, BAG_COLLECTIONS
from bvc_ai.application.source_replay import SourceReplayService

REQUIRED_CONTRACTS = frozenset(['BGT/' + c for c in BGT_COLLECTIONS] +
                              ['BAG/' + c for c in BAG_COLLECTIONS])


def validated_members(store, task, members, origin, extent=None):
    """Revalidate explicitly carried immutable publications, not arbitrary COMPLETE labels.

    Import revisions may be historical; only the current trusted A02 output can
    carry their source references forward. Their A01 input context must still match.
    This helper returns evidence and has no authority to create a current output.
    """
    if not isinstance(members, dict):
        raise ValueError('Explicit source set required')
    results = {}
    replay = SourceReplayService(store)
    events = store.events(task['task_id'])
    for key, member in sorted(members.items()):
        profile = source_profile(key)
        if profile.key is None or not isinstance(member, dict) or set(member) != {
                'snapshot_id', 'manifest_hash', 'import_revision_id'}:
            raise ValueError('Invalid source set entry')
        sid, revision = member['snapshot_id'], member['import_revision_id']
        binding = store.db.execute('SELECT snapshot_id FROM source_revision_bindings WHERE task_id=? AND revision_id=?',
                                   (task['task_id'], revision)).fetchone()
        output = next((o for o in task['outputs'] if o['revision_id'] == revision and o['agent_id'] == 'A02'), None)
        if (binding is None or binding[0] != sid or output is None
                or output['source_status'] != origin
                or output['output'].get('source_snapshot_id') != sid
                or output['output'].get('snapshot_manifest_hash') != member['manifest_hash']
                or any(task['active_revisions'].get(k) != v for k, v in output['input_revisions'].items())
                or not any(e['action'] == 'source_import_completed' and e['details'].get('snapshot_id') == sid
                           and e['details'].get('revision_id') == revision
                           and e['details'].get('snapshot_manifest_hash') == member['manifest_hash'] for e in events)):
            raise ValueError('Source set lacks trusted publication/context evidence')
        result = replay.verify(sid)
        snapshot = result.snapshot
        provenance = json.loads(snapshot.provenance_json)
        if (provenance.get('source_contract') != key or provenance.get('source_status') != origin
                or snapshot.snapshot_manifest_hash != member['manifest_hash']
                or (extent is not None and snapshot.fetch_extent != extent)):
            raise ValueError('Source set scope/origin/manifest mismatch')
        extent = snapshot.fetch_extent
        results[key] = result
    return results


def official_relations(records):
    """Resolve literal official references only. No spatial/LLM matching or URL fetch."""
    by_feature, by_registration = {}, {}
    for record in records:
        key = record['source_contract']
        by_feature.setdefault((key, record['source_id']), []).append(record['record_ref'])
        identifier = json.loads(record['properties_json']).get('identificatie')
        if isinstance(identifier, str) and identifier:
            by_registration.setdefault((key, identifier), []).append(record['record_ref'])
    relations, uncertainties = [], []
    for record in records:
        key = record['source_contract']
        props = json.loads(record['properties_json'])
        if key == 'BGT/pand':
            field, target = 'bag_pnd', 'BAG/pand'
            raw = props.get(field)
            refs = [raw] if isinstance(raw, str) and raw else []
        elif key in ('BAG/pand', 'BAG/verblijfsobject'):
            field = 'verblijfsobject' if key == 'BAG/pand' else 'pand'
            target = 'BAG/' + field
            refs = props.get(field) or []
        else:
            continue
        if not refs:
            uncertainties.append(dict(record_ref=record['record_ref'], field=field,
                                      reason='NO_OFFICIAL_REFERENCE_AVAILABLE'))
        for raw in refs:
            if key == 'BGT/pand':
                matches = by_registration.get((target, raw), [])
            else:
                prefix = source_profile(target).items_url + '/'
                identity = raw[len(prefix):] if raw.startswith(prefix) else raw
                matches = by_feature.get((target, identity), [])
            state = 'RESOLVED' if len(matches) == 1 else 'AMBIGUOUS' if matches else 'UNRESOLVED'
            relations.append(dict(source_ref=record['record_ref'], field=field,
                                  official_reference=raw, target_contract=target,
                                  target_refs=matches, status=state, basis='OFFICIAL_ATTRIBUTE'))
            if state != 'RESOLVED':
                uncertainties.append(dict(record_ref=record['record_ref'], field=field,
                                          official_reference=raw, reason=state))
    # Report asymmetric supplied relations as uncertainty; never synthesize an inverse.
    resolved = {(tuple(r['source_ref']), tuple(r['target_refs'][0])) for r in relations
                if r['status'] == 'RESOLVED' and r['source_ref'][0].startswith('BAG/')}
    for left, right in sorted(resolved):
        if (right, left) not in resolved:
            uncertainties.append(dict(record_ref=list(left), target_ref=list(right),
                                      reason='RECIPROCAL_REFERENCE_NOT_CONFIRMED'))
    return relations, uncertainties


class SourceBasisService:
    def __init__(self, store):
        self._store = store

    def build(self, task_id, *, expected_revision=None, require_complete=True):
        if self._store.db.in_transaction:
            raise ValueError('Source view requires its own consistent read transaction')
        with self._store.db:
            self._store.db.execute('BEGIN')
            task = self._store.get(task_id)
            output = current_output(task, 'A02')
            revision = output['revision_id']
            if expected_revision is not None and revision != expected_revision:
                raise ValueError('Stale source basis revision')
            members = output['output'].get('source_set')
            results = validated_members(self._store, task, members, output['source_status'])
            missing = sorted(REQUIRED_CONTRACTS - set(results))
            if not results or (require_complete and missing):
                raise ValueError('Incomplete A02 source basis')
            records, sources = [], []
            for key, result in sorted(results.items()):
                sources.append(dict(source_contract=key, **members[key],
                                    feature_count=len(result.features), page_count=len(result.pages),
                                    point_in_time_consistency=result.snapshot.point_in_time_consistency))
                for feature in result.features:
                    provenance = json.loads(feature.provenance_json)
                    records.append(dict(source_contract=key, source_id=feature.source_id,
                                        record_ref=[key, result.snapshot.snapshot_id, feature.source_id],
                                        geometry_ref=feature.geometry_ref,
                                        properties_json=feature.properties_json,
                                        raw_response_hash=provenance['raw_response_hash'],
                                        origin=provenance['source_status']))
            actual = {(o['geometry_ref'], o['properties'].get('snapshot_id'), o['properties'].get('source_id'))
                      for o in task['objects'] if o['revision_id'] == revision
                      and o['geometry_status'] == 'EXISTING_VALIDATED' and o['source_status'] == output['source_status']}
            expected = {(r['geometry_ref'], r['record_ref'][1], r['source_id']) for r in records}
            if actual != expected:
                raise ValueError('Current A02 objects differ from source set')
            relations, uncertainties = official_relations(records)
            result = dict(format='BVC_A02_SOURCE_BASIS_V1', task_id=task_id, revision_id=revision,
                          source_status=output['source_status'], complete=not missing,
                          missing_collections=missing, sources=sources, records=records,
                          relations=relations, uncertainties=uncertainties,
                          interpretation='FACTS_AND_EXPLICIT_OFFICIAL_REFERENCES; NO_DESIGN_OR_POLICY',
                          point_in_time_consistency='NOT_GUARANTEED',
                          summary=[f"{s['source_contract']}: {s['feature_count']} bronobjecten; "
                                   f"snapshot {s['snapshot_id']}" for s in sources])
            result['basis_hash'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False,
                                                           separators=(',', ':')).encode()).hexdigest()
            return result

    def verify(self, basis):
        current = self.build(basis['task_id'], expected_revision=basis['revision_id'],
                             require_complete=basis['complete'])
        if current != basis:
            raise ValueError('Changed source basis')
        return current
