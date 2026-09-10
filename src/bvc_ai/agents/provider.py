from typing import Protocol
from copy import deepcopy

class AIProvider(Protocol):
    def inventory(self, brief: dict, revision_points: list) -> dict: ...
    def review(self, output: dict) -> dict: ...

class DeterministicTestProvider:
    def inventory(self, brief, revision_points):
        return {
            "sources": deepcopy(brief["sources"]),
            "missing_data": ["Alle officiële bronbestanden ontbreken; niets is gedownload."],
            "geometry_uncertainties": ["CRS, actualiteit, nauwkeurigheid en projectgrens zijn niet vastgesteld."],
            "k00_discrepancies": ["K00 is niet aangeleverd; vergelijking is niet uitgevoerd."],
            "recommendations": ["Sluit later officiële BGT, BAG en BRK-bronnen aan; PDOK is een voorziening, geen zelfstandige geometrische bron."],
        }

    def review(self, output):
        findings = []
        for key in ("missing_data", "geometry_uncertainties", "k00_discrepancies", "recommendations"):
            if not output["payload"].get(key):
                findings.append(f"Vul {key} concreet aan.")
        if output["source_status"] != "TESTDATA":
            findings.append("Markeer alle fixturedata expliciet als TESTDATA.")
        return {"verdict": "INSUFFICIENT" if findings else "SUFFICIENT", "findings": findings}
