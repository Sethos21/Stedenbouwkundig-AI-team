"""Closed diagnostic vocabulary; never serialize exception text or headers."""
from functools import wraps
import os
import re

PHASES = {"discovery", "transport", "response", "validatie"}
CATEGORIES = {"AUTHENTICATION", "NETWORK_TRANSPORT", "UNEXPECTED_HTTP_STATUS",
              "CONTRACT_VERSION_MISMATCH", "SCHEMA_VALIDATION", "INTERNAL_APPLICATION"}


def diagnostic(phase, category, status=None, version=None):
    # Only bounded semantic versions; never arbitrary provider strings.
    if type(version) is not str or not re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", version):
        version = None
    key = os.environ.get("DSO_API_KEY")
    if key and version and key in version:
        version = None
    return dict(phase=phase if phase in PHASES else "validatie",
                category=category if category in CATEGORIES else "INTERNAL_APPLICATION",
                http_status=status if type(status) is int and 100 <= status <= 599 else None,
                contract_version=version)


def mark(error, phase, category, status=None, version=None):
    error.dso_diagnostic = diagnostic(phase, category, status, version)
    return error


def report(error):
    data = getattr(error, "dso_diagnostic", None)
    if type(data) is not dict:
        return diagnostic("validatie", "INTERNAL_APPLICATION")
    return diagnostic(data.get("phase"), data.get("category"),
                      data.get("http_status"), data.get("contract_version"))


def response_validation(function):
    """Annotate errors at the parser boundary without changing exception contracts."""
    @wraps(function)
    def wrapped(response, *args, **kwargs):
        try:
            return function(response, *args, **kwargs)
        except ValueError as error:
            data = getattr(error, "dso_diagnostic", None)
            versions = [v for k, v in response.headers if k.lower() == "api-version"] if hasattr(response, "headers") else []
            status = getattr(response, "status", None)
            category = data["category"] if type(data) is dict else "SCHEMA_VALIDATION"
            mark(error, "validatie", category, status, versions[0] if len(versions) == 1 else None)
            raise
    return wrapped
