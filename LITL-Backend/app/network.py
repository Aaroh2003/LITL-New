import json
import time

import httpx


class RemoteError(Exception):
    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


def _error_payload(response, deadline):
    raw = bytearray()
    try:
        for chunk in response.iter_bytes():
            if time.monotonic() > deadline or len(raw) + len(chunk) > 2048:
                break
            raw.extend(chunk)
        parsed = json.loads(bytes(raw))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def bounded_request(client, method, url, *, limit=4 * 1024 * 1024, deadline_seconds=20, **kwargs):
    deadline = time.monotonic() + deadline_seconds
    try:
        with client.stream(method, url, **kwargs) as response:
            if response.status_code < 200 or response.status_code >= 300:
                raise RemoteError(
                    f"Remote service returned HTTP {response.status_code}",
                    status=response.status_code,
                    payload=_error_payload(response, deadline),
                )
            length = response.headers.get("content-length")
            if length and int(length) > limit:
                raise RemoteError("Remote response exceeds safety limit")
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise RemoteError("Compressed HTTP responses are not accepted by the bounded connector")
            data = bytearray()
            for chunk in response.iter_bytes():
                if time.monotonic() > deadline or len(data) + len(chunk) > limit:
                    raise RemoteError("Remote response exceeds time/size limit")
                data.extend(chunk)
            return bytes(data)
    except (httpx.HTTPError, ValueError) as exc:
        raise RemoteError("Remote service is unavailable or returned an invalid response") from exc


def request_json(client, method, url, **kwargs):
    try:
        result = json.loads(bounded_request(client, method, url, **kwargs))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RemoteError("Remote service returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RemoteError("Remote service returned an invalid response shape")
    return result


def http_client():
    return httpx.Client(
        timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=False, trust_env=False,
        headers={"Accept-Encoding": "identity"},
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
    )
