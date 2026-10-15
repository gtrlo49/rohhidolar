"""HTTP access: browser-like identity, retries and a polite per-host delay."""

import os
import ssl
import time
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlparse

import httpx

CONTACT = os.environ.get("BOLIDOLAR_CONTACT", "+contact-pending")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    f"Version/17.0 Safari/605.1.15 BoliDolar/1.0 ({CONTACT})"
)
# robots.txt of the BCB asks for Crawl-delay: 10
DEFAULT_HOST_DELAYS = {"www.bcb.gob.bo": 10.0}
# www.bcp.com.bo resets connections that use Python's default TLS cipher policy (curl works).
# For this host only we lower OpenSSL's security level to 1; the certificate is still verified.
LEGACY_TLS_HOSTS = frozenset({"www.bcp.com.bo"})


class FetchError(Exception):
    """A page could not be downloaded."""


class Fetcher(Protocol):
    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str: ...

    def post_json(
        self, url: str, payload: dict[str, object], headers: dict[str, str] | None = None
    ) -> str: ...


class HttpFetcher:
    def __init__(
        self,
        client: httpx.Client | None = None,
        retries: int = 3,
        backoff: float = 2.0,
        host_delays: dict[str, float] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client or self._new_client()
        self._custom_client = client is not None
        self._legacy_client: httpx.Client | None = None
        self._retries = retries
        self._backoff = backoff
        self._delays = DEFAULT_HOST_DELAYS if host_delays is None else host_delays
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}

    @staticmethod
    def _new_client(legacy_tls: bool = False) -> httpx.Client:
        verify: ssl.SSLContext | bool = True
        if legacy_tls:
            verify = ssl.create_default_context()
            verify.set_ciphers("DEFAULT:@SECLEVEL=1")
        return httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            verify=verify,
        )

    def _client_for(self, host: str) -> httpx.Client:
        if self._custom_client or host not in LEGACY_TLS_HOSTS:
            return self._client
        if self._legacy_client is None:
            self._legacy_client = self._new_client(legacy_tls=True)
        return self._legacy_client

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        return self._request("GET", url, headers=headers)

    def post_json(
        self, url: str, payload: dict[str, object], headers: dict[str, str] | None = None
    ) -> str:
        return self._request("POST", url, headers=headers, json=payload)

    def _wait_for_host(self, host: str) -> None:
        delay = self._delays.get(host, 0.0)
        last = self._last.get(host)
        if delay and last is not None:
            remaining = delay - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)

    def _request(
        self, method: str, url: str, headers: dict[str, str] | None = None, **kwargs: object
    ) -> str:
        host = urlparse(url).netloc
        error: Exception | None = None
        for attempt in range(self._retries):
            self._wait_for_host(host)
            self._last[host] = self._clock()
            try:
                response = self._client_for(host).request(method, url, headers=headers, **kwargs)  # type: ignore[arg-type]
            except httpx.TransportError as exc:
                error = exc
            else:
                if response.status_code < 400:
                    return response.text
                error = FetchError(f"{method} {url} -> HTTP {response.status_code}")
                if response.status_code < 500:
                    break
            if attempt < self._retries - 1:
                self._sleep(self._backoff * (attempt + 1))
        raise FetchError(f"{method} {url} failed: {error}") from error
