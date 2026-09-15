"""Fail-closed verification of DESIGN-TEST-001 rectangles, not a GIS engine.
Unknown findings or geometry require further specialist/human verification.
"""
import math

RULES = {
    "A04": ("Groenverbinding ontbreekt in compacte hypothese",
            "Reserveer ooststrook x=240..280 voor landschappelijke verbinding",
            "LANDSCAPE_STRUCTURE", "design/green", (240, 30, 280, 250)),
    "A05": ("Toegang doorsnijdt centraal veld in hypothese",
            "Houd zuidstrook y=30..50 vrij voor toegang",
            "PROPOSED_ACCESS", "design/access", (30, 30, 230, 50)),
}


def rectangle(registry, ref):
    geometry = registry.get(ref, {})
    points = geometry.get("coordinates", [])
    if (geometry.get("kind") != "design" or geometry.get("source_status") != "TESTDATA"
            or geometry.get("crs") != "SYNTHETIC_LOCAL_METRES" or len(points) != 4):
        return None
    if any(len(p) != 2 or any(type(n) not in {int, float} or not math.isfinite(n) for n in p) for p in points):
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    bounds = min(xs), min(ys), max(xs), max(ys)
    x0, y0, x1, y1 = bounds
    if x0 >= x1 or y0 >= y1 or {tuple(p) for p in points} != {(x0,y0),(x0,y1),(x1,y0),(x1,y1)}:
        return None
    if any(a[0] != b[0] and a[1] != b[1] for a,b in zip(points, points[1:]+points[:1])):
        return None
    return bounds


def resolution_evidence(task, finding, integration_revision):
    """Return runtime-computed evidence for an exact revision, or None."""
    actor = finding["created_by"]
    rule = RULES.get(actor)
    if (task.get("project_id") != "DESIGN-TEST-001" or task.get("source_status") != "TESTDATA"
            or rule is None or finding["revision_id"].split("/v")[0] != actor):
        return None
    description, effect, specialist_type, specialist_ref, required_bounds = rule
    if (finding["description"] != description or finding["spatial_effect"] != effect
            or finding["classification"] != "STEERING"):
        return None
    integration = next((o for o in task["outputs"] if o["revision_id"] == integration_revision), None)
    if (integration is None or task["active_revisions"].get("A03_INTEGRATION") != integration_revision
            or any(task["active_revisions"].get(s) != r for s,r in integration["input_revisions"].items())):
        return None
    objects = [o for o in task["objects"] if o["revision_id"] == integration_revision]
    if any(o["object_type"] not in {"DEVELOPMENT_FIELD", "CENTRAL_PLACE"} for o in objects):
        return None
    fields = [o for o in objects if o["object_type"] == "DEVELOPMENT_FIELD"]
    specialists = [o for o in task["objects"] if o["revision_id"] == integration["input_revisions"].get(actor)
                   and o["object_type"] == specialist_type and o["geometry_ref"] == specialist_ref
                   and o["geometry_status"] == "PROPOSED"]
    registry = task["geometry_registry"]
    if not fields or not specialists or rectangle(registry, specialist_ref) != required_bounds:
        return None
    checked = []
    for obj in objects:
        bounds = rectangle(registry, obj["geometry_ref"])
        if bounds is None or obj["geometry_status"] != "PROPOSED":
            return None
        if (actor == "A04" and bounds[2] > 240) or (actor == "A05" and bounds[1] < 50):
            return None
        checked.append({"object_id": obj["object_id"], "geometry_ref": obj["geometry_ref"], "bounds": list(bounds)})
    return {"rule_id": f"synthetic/{actor}/clear-strip/v1", "integration_revision_id": integration_revision,
            "input_revisions": dict(integration["input_revisions"]), "checked_objects": checked,
            "specialist_object_ids": [o["object_id"] for o in specialists], "source_status": "TESTDATA"}
