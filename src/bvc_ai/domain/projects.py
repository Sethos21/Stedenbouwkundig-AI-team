"""Release 1 project identity and deliberately small lifecycle."""
from dataclasses import dataclass, asdict
from enum import StrEnum


class ProjectStatus(StrEnum):
    CREATED = "PROJECT_AANGEMAAKT"
    INTAKE = "INTAKE_IN_UITVOERING"
    RESEARCH = "ONDERZOEK_IN_UITVOERING"
    READY = "GEREED_VOOR_BEOORDELING"
    RELEASED = "ONDERZOEK_VRIJGEGEVEN_VOOR_ONTWERP"


TRANSITIONS = {
    ProjectStatus.CREATED: {ProjectStatus.INTAKE},
    ProjectStatus.INTAKE: {ProjectStatus.RESEARCH},
    ProjectStatus.RESEARCH: {ProjectStatus.READY},
    ProjectStatus.READY: {ProjectStatus.RESEARCH, ProjectStatus.RELEASED},
    ProjectStatus.RELEASED: set(),
}


def check_project_transition(current, target, *, human=False):
    current, target = ProjectStatus(current), ProjectStatus(target)
    if target == ProjectStatus.RELEASED and not human:
        raise PermissionError("Alleen HumanApprovalService mag onderzoek vrijgeven")
    if target not in TRANSITIONS[current]:
        raise ValueError(f"Verboden projectovergang: {current} -> {target}")


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Niet-lege tekst vereist: {field}")
    return value.strip()


@dataclass(frozen=True)
class Project:
    project_id: str
    name: str
    created_at: str
    updated_at: str
    status: ProjectStatus = ProjectStatus.CREATED
    research_type: str | None = None
    address: str | None = None
    location: str | None = None

    def __post_init__(self):
        for field in ("project_id", "name", "created_at", "updated_at"):
            text(getattr(self, field), field)
        ProjectStatus(self.status)
        for field in ("research_type", "address", "location"):
            if getattr(self, field) is not None:
                text(getattr(self, field), field)

    def to_dict(self):
        return asdict(self)
