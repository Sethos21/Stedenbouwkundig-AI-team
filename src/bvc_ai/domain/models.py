from dataclasses import dataclass, field, asdict
from enum import StrEnum
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat()

class Status(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    SPECIALIST_COMPLETE = "SPECIALIST_COMPLETE"
    REVIEW_PENDING = "REVIEW_PENDING"
    REVIEWED = "REVIEWED"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"

class SourceStatus(StrEnum):
    VERIFIED_SOURCE = "VERIFIED_SOURCE"
    PROJECT_DATA = "PROJECT_DATA"
    DERIVED = "DERIVED"
    INDICATIVE = "INDICATIVE"
    TESTDATA = "TESTDATA"
    DESIGN_ASSUMPTION = "DESIGN_ASSUMPTION"

@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    description: str
    status: str = Status.DRAFT
    assigned_agent: str = "A01"
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    input_refs: tuple = ()
    output_refs: tuple = ()
    review_status: str = "PENDING"
    human_approval: dict | None = None

@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    name: str
    active: bool
    responsibilities: list
    forbidden: list

@dataclass(frozen=True)
class SourceReference:
    source_id: str
    label: str
    source_type: str
    source_status: str
    location: str
    geometry_origin: str
    def __post_init__(self):
        SourceStatus(self.source_status)
        if self.source_type == "fixture" and self.source_status != SourceStatus.TESTDATA:
            raise ValueError("Fixtures moeten TESTDATA blijven")

@dataclass(frozen=True)
class AgentOutput:
    task_id: str
    agent_id: str
    timestamp: str
    input_refs: list
    source_refs: list
    source_type: str
    source_status: str
    confidence: float
    output_version: int
    reviewer: str | None
    review_status: str
    human_approval: dict | None
    notes: list
    kind: str
    payload: dict

@dataclass(frozen=True)
class Review:
    task_id: str
    reviewer: str
    timestamp: str
    output_version: int
    verdict: str
    findings: list

@dataclass(frozen=True)
class Approval:
    task_id: str
    human_actor: str
    timestamp: str
    decision: str
    notes: str = ""

@dataclass(frozen=True)
class AuditEvent:
    task_id: str
    actor: str
    action: str
    timestamp: str
    details: dict
