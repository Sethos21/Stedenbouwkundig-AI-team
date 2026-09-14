"""Deterministic synthetic proposal data; no tools, approval or state mutation."""
from bvc_ai.domain.design import ENV_THEMES, REVIEW_STEPS


def object_proposal(local_id, object_type, geometry_ref, description, density=None):
    props = {"description": description}
    if density is not None:
        props["density_per_ha"] = density
    return dict(local_id=local_id, object_type=object_type, geometry_ref=geometry_ref,
                geometry_status="EXISTING_VALIDATED" if object_type in {"PROJECT_BOUNDARY", "EXISTING_FEATURE", "SOURCE_ZONE"} else "PROPOSED",
                source_basis=["fixture/boundary"], properties=props)


def finding(description, effect, severity="MAJOR", classification="STEERING"):
    return dict(severity=severity, description=description, spatial_effect=effect, classification=classification)


def design_proposal(step, context, inputs):
    result = dict(summary=f"{step}: uitsluitend synthetische TESTDATA; geen formeel onderzoek of toestemming.",
                  objects=[], findings=[], conditions=[], variants=[], responses=[], review=None)
    if step == "A02":
        result["objects"] = [object_proposal("boundary", "PROJECT_BOUNDARY", "fixture/boundary", "Synthetische projectgrens"),
                             object_proposal("existing", "EXISTING_FEATURE", "fixture/existing", "Immutable synthetische watergang")]
        result["objects"] += [object_proposal(f"zone{i}", "SOURCE_ZONE", f"fixture/zone{i}", f"Synthetische bronzone {i}") for i in range(1, 4)]
    elif step == "A06":
        result["conditions"] = [
            dict(theme="watergang", classification="HARD_CONSTRAINT", description="TESTDATA: behoud watergang en vrije strook x=0..30; geen bouwobjecten daar."),
            dict(theme="groen", classification="STEERING", description="TESTDATA: verbind centrale openbare ruimte met oostelijke groenzone."),
            dict(theme="programma", classification="UNCERTAIN", description="TESTDATA: toegestane functiemenging onbekend; dit is geen toestemming."),
        ]
    elif step == "A08_GATE":
        result["conditions"] = [dict(theme=theme, classification="ENVIRONMENTAL_RISK" if theme == "geluid" else "RESEARCH_REQUIRED",
              description="TESTDATA: noordrand kent indicatief geluidrisico; houd afstand." if theme == "geluid" else f"TESTDATA {theme}: geen formeel onderzoek uitgevoerd; specialistisch onderzoek vereist, geen toestemming.") for theme in sorted(ENV_THEMES)]
        result["findings"] = [finding("Indicatief geluidrisico aan noordrand", "Verplaats bouwvelden zuidwaarts en houd noordelijke buffer vrij", classification="ENVIRONMENTAL_RISK")]
    elif step == "A03_HYPOTHESIS":
        result["objects"] = [object_proposal("compact", "DEVELOPMENT_FIELD", "design/compact", "Compact centraal veld, dichtheid als aanname", 40),
                             object_proposal("linear", "DEVELOPMENT_FIELD", "design/linear", "Langgerekt oostelijk veld, lagere dichtheid", 25)]
        result["variants"] = [dict(name="Compact", strategy="Compact centraal woonveld met brede oostelijke groenruimte", object_ids=["compact"]),
                              dict(name="Lineair", strategy="Langgerekte oostelijke bebouwing met centrale open ruimte", object_ids=["linear"])]
    elif step == "A04":
        result["objects"] = [object_proposal("green", "LANDSCAPE_STRUCTURE", "design/green", "Groen-blauwe drager verbindt de zuidrand met het oosten")]
        result["findings"] = [finding("Groenverbinding ontbreekt in compacte hypothese", "Reserveer ooststrook x=240..280 voor landschappelijke verbinding", "MINOR")]
    elif step == "A05":
        result["objects"] = [object_proposal("access", "PROPOSED_ACCESS", "design/access", "Zuidelijke toegang; parkeeroplossing vereist latere uitwerking")]
        result["findings"] = [finding("Toegang doorsnijdt centraal veld in hypothese", "Houd zuidstrook y=30..50 vrij voor toegang", "MINOR")]
    elif step == "A03_INTEGRATION":
        result["objects"] = [object_proposal("integrated", "DEVELOPMENT_FIELD", "design/integrated", "Compacte variant: zuidwaarts verschoven, oostelijke groenstrook en zuidelijke toegang vrijgehouden", 40),
                             object_proposal("central", "CENTRAL_PLACE", "design/central", "Centrale ontmoetingsruimte naast landschappelijke verbinding")]
        result["responses"] = [dict(finding_id=f["finding_id"], explanation={
            "A08": "Noordgrens bouwveld teruggebracht tot y=200; indicatief risico blijft open tot formeel geluidonderzoek.",
            "A04": "Oostgrens bouwveld x=230; strook x=240..280 blijft vrij. A04-landschapsobject behouden via inputrevision.",
            "A05": "Zuidgrens bouwveld y=60; toegang y=30..50 blijft vrij. A05-toegangsobject behouden via inputrevision.",
            "A07": "Gemeentelijke onderzoeksvraag opgenomen als resterende onzekerheid in het beslispakket.",
        }.get(f["created_by"], "Finding blijft expliciet open voor bevoegde beoordeling."))
            for f in context["findings"] if f["status"] not in {"RESOLVED", "ACCEPTED_RISK"}]
    elif step in REVIEW_STEPS:
        actor = step.split("_")[0]
        resolved = [f["finding_id"] for f in context["findings"] if f["created_by"] == actor and f["status"] in {"OPEN", "UNRESOLVED", "BLOCKED"}] if actor in {"A04", "A05"} else []
        result["review"] = dict(revision_id=inputs["A03_INTEGRATION"], input_revisions=inputs,
             verdict="PASS_WITH_FINDINGS", rationale={
                 "A04": "Integratie houdt de oostelijke groenstrook vrij en behoudt de voorgestelde landschappelijke drager; detailuitwerking volgt.",
                 "A05": "Integratie houdt de zuidelijke toegang vrij; parkeren en verkeerskundige capaciteit zijn niet doorgerekend.",
                 "A08": "Bouwveld ligt zuidelijker, maar indicatieve geluidrisico's en alle formele onderzoeksvragen blijven open.",
                 "A07": "Indieningsreview TESTDATA: ruimtelijke verwerking traceerbaar; beleid, milieuonderzoek en parkeeronderbouwing ontbreken nog. Geen vergunningoordeel.",
             }[actor], resolved_findings=resolved)
        if actor == "A07":
            result["findings"] = [finding("Formele milieu- en parkeeronderbouwing ontbreekt voor indiening", "Bouwgrenzen en ontsluiting blijven indicatief tot onderbouwing beschikbaar is", "MAJOR", "RESEARCH_REQUIRED")]
    return result
