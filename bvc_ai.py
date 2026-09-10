import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from bvc_ai.cli.main import main
if __name__ == "__main__":
    raise SystemExit(main())
