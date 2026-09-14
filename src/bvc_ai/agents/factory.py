"""Provider selection at the composition boundary."""
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.agents.openai_provider import OpenAIProvider, DEFAULT_MODEL


def create_provider(name="mock", *, model=DEFAULT_MODEL, timeout=30):
    if name == "mock":
        return DeterministicTestProvider()
    if name == "openai":
        return OpenAIProvider(model=model, timeout=timeout)
    raise ValueError("Onbekende provider; kies mock of openai.")
