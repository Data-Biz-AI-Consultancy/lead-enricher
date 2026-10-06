"""Network primitives: DNS resolution and HTML fetching.

Everything here is best-effort and raises :class:`FetchError` (or the
``TimeoutError`` subclass) rather than leaking httpx/socket exceptions into the
enrichment layer. That keeps the fallback decision in one place.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass, field

import httpx

DEFAULT_TIMEOUT = 5.0
MAX_BODY_BYTES = 512 * 1024  # cap what we read; we only need <head> metadata
USER_AGENT = "lead-enricher/0.1 (+https://example.com/bot)"


class FetchError(Exception):
    """A domain could not be resolved or fetched."""


class FetchTimeout(FetchError):
    """The fetch exceeded the configured timeout."""


@dataclass
class FetchResult:
    """Raw evidence gathered from a live fetch."""

    domain: str
    url: str
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    html: str = ""
    resolved_ips: list[str] = field(default_factory=list)

    @property
    def header_block(self) -> str:
        """Headers rendered as a single text block for regex scanning."""
        return "\n".join(f"{k}: {v}" for k, v in self.headers.items())


async def resolve_dns(domain: str) -> list[str]:
    """Resolve ``domain`` to a list of IP strings via the system resolver.

    Returns an empty list when resolution fails -- callers treat "no DNS" as a
    signal to fall back rather than a hard error.
    """

    def _resolve() -> list[str]:
        infos = socket.getaddrinfo(domain, None)
        return sorted({info[4][0] for info in infos})

    try:
        return await asyncio.wait_for(asyncio.to_thread(_resolve), timeout=DEFAULT_TIMEOUT)
    except (socket.gaierror, OSError, asyncio.TimeoutError):
        return []


async def fetch_site(
    domain: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> FetchResult:
    """Fetch ``https://<domain>/`` and return its status, headers, and HTML.

    Tries HTTPS first and falls back to HTTP only when the TLS attempt fails at
    the connection layer (some legacy sites still lack certificates).

    Raises:
        FetchTimeout: on a request timeout.
        FetchError: on any other transport/HTTP error.
    """
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        )

    try:
        last_error: Exception | None = None
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}/"
            try:
                response = await client.get(url)
            except httpx.TimeoutException as exc:
                raise FetchTimeout(f"timed out fetching {domain}") from exc
            except httpx.TransportError as exc:
                last_error = exc
                continue  # try the next scheme
            except httpx.HTTPError as exc:
                raise FetchError(f"failed to fetch {domain}: {exc}") from exc

            html = response.text[:MAX_BODY_BYTES]
            return FetchResult(
                domain=domain,
                url=str(response.url),
                status_code=response.status_code,
                headers={k.lower(): v for k, v in response.headers.items()},
                html=html,
            )
        raise FetchError(f"failed to fetch {domain}: {last_error}")
    finally:
        if owns_client:
            await client.aclose()
