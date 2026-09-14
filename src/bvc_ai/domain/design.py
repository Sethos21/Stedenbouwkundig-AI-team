"""Ontwerplus domain; geometry validation concerns synthetic TESTDATA only."""
from dataclasses import dataclass
from enum import StrEnum


class GeometryStatus(StrEnum):
    EXISTING_VALIDATED = "EXISTING_VALIDATED"
    PROPOSED = "PROPOSED"


class Severity(StrEnum):
    INFO = "INFO"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    BLOCKED = "BLOCKED"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class Verdict(StrEnum):
    PASS = "PASS"
    PASS_WITH_FINDINGS = "PASS_WITH_FINDINGS"
    REVISE = "REVISE"
    BLOCKED = "BLOCKED"


DESIGN_TYPES = {
    "DEVELOPMENT_FIELD", "PUBLIC_SPACE", "URBAN_EDGE", "CENTRAL_PLACE",
    "BUILDING_ZONE", "PROPOSED_ROUTE", "PROPOSED_ACCESS", "LANDSCAPE_STRUCTURE",
    "PHASING_AREA", "MASSING_ZONE",
}
SOURCE_TYPES = {"PROJECT_BOUNDARY", "EXISTING_FEATURE", "SOURCE_ZONE"}
ROLES = {f"A{i:02}" for i in range(1, 9)}
STEPS = {
    "A01_START": ("A01", ()),
    "A02": ("A02", ("A01_START",)),
    "A06": ("A06", ("A02",)),
    "A08_GATE": ("A08", ("A02", "A06")),
    "A03_HYPOTHESIS": ("A03", ("A02", "A06", "A08_GATE")),
    "A04": ("A04", ("A03_HYPOTHESIS",)),
    "A05": ("A05", ("A03_HYPOTHESIS",)),
    "A03_INTEGRATION": ("A03", ("A03_HYPOTHESIS", "A04", "A05")),
    "A04_REVIEW": ("A04", ("A03_INTEGRATION",)),
    "A05_REVIEW": ("A05", ("A03_INTEGRATION",)),
    "A08_REVIEW": ("A08", ("A03_INTEGRATION",)),
    "A07": ("A07", ("A04_REVIEW", "A05_REVIEW", "A08_REVIEW")),
    "A01_PACKAGE": ("A01", ("A07",)),
}
REVIEW_STEPS = {"A04_REVIEW", "A05_REVIEW", "A08_REVIEW", "A07"}
ENV_THEMES = {
    "geluid", "geur", "bodem", "luchtkwaliteit", "externe veiligheid",
    "milieuzonering", "stikstof", "beschermde soorten", "Natura 2000",
    "natuurstructuren", "water/bodem", "klimaatrisico's", "agrarische hinder",
}


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    agent_id: str
    step: str
    revision_id: str
    input_revisions: dict
    output: dict
    timestamp: str
    source_status: str = "TESTDATA"


@dataclass(frozen=True)
class Handoff:
    from_step: str
    to_step: str
    revision_id: str
    input_revisions: dict


@dataclass(frozen=True)
class DesignObject:
    object_id: str
    project_id: str
    object_type: str
    geometry_ref: str
    geometry_status: str
    revision_id: str
    created_by: str
    source_basis: list
    properties: dict
    required_reviews: list
    findings: list
    source_status: str = "TESTDATA"


@dataclass(frozen=True)
class Finding:
    finding_id: str
    created_by: str
    revision_id: str
    input_revisions: dict
    severity: str
    status: str
    description: str
    spatial_effect: str
    classification: str


@dataclass(frozen=True)
class ReviewResult:
    review_id: str
    reviewer: str
    revision_id: str
    input_revisions: dict
    verdict: str
    findings: list
    rationale: str


@dataclass(frozen=True)
class DecisionRequest:
    decision_id: str
    input_revisions: dict
    question: str
    variants: list
    specialist_judgments: list
    open_findings: list
    risks: list
    uncertainties: list
    revisions: list


@dataclass(frozen=True)
class RevisionDependency:
    revision_id: str
    upstream_step: str
    upstream_revision: str


@dataclass(frozen=True)
class HumanDecision:
    task_id: str
    human_actor: str
    timestamp: str
    decision: str
    notes: str
    input_revisions: dict
    finding_id: str | None = None


def current_output(task, step):
    revision = task["active_revisions"].get(step)
    for output in task["outputs"]:
        if output["revision_id"] == revision:
            if all(task["active_revisions"].get(s) == r
                   for s, r in output["input_revisions"].items()):
                return output
    raise ValueError(f"Ontbrekende of stale input: {step}")


def open_findings(task):
    # Old findings remain obligations even if their source revision is stale.
    return [f for f in task["findings"] if f["status"] not in {"RESOLVED", "ACCEPTED_RISK"}]


def check_critical(task):
    if any(f["severity"] == "CRITICAL" for f in open_findings(task)):
        raise ValueError("Open CRITICAL finding blokkeert de gate")


def check_design_approval(task):
    check_critical(task)
    package = current_output(task, "A01_PACKAGE")
    if not task["decision_requests"] or task["decision_requests"][-1]["input_revisions"] != package["input_revisions"]:
        raise ValueError("Actueel beslispakket ontbreekt")
    integration = current_output(task, "A03_INTEGRATION")
    for step in REVIEW_STEPS:
        output = current_output(task, step)
        review = next((r for r in task["reviews"] if r["review_id"] == output["revision_id"]), None)
        if (review is None or review["review_id"] in task["stale_reviews"]
                or review["revision_id"] != integration["revision_id"]
                or review["verdict"] not in {"PASS", "PASS_WITH_FINDINGS"}):
            raise ValueError("Actuele voldoende vakreview ontbreekt")
