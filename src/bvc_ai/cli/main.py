import argparse
import json
from pathlib import Path
from bvc_ai.infrastructure.store import Store
from bvc_ai.application.workflow import Workflow
from bvc_ai.application.approval import HumanApprovalService, _HUMAN_CAPABILITY
from bvc_ai.agents.provider import DeterministicTestProvider

PROJECT = Path(__file__).resolve().parents[3]

def main(argv=None):
    parser = argparse.ArgumentParser(prog="bvc-ai")
    parser.add_argument("--data", default="runtime", help="Opslagmap binnen dit project")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("name", choices=["gis-001"])
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
    store = Store(directory)
    try:
        workflow = Workflow(store, DeterministicTestProvider(), PROJECT)
        if args.command == "demo":
            result = workflow.demo()
        elif args.command == "resume":
            result = workflow.run(args.task_id)
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
        store.export_audit()
        store.close()
