"""Opt-in, stateless HTTPS GET for the fixed PDOK pand request profile."""
import http.client
import math
import queue
import socket
import threading
import time
from urllib.parse import parse_qsl, urlsplit

from bvc_ai.adapters.pdok_bgt import ITEMS_URL, JSON_FG, RD_URI, _continuation
from bvc_ai.adapters.source_transport import GetRequest, HttpResponse, ResponseOrigin

BBOX = '176492.301,360605.561,176992.301,361105.561'


def validate_live_request(request):
    if not isinstance(request, GetRequest) or request.method != 'GET':
        raise ValueError('GET request required')
    if _continuation(request.url, ITEMS_URL) != request.url:
        raise ValueError('Absolute PDOK endpoint required')
    pairs = tuple(parse_qsl(urlsplit(request.url).query, keep_blank_values=True))
    if pairs != request.parameters or len(dict(pairs)) != len(pairs):
        raise ValueError('Exact unique request parameters required')
    params = dict(pairs)
    expected = {'bbox': BBOX, 'bbox-crs': RD_URI, 'crs': RD_URI, 'f': 'jsonfg', 'limit': '1000'}
    if any(params.get(k) != v for k, v in expected.items()):
        raise ValueError('Explicit Mastenbroekweg RD query scope required')
    if set(params) - (set(expected) | {'cursor'}):
        raise ValueError('Unsupported query parameter')
    if 'cursor' in params and not params['cursor']:
        raise ValueError('Empty continuation')
    if request.headers != (('Accept', JSON_FG),):
        raise ValueError('Only the JSON-FG Accept header is allowed')
    if (type(request.timeout_seconds) not in (float, int)
            or not math.isfinite(request.timeout_seconds) or request.timeout_seconds <= 0
            or type(request.max_response_bytes) is not int or request.max_response_bytes < 1):
        raise ValueError('Positive finite transport budgets required')


class PDOKLiveGetTransport:
    """No proxy, redirects, cookies, credentials, decompression or session reuse.

    The calling thread has a total deadline including DNS/TLS/headers/body.
    A daemon worker permits bounded return even when OS DNS is stalled; it checks
    cancellation before sending GET. An active socket is shut down on timeout.
    Python plugins remain trusted code, not a security sandbox.
    """
    def get(self, request):
        validate_live_request(request)
        deadline = time.monotonic() + request.timeout_seconds
        result = queue.Queue(maxsize=1)
        cancelled = threading.Event()
        connection = http.client.HTTPSConnection('api.pdok.nl', timeout=request.timeout_seconds)

        def remaining():
            seconds = deadline - time.monotonic()
            if cancelled.is_set() or seconds <= 0:
                raise TimeoutError('PDOK total request deadline exceeded')
            return seconds

        def receive():
            try:
                connection.connect()
                connection.sock.settimeout(remaining())
                parts = urlsplit(request.url)
                connection.request('GET', parts.path + '?' + parts.query,
                                   headers={'Accept': JSON_FG, 'Accept-Encoding': 'identity'})
                connection.sock.settimeout(remaining())
                response = connection.getresponse()
                headers = tuple(response.getheaders())
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
                        raise OSError('PDOK response byte cap exceeded')
                    chunks.append(chunk)
                lengths = [v for k, v in headers if k.lower() == 'content-length']
                if lengths and (len(lengths) != 1 or not lengths[0].isdigit()
                                or int(lengths[0]) != size):
                    raise OSError('PDOK response Content-Length mismatch')
                result.put((HttpResponse(response.status, headers, b''.join(chunks),
                                         ResponseOrigin.PROVIDER_RESPONSE), None))
            except Exception as exc:
                error = OSError(str(exc)) if isinstance(exc, http.client.HTTPException) else exc
                result.put((None, error))
            finally:
                connection.close()

        threading.Thread(target=receive, name='pdok-bounded-get', daemon=True).start()
        try:
            response, error = result.get(timeout=remaining())
            remaining()
            if error is not None:
                raise error
            return response
        except queue.Empty:
            raise TimeoutError('PDOK total request deadline exceeded') from None
        finally:
            cancelled.set()
            active_socket = connection.sock
            if active_socket is not None:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()
