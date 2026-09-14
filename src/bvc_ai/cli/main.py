import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
from bvc_ai.infrastructure.store import Store
from bvc_ai.application.workflow import Workflow
from bvc_ai.application.approval import HumanApprovalService, _HUMAN_CAPABILITY
from bvc_ai.agents.factory import create_provider
from bvc_ai.agents.openai_provider import DEFAULT_MODEL
from bvc_ai.agents.smoke import InventorySmokeProvider

PROJECT = Path(__file__).resolve().parents[3]

def main(argv=None):
    parser = argparse.ArgumentParser(prog="bvc-ai")
    parser.add_argument("--data", default="runtime", help="Opslagmap binnen dit project")
    parser.add_argument("--provider", choices=["mock", "openai"], default="mock")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model voor de OpenAI-provider")
    parser.add_argument("--timeout", type=float, default=30, help="OpenAI socket-timeout in seconden (maximaal 120)")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("name", choices=["gis-001"])
    commands.add_parser("smoke", help="Eén A02-call, mockreview, eigen opslagmap")
    commands.add_parser("tasks")
    for name in ("status", "review", "audit", "resume"):
        sub = commands.add_parser(name)
        sub.add_argument("task_id")
    for name in ("approve", "reject"):
        sub = commands.add_parser(name)
        sub.add_argument("task_id")
        sub.add_argument("--actor", required=True)
        sub.add_argument("--reason", default="")
    args = parser.parse_args(argv)
    directory = (PROJECT / args.data).resolve()
    if not directory.is_relative_to(PROJECT):
        parser.error("--data moet binnen de projectmap liggen")
    if args.command == "smoke":
        # Every run has a separate task store, also when --data names a test directory.
        directory = (directory / "smoke" / uuid4().hex).resolve()
        if not directory.is_relative_to(PROJECT):
            parser.error("Smoke-opslag moet binnen de projectmap liggen")
        if args.provider == "openai" and not os.environ.get("OPENAI_API_KEY", "").strip():
            print(json.dumps({"status": "SKIPPED", "reason": "OPENAI_API_KEY ontbreekt; live call niet uitgevoerd."}))
            return 0
    store = None
    try:
        provider = None
        if args.command in {"demo", "resume", "smoke"}:
            provider = create_provider(args.provider, model=args.model, timeout=args.timeout)
            if args.command == "smoke":
                provider = InventorySmokeProvider(provider)
        store = Store(directory)
        if args.command in {"demo", "smoke"}:
            result = Workflow(store, provider, PROJECT).demo()
            if args.command == "smoke":
                result = {"data_directory": str(directory.relative_to(PROJECT)),
                          "inventory_provider": args.provider, "review_provider": "mock", "task": result}
        elif args.command == "resume":
            result = Workflow(store, provider, PROJECT).run(args.task_id)
        elif args.command == "tasks":
            result = store.list()
        elif args.command == "audit":
            result = store.events(args.task_id)
        elif args.command == "review":
            result = store.get(args.task_id)["reviews"]
        elif args.command == "status":
            result = store.get(args.task_id)
        else:
            service = HumanApprovalService(store, capability=_HUMAN_CAPABILITY)
            service.decide(args.task_id, args.actor, "APPROVED" if args.command == "approve" else "REJECTED", args.reason)
            result = store.get(args.task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, PermissionError, KeyError) as exc:
        print(f"Fout: {exc}")
        return 2
    finally:
        if store is not None:
            store.export_audit()
            store.close()
