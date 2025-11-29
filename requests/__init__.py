"""Lightweight fallback implementation of the requests API.

This module provides a minimal subset of the requests interface so the
application can run in environments without network package installs.
"""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, Optional


class HTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.response = type("obj", (), {"status_code": status_code})


@dataclass
class _Response:
    status_code: int
    content: bytes
    headers: Dict[str, str]

    @property
    def text(self) -> str:
        try:
            return self.content.decode("utf-8")
        except Exception:
            return self.content.decode(errors="ignore")

    def json(self):
        return json.loads(self.text or "{}")

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise HTTPError(self.status_code, f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 8192) -> Iterable[bytes]:
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


def _do_request(method: str, url: str, headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None, timeout: int = 30) -> _Response:
    request = urllib.request.Request(url=url, headers=headers or {}, data=data, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return _Response(status_code=resp.getcode(), content=resp.read(), headers=dict(resp.headers))
    except urllib.error.HTTPError as exc:
        return _Response(status_code=exc.code, content=exc.read(), headers=dict(exc.headers))


def get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30, stream: bool = False) -> _Response:
    # stream parameter kept for compatibility
    return _do_request("GET", url, headers=headers, data=None, timeout=timeout)


def post(url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Dict] = None, timeout: int = 30) -> _Response:
    data_bytes = None
    request_headers = headers or {}
    if json is not None:
        data_bytes = json.dumps(json).encode("utf-8")
        request_headers = {**request_headers, "Content-Type": "application/json"}
    return _do_request("POST", url, headers=request_headers, data=data_bytes, timeout=timeout)
