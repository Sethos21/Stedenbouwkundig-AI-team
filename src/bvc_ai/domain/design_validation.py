"""Strict proposal validation; providers cannot supply workflow control fields."""
import math
import json
import re
from bvc_ai.domain.design import DESIGN_TYPES, SOURCE_TYPES, ENV_THEMES, Severity, Verdict, REVIEW_STEPS
from bvc_ai.domain.policies import K00Policy


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("Onverwachte of ontbrekende voorstelvelden")


def nonempty(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Niet-lege tekst vereist")


def strings(value):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError("Lijst met tekst vereist")


def forbidden(value):
    if isinstance(value, dict):
        if set(value) & {"human_approval", "source_status", "workflowstate", "status", "created_by", "actor", "decision", "capacity", "required_reviews"}:
            raise PermissionError("Provider mag geen beheerde status, identiteit of capaciteit schrijven")
        for item in value.values():
            forbidden(item)
    elif isinstance(value, list):
        for item in value:
            forbidden(item)
    elif isinstance(value, str) and re.search(r"\b(APPROVED|REJECTED|ACCEPTED_RISK|VERIFIED_SOURCE)\b", value, re.IGNORECASE):
        raise PermissionError("Menselijk besluit of bronpromotie in provideroutput verboden")


def validate_proposal(step, proposal, task, inputs):
    if len(json.dumps(proposal, allow_nan=False)) > 200000:
        raise ValueError("Voorstel te groot")
    exact(proposal, {"summary", "objects", "findings", "conditions", "variants", "responses", "review"})
    forbidden(proposal)
    nonempty(proposal["summary"])
    for key in ("objects", "findings", "conditions", "variants", "responses"):
        if not isinstance(proposal[key], list):
            raise ValueError(f"{key} moet een lijst zijn")
    actor = step.split("_")[0]
    allowed = {
        "A02": SOURCE_TYPES,
        "A03_HYPOTHESIS": DESIGN_TYPES - {"PROPOSED_ROUTE", "PROPOSED_ACCESS", "LANDSCAPE_STRUCTURE"},
        "A03_INTEGRATION": DESIGN_TYPES - {"PROPOSED_ROUTE", "PROPOSED_ACCESS", "LANDSCAPE_STRUCTURE"},
        "A04": {"LANDSCAPE_STRUCTURE", "PUBLIC_SPACE"},
        "A05": {"PROPOSED_ROUTE", "PROPOSED_ACCESS"},
    }.get(step, set())
    ids = set()
    geometry_registry = task["geometry_registry"]
    for obj in proposal["objects"]:
        exact(obj, {"local_id", "object_type", "geometry_ref", "geometry_status", "source_basis", "properties"})
        nonempty(obj["local_id"])
        if obj["local_id"] in ids:
            raise ValueError("Dubbel object in voorstel")
        ids.add(obj["local_id"])
        K00Policy.authorize(obj["local_id"], "write")
        if obj["object_type"] not in allowed:
            raise PermissionError(f"{actor} mag dit objecttype niet schrijven")
        expected = "EXISTING_VALIDATED" if step == "A02" else "PROPOSED"
        if obj["geometry_status"] != expected:
            raise PermissionError("Geometriestatus valt buiten rolbevoegdheid")
        ref = obj["geometry_ref"]
        if ref not in geometry_registry or geometry_registry[ref]["kind"] != ("source" if step == "A02" else "design"):
            raise ValueError("Alleen geregistreerde synthetische modelgeometrie toegestaan")
        strings(obj["source_basis"])
        if not obj["source_basis"] or any(s not in geometry_registry or geometry_registry[s]["kind"] != "source" for s in obj["source_basis"]):
            raise ValueError("Synthetische bronbasis ontbreekt")
        exact(obj["properties"], {"description", "density_per_ha"} if obj["object_type"] == "DEVELOPMENT_FIELD" else {"description"})
        nonempty(obj["properties"]["description"])
        if obj["object_type"] == "DEVELOPMENT_FIELD":
            density = obj["properties"]["density_per_ha"]
            if type(density) not in {int, float} or not math.isfinite(density) or not 0 < density <= 100:
                raise ValueError("Ongeldige TESTDATA-dichtheidsaanname")
    if allowed and not proposal["objects"]:
        raise ValueError("Specialistische objectoutput ontbreekt")
    if proposal["findings"] and actor not in {"A04", "A05", "A06", "A07", "A08"}:
        raise PermissionError("Rol mag geen specialistische findings schrijven")
    for finding in proposal["findings"]:
        exact(finding, {"severity", "description", "spatial_effect", "classification"})
        Severity(finding["severity"])
        for key in ("description", "spatial_effect"):
            nonempty(finding[key])
        if finding["classification"] not in {"HARD_CONSTRAINT", "ENVIRONMENTAL_RISK", "STEERING", "UNCERTAIN", "RESEARCH_REQUIRED"}:
            raise ValueError("Onbekende findingclassificatie")
    if proposal["conditions"] and step not in {"A06", "A08_GATE"}:
        raise PermissionError("Rol mag geen beleids- of milieucondities schrijven")
    for condition in proposal["conditions"]:
        exact(condition, {"theme", "classification", "description"})
        nonempty(condition["theme"])
        nonempty(condition["description"])
        allowed_classes = {"HARD_CONSTRAINT", "STEERING", "UNCERTAIN"} if step == "A06" else {"HARD_CONSTRAINT", "ENVIRONMENTAL_RISK", "STEERING", "UNCERTAIN", "RESEARCH_REQUIRED"}
        if condition["classification"] not in allowed_classes:
            raise ValueError("Ongeldige conditieclassificatie")
    if step == "A06" and not {"HARD_CONSTRAINT", "STEERING", "UNCERTAIN"}.issubset({c["classification"] for c in proposal["conditions"]}):
        raise ValueError("Beleidsclassificaties ontbreken")
    if step == "A08_GATE" and {c["theme"] for c in proposal["conditions"]} != ENV_THEMES:
        raise ValueError("Milieu/ecologische themascreening onvolledig")
    if step == "A03_HYPOTHESIS":
        if len(proposal["variants"]) < 2:
            raise ValueError("Minimaal twee conceptvarianten vereist")
        for variant in proposal["variants"]:
            exact(variant, {"name", "strategy", "object_ids"})
            nonempty(variant["name"])
            nonempty(variant["strategy"])
            strings(variant["object_ids"])
            if not variant["object_ids"] or not set(variant["object_ids"]) <= ids:
                raise ValueError("Variant verwijst naar ontbrekende objecten")
        object_refs = {o["local_id"]: o["geometry_ref"] for o in proposal["objects"]}
        signatures = {tuple(sorted(object_refs[i] for i in v["object_ids"])) for v in proposal["variants"]}
        if len(signatures) < 2:
            raise ValueError("Varianten hebben identieke objectsets")
    elif proposal["variants"]:
        raise PermissionError("Alleen hypothese maakt varianten")
    if proposal["responses"] and step != "A03_INTEGRATION":
        raise PermissionError("Alleen integratie registreert verwerking")
    obligations = {f["finding_id"] for f in task["findings"] if f["status"] not in {"RESOLVED", "ACCEPTED_RISK"}}
    response_ids = []
    for response in proposal["responses"]:
        exact(response, {"finding_id", "explanation"})
        nonempty(response["explanation"])
        if response["finding_id"] not in obligations:
            raise ValueError("Verwerking verwijst naar onbekende of gesloten finding")
        response_ids.append(response["finding_id"])
    if step == "A03_INTEGRATION" and (set(response_ids) != obligations or len(response_ids) != len(obligations)):
        raise ValueError("Integratie moet alle open findings expliciet behandelen")
    review = proposal["review"]
    if step in REVIEW_STEPS:
        exact(review, {"revision_id", "input_revisions", "verdict", "rationale", "resolved_findings"})
        Verdict(review["verdict"])
        nonempty(review["rationale"])
        strings(review["resolved_findings"])
        if len(set(review["resolved_findings"])) != len(review["resolved_findings"]):
            raise ValueError("Dubbele findingresolutie")
        if review["verdict"] == "PASS" and (proposal["findings"] or obligations - set(review["resolved_findings"])):
            raise ValueError("Open findings vereisen PASS_WITH_FINDINGS of een herstelverdict")
        if review["input_revisions"] != inputs or review["revision_id"] != inputs["A03_INTEGRATION"]:
            raise ValueError("Review hoort niet bij exact de actuele inputrevisies")
        if review["verdict"] in {"REVISE", "BLOCKED", "PASS_WITH_FINDINGS"} and not proposal["findings"] and not obligations:
            raise ValueError("Review vereist inhoudelijke findings")
        integration = next(o for o in task["outputs"] if o["revision_id"] == inputs["A03_INTEGRATION"])
        addressed = {r["finding_id"] for r in integration["output"]["responses"]}
        for fid in review["resolved_findings"]:
            finding = next((f for f in task["findings"] if f["finding_id"] == fid), None)
            if finding is None or finding["created_by"] != actor or fid not in addressed or fid not in obligations:
                raise PermissionError("Alleen eigenaar mag aantoonbaar verwerkte finding oplossen")
    elif review is not None:
        raise PermissionError("Review buiten reviewstap")
