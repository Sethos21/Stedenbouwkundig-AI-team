from .models import Status, SourceReference, SourceStatus

TRANSITIONS = {
    "DRAFT": {"READY", "BLOCKED", "FAILED"},
    "READY": {"RUNNING", "BLOCKED", "FAILED"},
    "RUNNING": {"SPECIALIST_COMPLETE", "BLOCKED", "FAILED"},
    "SPECIALIST_COMPLETE": {"REVIEW_PENDING", "BLOCKED", "FAILED"},
    "REVIEW_PENDING": {"REVIEWED", "READY", "BLOCKED", "FAILED"},
    "REVIEWED": {"AWAITING_HUMAN_APPROVAL", "BLOCKED", "FAILED"},
    "AWAITING_HUMAN_APPROVAL": {"APPROVED", "REJECTED"},
    "APPROVED": set(), "REJECTED": set(),
    "BLOCKED": {"READY"}, "FAILED": {"READY"},
}

def check_transition(current, target, *, human_service=False):
    Status(target)
    if target in {"APPROVED", "REJECTED"} and not human_service:
        raise PermissionError("Alleen Human Approval Service mag definitief beslissen")
    if target not in TRANSITIONS[current]:
        raise ValueError(f"Verboden overgang: {current} -> {target}")

def validate_output(output):
    if output.agent_id != "A02" or output.kind != "source_inventory":
        raise PermissionError("A02 mag uitsluitend broninventarisatie registreren")
    if output.human_approval is not None:
        raise PermissionError("Agent mag geen menselijke goedkeuring meesturen")
    if output.source_type != "fixture" or output.source_status != "TESTDATA":
        raise ValueError("Milestone 1 accepteert uitsluitend TESTDATA")
    if not 0 <= output.confidence <= 1 or not output.source_refs:
        raise ValueError("Ongeldige provenance")
    required = {"sources", "missing_data", "geometry_uncertainties", "k00_discrepancies", "recommendations"}
    if set(output.payload) != required:
        raise ValueError("Onverwachte of ontbrekende outputvelden, ontwerp is verboden")
    sources = [SourceReference(**s) for s in output.payload["sources"]]
    if not sources or any(s.source_status != SourceStatus.TESTDATA for s in sources):
        raise ValueError("Bronnen moeten TESTDATA zijn")
    if output.source_refs != [s.source_id for s in sources]:
        raise ValueError("Bronverwijzingen komen niet overeen")

class K00Policy:
    @staticmethod
    def authorize(asset_id, operation, *, origin="derived", classification="derived"):
        if asset_id.strip().upper() == "K00" and operation != "read":
            raise PermissionError("K00 is een immutable reference asset")
        if operation != "read" and (origin != "derived" or classification != "derived"):
            raise PermissionError("Alleen afgeleide lagen; nooit ontwerp als bestaande geometrie")

def check_review_ready(task):
    if task["review_status"] != "SUFFICIENT" or not task.get("outputs") or not task.get("reviews"):
        raise ValueError("Voldoende review en specialist-output ontbreken")
    latest = task["outputs"][-1]
    review = task["reviews"][-1]
    if (review["verdict"] != "SUFFICIENT" or review["reviewer"] != "A07"
            or review["task_id"] != task["task_id"]
            or latest["task_id"] != task["task_id"]
            or review["output_version"] != latest["output_version"]):
        raise ValueError("Review hoort niet bij de actuele outputversie")
