"""Tests for the enrichment pipeline, including fallback behaviour."""

from __future__ import annotations

import httpx
import pytest

from lead_enricher.enricher import EnrichmentError, LeadEnricher
from lead_enricher.fetch import FetchError
from lead_enricher.models import EmployeeTier, SourceKind

from tests.conftest import SAMPLE_HTML, make_client


async def _dns_ok(domain: str) -> list[str]:
    return ["93.184.216.34"]


async def _dns_fail(domain: str) -> list[str]:
    return []


async def test_successful_live_enrichment() -> None:
    async with make_client() as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_ok)
        result = await enricher.enrich("acme.com")

    assert result.source is SourceKind.LIVE
    assert result.domain == "acme.com"
    assert result.company_name == "Acme Robotics"
    assert result.industry == "Software / SaaS"
    assert result.employee_tier is EmployeeTier.LARGE
    assert result.estimated_employees == 500
    assert "Stripe" in result.tech_stack["payments"]
    assert result.confidence > 0.5
    assert "live HTML fetched" in result.signals


async def test_timeout_falls_back_to_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_ok)
        result = await enricher.enrich("slow.com")

    assert result.source is SourceKind.MOCK
    assert result.confidence <= 0.5
    assert any("timed out" in s for s in result.signals)


async def test_connection_error_falls_back_to_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_fail)
        result = await enricher.enrich("down.com")

    assert result.source is SourceKind.MOCK
    assert "DNS did not resolve" in result.signals


async def test_empty_page_falls_back_to_mock() -> None:
    async with make_client(html="", headers={}) as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_ok)
        result = await enricher.enrich("blank.com")

    assert result.source is SourceKind.MOCK
    assert any("no usable signals" in s for s in result.signals)


async def test_mock_disabled_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enricher = LeadEnricher(client=client, allow_mock=False, dns_resolver=_dns_fail)
        with pytest.raises(EnrichmentError):
            await enricher.enrich("down.com")


async def test_non_2xx_still_returns_live_payload() -> None:
    async with make_client(status_code=404) as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_ok)
        result = await enricher.enrich("acme.com")

    assert result.source is SourceKind.LIVE
    assert any("non-2xx" in s for s in result.signals)


async def test_tier_estimated_from_tech_when_page_silent() -> None:
    html = (
        "<html><head><title>BigCo</title></head><body>"
        '<script src="https://js.stripe.com/v3/"></script>'
        '<script src="https://www.googletagmanager.com/gtm.js"></script>'
        "munchkin.js braze appboy pardot"  # Marketo, Braze, Salesforce signatures
        "</body></html>"
    )
    headers = {"server": "cloudflare", "x-powered-by": "Next.js"}
    async with make_client(html=html, headers=headers) as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_ok)
        result = await enricher.enrich("bigco.com")

    # No explicit headcount -> inferred from detected enterprise tooling.
    assert result.employee_tier is EmployeeTier.LARGE
    assert result.estimated_employees == 450


async def test_tier_defaults_to_small_without_enterprise_tools() -> None:
    html = (
        "<html><head><title>SmallCo</title></head><body>"
        '<script src="https://cdn.segment.com/analytics.js"></script>'
        "</body></html>"
    )
    async with make_client(html=html, headers={}) as client:
        enricher = LeadEnricher(client=client, dns_resolver=_dns_ok)
        result = await enricher.enrich("smallco.com")

    assert result.employee_tier is EmployeeTier.SMALL
    assert result.estimated_employees == 35


async def test_enricher_without_client_uses_fetch_default(monkeypatch) -> None:
    async def fake_fetch_site(domain, *, client=None, timeout=5.0):
        from lead_enricher.fetch import FetchResult

        return FetchResult(
            domain=domain,
            url=f"https://{domain}/",
            status_code=200,
            headers={"server": "nginx"},
            html=SAMPLE_HTML,
        )

    monkeypatch.setattr("lead_enricher.enricher.fetch_site", fake_fetch_site)
    enricher = LeadEnricher(dns_resolver=_dns_ok)
    result = await enricher.enrich("acme.com")
    assert result.source is SourceKind.LIVE


def test_fetch_error_is_subclass_of_exception() -> None:
    assert issubclass(FetchError, Exception)
