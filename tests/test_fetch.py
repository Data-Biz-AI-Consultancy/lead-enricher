"""Tests for DNS resolution and HTML fetching."""

from __future__ import annotations

import httpx
import pytest

from lead_enricher.fetch import FetchError, FetchTimeout, fetch_site, resolve_dns


async def test_fetch_site_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://acme.com/"
        return httpx.Response(200, headers={"Server": "nginx"}, text="<title>Acme</title>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_site("acme.com", client=client)

    assert result.status_code == 200
    assert result.html == "<title>Acme</title>"
    assert result.headers["server"] == "nginx"
    assert "server: nginx" in result.header_block


async def test_fetch_site_timeout_raises_fetch_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchTimeout):
            await fetch_site("slow.com", client=client)


async def test_fetch_site_falls_back_to_http_on_transport_error() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.scheme)
        if request.url.scheme == "https":
            raise httpx.ConnectError("tls failed", request=request)
        return httpx.Response(200, text="<title>Legacy</title>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_site("legacy.com", client=client)

    assert calls == ["https", "http"]
    assert result.status_code == 200
    assert result.url.startswith("http://")


async def test_fetch_site_generic_http_error_raises_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.HTTPError("protocol error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchError):
            await fetch_site("weird.com", client=client)


async def test_fetch_site_all_schemes_fail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchError):
            await fetch_site("down.com", client=client)


async def test_fetch_site_non_2xx_is_returned_not_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_site("flaky.com", client=client)

    assert result.status_code == 503


async def test_fetch_site_creates_own_client_when_none_given(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
            self.closed = False

        async def get(self, url: str) -> httpx.Response:
            return httpx.Response(200, text="<title>X</title>", request=httpx.Request("GET", url))

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = await fetch_site("acme.com")
    assert result.status_code == 200


async def test_resolve_dns_returns_ips(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *a, **k: [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("93.184.216.34", 0)),
        ],
    )
    assert await resolve_dns("example.com") == ["93.184.216.34"]


async def test_resolve_dns_returns_empty_on_failure(monkeypatch) -> None:
    import socket

    def boom(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr("socket.getaddrinfo", boom)
    assert await resolve_dns("does-not-exist.invalid") == []
