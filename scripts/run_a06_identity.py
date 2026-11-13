"""Offline Issue #6 test runner: pinned local Git snapshot, never fetches or merges.

Uses the existing interpreter/dependencies. All artifacts stay under .tools.
No production module, test entry point, pin or existing branch is modified.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FEATURE = '28b4dd7b60fd5546e8161054ad76d7cd62bf831a'
GUARD = '''import os, sys
from pathlib import Path
log = Path(os.environ['A06_GUARD_LOG']) / (str(os.getpid()) + '.txt')
log.write_text('ACTIVE\\n', encoding='utf-8')
def offline(event, args):
    if event.startswith('socket.'):
        with log.open('a', encoding='utf-8') as stream:
            stream.write('BLOCKED ' + event + '\\n')
        raise RuntimeError('OFFLINE socket denied')
sys.addaudithook(offline)
os.environ['A06_GUARD_ACTIVE'] = '1'
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('targeted', 'full', 'master'), default='targeted')
    args = parser.parse_args()
    tools = ROOT / '.tools'
    tools.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix='issue6-' + args.suite + '-', dir=tools))
    guard, logs, temp = (run / p for p in ('guard', 'guard-logs', 'tmp'))
    for folder in (guard, logs, temp):
        folder.mkdir()
    (guard / 'sitecustomize.py').write_text(GUARD, encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if not k.upper().endswith('API_KEY')}
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1',
               PYTHONUTF8='1', A06_GUARD_LOG=str(logs))
    env.pop('A06_GUARD_ACTIVE', None)
    before = {}
    if args.suite == 'master':
        target = ROOT
        command = ['pwsh', '-NoProfile', '-File', str(ROOT / 'test.ps1')]
    else:
        # Read only an exact, already available commit. No branch writes or network.
        archive = subprocess.check_output(['git', 'archive', '--format=zip', FEATURE], cwd=ROOT)
        target = run / 'snapshot'
        target.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for entry in bundle.infolist():
                destination = (target / entry.filename).resolve()
                if not destination.is_relative_to(target.resolve()):
                    raise RuntimeError('Archive path escapes local snapshot')
            bundle.extractall(target)
        before = {str(p.relative_to(target)): sha(p) for p in target.rglob('*') if p.is_file()}
        # Existing BAG tests require this ignored parent directory in a fresh export.
        (target / 'runtime/2d-live').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'tests/characterization/a06_identity_cases.py',
                        target / 'tests/test_a06_identity_characterization.py')
        command = ([sys.executable, '-B', '-m', 'unittest', '-v', 'test_a06_identity_characterization']
                   if args.suite == 'targeted' else [sys.executable, '-B', str(target / 'run_tests.py')])
    env['PYTHONPATH'] = os.pathsep.join(str(p) for p in (guard, target / 'src', target / 'tests'))
    # Startup evidence without making even a blocked network call.
    subprocess.run([sys.executable, '-B', '-c',
                    "import os; assert os.environ.get('A06_GUARD_ACTIVE') == '1'"],
                   cwd=target, env=env, check=True)
    print('Run directory:', run.relative_to(ROOT), flush=True)
    started = time.monotonic()
    with (run / 'tests.txt').open('w', encoding='utf-8') as output:
        completed = subprocess.run(command, cwd=target / 'tests' if args.suite == 'targeted' else target,
                                       env=env, stdout=output, stderr=subprocess.STDOUT)
    changes = [name for name, original in before.items()
               if not (target / name).is_file() or sha(target / name) != original]
    guard_files = list(logs.glob('*.txt'))
    blocked = sum(p.read_text(encoding='utf-8').count('BLOCKED ') for p in guard_files)
    result = dict(suite=args.suite, runtime_commit=FEATURE if before else
                  subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  command=command, exit_code=completed.returncode, seconds=round(time.monotonic() - started, 3),
                  unchanged_snapshot_files=len(before), changed_snapshot_files=changes,
                  guard_processes=len(guard_files), blocked_socket_events=blocked,
                  test_sha256=sha(ROOT / 'tests/characterization/a06_identity_cases.py'),
                  runner_sha256=sha(Path(__file__)), log_sha256=sha(run / 'tests.txt'))
    (run / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    print('\n'.join((run / 'tests.txt').read_text(encoding='utf-8').splitlines()[-8:]))
    return 1 if completed.returncode or changes or blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())
