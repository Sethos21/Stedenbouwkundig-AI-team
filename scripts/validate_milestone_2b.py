"""Reproduce M2B CLI evidence without touching historical runtime or human decisions."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


def historical_hashes():
    paths = [p for p in (ROOT/'runtime').rglob('*') if p.is_file() and 'milestone-2b' not in p.relative_to(ROOT/'runtime').parts]
    paths += [p for p in DOCS.rglob('*') if p.is_file() and not p.name.startswith('milestone-2b')]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    before = historical_hashes()
    testlog = (DOCS/'milestone-2b-tests.txt').read_text(encoding='utf-8-sig')
    count = re.search(r'Ran (\d+) tests in ([\d.]+)s', testlog)
    if not count or not testlog.rstrip().endswith('OK'):
        raise RuntimeError('Volledige geslaagde testuitvoer ontbreekt; voer eerst test.ps1 uit')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, str(ROOT/'bvc_ai.py'), 'demo', 'design-test-001']
    runs = []
    for _ in range(2):
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding='utf-8', capture_output=True, check=True)
        runs.append(json.loads(result.stdout))
    first = runs[0]
    assert first == runs[1], 'Replay heeft state of audit gewijzigd'
    assert first['workflowstate'] == 'AWAITING_HUMAN_APPROVAL'
    assert first['human_approval'] is None
    assert first['source_status'] == 'TESTDATA'
    assert first['iteration_count'] <= 3
    assert not first['stale_reviews']
    assert set(first['output_per_agent']) == {f'A{i:02}' for i in range(1,9)}
    assert all(o['source_status'] == 'TESTDATA' for o in first['state']['objects'])
    sys.path.insert(0, str(ROOT/'src'))
    from bvc_ai.infrastructure.store import Store
    store = Store(ROOT/'runtime/milestone-2b')
    try:
        events = store.events('DESIGN-TEST-001')
        assert first['state'] == store.get('DESIGN-TEST-001')
        assert len(events) == first['audit_event_count']
        assert not any(e['action'].startswith('human_') for e in events)
        exported = [json.loads(line) for line in (ROOT/'runtime/milestone-2b/audit.jsonl').read_text(encoding='utf-8').splitlines()]
        assert exported == events
    finally:
        store.close()
    after = historical_hashes()
    assert before == after, 'Historische bestanden zijn gewijzigd'
    (DOCS/'milestone-2b-result.json').write_text(json.dumps(first, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (DOCS/'milestone-2b-audit.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False)+'\n' for e in events), encoding='utf-8')
    integrity = dict(timestamp=datetime.now(timezone.utc).isoformat(), test_count=int(count[1]), test_seconds=float(count[2]),
                     historical_files_unchanged=True, historical_sha256=before, replay_identical=True,
                     canonical_audit_matches_export=True, evidence_sha256={name: hashlib.sha256((DOCS/name).read_bytes()).hexdigest()
                     for name in ('milestone-2b-result.json', 'milestone-2b-audit.jsonl', 'milestone-2b-tests.txt')})
    (DOCS/'milestone-2b-integrity.json').write_text(json.dumps(integrity, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:first[k] for k in ('project_id','workflowstate','iteration_count','a07_verdict','human_approval','audit_event_count')}, indent=2))
    print(f"Tests: {count[1]}; historical files unchanged: {len(before)}; replay identical")


if __name__ == '__main__':
    main()
