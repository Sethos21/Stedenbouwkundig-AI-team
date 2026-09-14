"""Exactly one inventory call, with the existing deterministic review."""
from bvc_ai.agents.provider import DeterministicTestProvider


class InventorySmokeProvider:
    def __init__(self, provider):
        self._provider = provider
        self._used = False

    def inventory(self, brief, revision_points):
        if self._used:
            raise ValueError("Smoke-demo staat slechts één A02-call toe.")
        self._used = True
        return self._provider.inventory(brief, revision_points)

    def review(self, output):
        result = DeterministicTestProvider().review(output)
        result["findings"].append("Provider: mock; DeterministicTestProvider; rol: A07; smoke-review van TESTDATA.")
        return result
