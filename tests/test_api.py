"""End-to-end tests for the FastAPI app via ASGI transport."""

from __future__ import annotations

import httpx
import pytest
from asgi_lifespan import LifespanManager

from lead_enricher.app import app
from tests.conftest import make_client


@pytest.fixture
async def api_client():
    """App client whose enricher uses a mocked transport and fake DNS."""

    async def _dns_ok(domain: str) -> list[str]:
        return ["93.184.216.34"]

    mock_client = make_client()

    async with LifespanManager(app) as manager:
        # Swap the pooled client for our mock-backed enricher on the real app.
        from lead_enricher.enricher import LeadEnricher

        app.state.enricher = LeadEnricher(client=mock_client, dns_resolver=_dns_ok)
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    await mock_client.aclose()


async def test_healthz(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_enrich_post_success(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.post("/enrich", json={"domain": "acme.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["domain"] == "acme.com"
    assert body["source"] == "live"
    assert 0.0 <= body["confidence"] <= 1.0
    assert "tech_stack" in body


async def test_enrich_get_success(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/enrich", params={"domain": "https://www.acme.com/x"})
    assert resp.status_code == 200
    assert resp.json()["domain"] == "acme.com"


async def test_enrich_post_invalid_domain(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.post("/enrich", json={"domain": "not a domain"})
    assert resp.status_code == 422
    assert resp.json()["detail"]


async def test_enrich_post_missing_domain(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.post("/enrich", json={})
    assert resp.status_code == 422


async def test_enrich_post_extra_field_rejected(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.post("/enrich", json={"domain": "acme.com", "extra": 1})
    assert resp.status_code == 422


async def test_enrich_get_invalid_domain(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/enrich", params={"domain": "192.168.0.1"})
    assert resp.status_code == 422


async def test_enrich_get_missing_domain(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/enrich")
    assert resp.status_code == 422


async def test_lifespan_creates_and_closes_client() -> None:
    """The app owns a pooled client that exists during its lifespan."""
    async with LifespanManager(app):
        assert hasattr(app.state, "client")
        assert hasattr(app.state, "enricher")


async def test_enrich_returns_502_when_mock_disabled() -> None:
    """With mock fallback off, an unreachable host surfaces as 502."""
    from lead_enricher.enricher import LeadEnricher

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    async def _dns_fail(domain: str) -> list[str]:
        return []

    async with LifespanManager(app) as manager:
        failing = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        app.state.enricher = LeadEnricher(
            client=failing, allow_mock=False, dns_resolver=_dns_fail
        )
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/enrich", json={"domain": "down.com"})
        await failing.aclose()

    assert resp.status_code == 502
    assert "down.com" in resp.json()["detail"]
