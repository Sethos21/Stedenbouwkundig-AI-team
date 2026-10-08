"""Runtime-only DSO credential boundary; one closed read-only POST search."""
import http.client
import os
import queue
import socket
import threading
import time

from bvc_ai.adapters.dso_contract import canonical, read_json
from bvc_ai.adapters.dso_diagnostics import mark
from bvc_ai.adapters.dso_discovery import HOST, PATH, validate_request
from bvc_ai.adapters.source_transport import HttpResponse, ResponseOrigin


class DSOLivePostTransport:
    def __init__(self, *, live_opt_in=False):
        self._live_opt_in = live_opt_in

    def post(self, request):
        validate_request(request)
        return self._send(request)

    def _send(self, request):
        # Both callers use closed profiles; this helper is never arbitrary HTTP.
        if request.method == 'GET':
            from bvc_ai.adapters.ow_document import validate_request as validate_ow
            validate_ow(request)
        else:
            validate_request(request)
        if self._live_opt_in is not True:
            raise PermissionError('Explicit DSO live opt-in required')
        key = os.environ.get('DSO_API_KEY')
        if not key:
            raise mark(ValueError('DSO_API_KEY is required for live discovery'), 'transport', 'AUTHENTICATION')
        if any(not 33 <= ord(c) <= 126 for c in key):
            raise mark(ValueError('Invalid DSO credential configuration'), 'transport', 'AUTHENTICATION')
        if key in request.url or key in getattr(request, 'body', b'').decode('utf-8'):
            raise ValueError('DSO request rejected')
        deadline = time.monotonic() + request.timeout_seconds
        results = queue.Queue(maxsize=1)
        cancelled = threading.Event()
        # Construction contains no credentials. Never enable HTTP debug output.
        connection = http.client.HTTPSConnection(HOST, timeout=request.timeout_seconds)
        connection.set_debuglevel(0)

        def remaining():
            seconds = deadline - time.monotonic()
            if cancelled.is_set() or seconds <= 0:
                raise mark(TimeoutError('DSO request deadline exceeded'), 'transport', 'NETWORK_TRANSPORT')
            return seconds

        def receive():
            result = None
            status, version = None, None
            try:
                connection.connect()
                connection.sock.settimeout(remaining())
                headers = dict(request.headers)
                headers.update({'X-API-Key': key, 'Accept-Encoding': 'identity'})
                connection.request(request.method, request.url.split(HOST, 1)[1],
                                   body=getattr(request, 'body', None), headers=headers)
                connection.sock.settimeout(remaining())
                response = connection.getresponse()
                status = response.status
                raw_headers = response.getheaders()
                if any(key in name or key in value for name, value in raw_headers):
                    raise ValueError('DSO response rejected')
                headers = {}
                for name, value in raw_headers:
                    name = name.lower()
                    if name in headers:
                        raise ValueError('DSO response rejected')
                    headers[name] = value
                version = headers.get('api-version')
                if status != 200:
                    category = 'AUTHENTICATION' if status in (401, 403) else 'UNEXPECTED_HTTP_STATUS'
                    raise mark(OSError('DSO HTTP request failed'), 'response', category, status, version)
                if headers.get('content-encoding', 'identity') != 'identity':
                    raise ValueError('DSO response rejected')
                chunks, size = [], 0
                while True:
                    seconds = remaining()
                    if connection.sock is not None:
                        connection.sock.settimeout(seconds)
                    chunk = response.read1(min(65536, request.max_response_bytes - size + 1))
                    remaining()
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > request.max_response_bytes:
                        raise ValueError('DSO response limit exceeded')
                    chunks.append(chunk)
                body = b''.join(chunks)
                length = headers.get('content-length')
                if length is not None and (not length.isdigit() or int(length) != size):
                    raise ValueError('DSO truncated response')
                # Reject reflection BEFORE anything is returned, persisted or hashed.
                # JSON decoding also detects unicode-escaped credential reflection.
                if key.encode() in body or key in canonical(read_json(body)):
                    raise ValueError('DSO response rejected')
                result = HttpResponse(200, tuple((n, headers[n]) for n in
                                      ('content-type', 'api-version') if n in headers),
                                      body, ResponseOrigin.PROVIDER_RESPONSE)
            except Exception as error:
                # Discard original exception and traceback inside the worker.
                data = getattr(error, 'dso_diagnostic', None)
                if type(data) is dict:
                    result = mark(OSError('DSO request failed'), data['phase'], data['category'],
                                  data['http_status'], data['contract_version'])
                elif isinstance(error, (OSError, http.client.HTTPException)):
                    result = mark(OSError('DSO transport failed'), 'transport', 'NETWORK_TRANSPORT', status, version)
                elif isinstance(error, ValueError):
                    result = mark(OSError('DSO response rejected'), 'response', 'SCHEMA_VALIDATION', status, version)
                else:
                    result = mark(OSError('DSO internal failure'), 'transport', 'INTERNAL_APPLICATION', status, version)
            finally:
                try:
                    connection.close()
                except Exception:
                    pass
                results.put(result)

        threading.Thread(target=receive, name='dso-bounded-discovery', daemon=True).start()
        try:
            try:
                result = results.get(timeout=remaining())
            except queue.Empty:
                raise mark(TimeoutError('DSO request deadline exceeded'), 'transport', 'NETWORK_TRANSPORT') from None
            remaining()
            if isinstance(result, Exception):
                raise result from None
            return result
        finally:
            cancelled.set()
            active_socket = connection.sock
            if active_socket is not None:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
            try:
                connection.close()
            except Exception:
                pass


class DSOLiveOWTransport(DSOLivePostTransport):
    """Only the closed Presenteren OW GET profile; same credential boundary."""
    def get(self, request):
        from bvc_ai.adapters.ow_document import validate_request as validate_ow
        validate_ow(request)
        return self._send(request)
