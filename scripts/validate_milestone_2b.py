"""Run current full suite and a fresh isolated TESTDATA demo; bind evidence to code."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVIDENCE_NAMES = {"milestone-2b-tests.txt", "milestone-2b-result.json", "milestone-2b-audit.jsonl", "milestone-2b-integrity.json"}


def code_identity(root=ROOT):
    files = {root / name for name in ("AGENTS.md", "test.ps1", "bvc-ai.ps1", "run_tests.py", "bvc_ai.py")}
    for directory in ("src", "tests", "scripts", "config", "examples"):
        files.update(p for p in (root / directory).rglob("*") if p.is_file() and p.suffix in {".py", ".json"})
    manifest = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return dict(git_head=head, source_sha256=digest, source_files=manifest)


def run_current_tests(root=ROOT):
    identity = code_identity(root)
    started = datetime.now(timezone.utc).isoformat()
    command = ["pwsh", "-NoProfile", "-File", str(root / "test.ps1")]
    result = subprocess.run(command, cwd=root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1"),
                            text=True, encoding="utf-8", capture_output=True)
    log = result.stdout + result.stderr
    count = re.search(r"Ran (\d+) tests in ([\d.]+)s", log)
    if result.returncode != 0 or not count or int(count[1]) == 0 or not log.rstrip().endswith("OK"):
        raise RuntimeError("Actuele volledige testsuite mislukt; geen nieuw validatiebewijs: " + log)
    if code_identity(root) != identity:
        raise RuntimeError("Code gewijzigd tijdens tests; validatie geweigerd")
    return log, dict(started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                     command=command, exit_code=result.returncode, test_count=int(count[1]), test_seconds=float(count[2]),
                     test_log_sha256=hashlib.sha256(log.encode("utf-8")).hexdigest(), code=identity)


def historical_hashes():
    paths = [p for p in (ROOT / "runtime").rglob("*") if p.is_file()]
    paths += [p for p in DOCS.rglob("*") if p.is_file() and p.name not in EVIDENCE_NAMES
              and p.name != "MILESTONE_2B1_VALIDATION.md"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    before = historical_hashes()
    testlog, test_run = run_current_tests()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    data = ROOT / ".tools" / "validation-runs" / uuid4().hex
    command = [sys.executable, str(ROOT / "bvc_ai.py"), "--data", str(data), "demo", "design-test-001"]
    runs = []
    for _ in range(2):
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, check=True)
        runs.append(json.loads(result.stdout))
    first = runs[0]
    assert first == runs[1], "Replay heeft state of audit gewijzigd"
    assert first["workflowstate"] == "AWAITING_HUMAN_APPROVAL"
    assert first["human_approval"] is None
    assert first["source_status"] == "TESTDATA"
    assert first["iteration_count"] == 1
    assert not first["stale_reviews"]
    assert all(first["output_per_agent"].get(f"A{i:02}") for i in range(1, 9))
    assert all(o["source_status"] == "TESTDATA" for o in first["state"]["objects"])
    resolutions = [h for h in first["state"]["finding_history"] if h["target"] == "RESOLVED"]
    assert len(resolutions) == 2 and all(h.get("verification") for h in resolutions)
    sys.path.insert(0, str(ROOT / "src"))
    from bvc_ai.infrastructure.store import Store
    store = Store(data / "milestone-2b")
    try:
        assert store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        events = store.events("DESIGN-TEST-001")
        assert first["state"] == store.get("DESIGN-TEST-001")
        assert len(events) == first["audit_event_count"]
        assert not any(e["action"].startswith("human_") for e in events)
        exported = [json.loads(line) for line in (data / "milestone-2b/audit.jsonl").read_text(encoding="utf-8").splitlines()]
        assert exported == events
    finally:
        store.close()
    assert before == historical_hashes(), "Historische bestanden zijn gewijzigd"
    assert code_identity() == test_run["code"], "Code gewijzigd na tests; bewijs geweigerd"
    (DOCS / "milestone-2b-tests.txt").write_text(testlog, encoding="utf-8", newline="\n")
    (DOCS / "milestone-2b-result.json").write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DOCS / "milestone-2b-audit.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    integrity = dict(timestamp=datetime.now(timezone.utc).isoformat(), test_count=test_run["test_count"],
                     test_seconds=test_run["test_seconds"], test_run=test_run,
                     data_directory=str(data.relative_to(ROOT)), historical_files_unchanged=True, historical_sha256=before,
                     replay_identical=True, canonical_audit_matches_export=True,
                     evidence_sha256={name: hashlib.sha256((DOCS / name).read_bytes()).hexdigest()
                                      for name in sorted(EVIDENCE_NAMES - {"milestone-2b-integrity.json"})})
    (DOCS / "milestone-2b-integrity.json").write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: first[k] for k in ("project_id", "workflowstate", "iteration_count", "a07_verdict", "human_approval", "audit_event_count")}, indent=2))
    print(f"Tests: {test_run['test_count']}; source SHA-256: {test_run['code']['source_sha256']}; replay identical")


if __name__ == "__main__":
    main()
