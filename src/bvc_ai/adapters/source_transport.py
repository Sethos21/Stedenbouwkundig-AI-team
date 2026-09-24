"""Small GET-only boundary. Phase 3A supplies no live network implementation."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from bvc_ai.domain.sources import RawResponse, required


class ResponseOrigin(StrEnum):
    TESTDATA = "TESTDATA"
    PROVIDER_RESPONSE = "UNVALIDATED_PROVIDER_RESPONSE"


@dataclass(frozen=True)
class GetRequest:
    url: str
    parameters: tuple[tuple[str, str], ...]
    headers: tuple[tuple[str, str], ...]
    timeout_seconds: float = 15.0
    max_response_bytes: int = 8 * 1024 * 1024
    method: str = field(default="GET", init=False)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    origin: ResponseOrigin

    def __post_init__(self):
        if type(self.status) is not int or not 100 <= self.status <= 599:
            raise ValueError("HTTP status required")
        if type(self.body) is not bytes:
            raise ValueError("Exact response bytes required")
        if type(self.headers) is not tuple:
            raise ValueError("Immutable header pairs required")
        for pair in self.headers:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError("Header pair required")
            required(pair[0])
            if not isinstance(pair[1], str):
                raise ValueError("Text header value required")
        ResponseOrigin(self.origin)


class GetTransport(Protocol):
    def get(self, request: GetRequest) -> HttpResponse:
        """Return exact bytes/headers, without redirects or parsing. Implementations MUST
        enforce timeout_seconds over the entire request/body read and enforce
        max_response_bytes while reading; raise TimeoutError/OSError on interruption.
        This is a trusted contract, not cancellation of arbitrary Python code."""
        ...


@dataclass(frozen=True)
class CapturedResponse:
    request: GetRequest
    response: HttpResponse
    raw: RawResponse
    retrieval_started_at: str
    retrieval_finished_at: str
