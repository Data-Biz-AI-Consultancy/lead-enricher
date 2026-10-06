"""The enrichment pipeline: resolve -> fetch -> detect -> score -> fall back."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import httpx

from lead_enricher import detect
from lead_enricher.domain import registrable_stem
from lead_enricher.fetch import DEFAULT_TIMEOUT, FetchError, FetchResult, fetch_site, resolve_dns
from lead_enricher.mock import build_mock_profile
from lead_enricher.models import EmployeeTier, EnrichResponse, SourceKind

logger = logging.getLogger(__name__)

# Tools whose presence implies a larger, more mature organization. Used only to
# *guess* a tier when the page never states headcount.
_ENTERPRISE_TOOLS = frozenset(
    {
        "Salesforce",
        "Marketo",
        "Braze",
        "Amazon Web Services",
        "Microsoft Azure",
        "Google Cloud",
        "Adobe",
    }
)

DnsResolver = Callable[[str], Awaitable[list[str]]]


class EnrichmentError(Exception):
    """Raised when enrichment cannot produce any payload and mock is disabled."""


def _score_live(result: FetchResult, tech_stack: dict, industry: str | None) -> tuple[float, list[str]]:
    """Compute a confidence score and evidence trail for a live fetch."""
    signals: list[str] = []
    score = 0.35
    signals.append("live HTML fetched")

    if 200 <= result.status_code < 300:
        score += 0.15
        signals.append(f"HTTP {result.status_code}")
    else:
        signals.append(f"non-2xx response (HTTP {result.status_code})")

    meta = detect.extract_metadata(result.html)
    if meta.get("og_site_name"):
        score += 0.10
        signals.append("og:site_name present")
    elif meta.get("title"):
        score += 0.05
        signals.append("HTML <title> present")

    if industry:
        score += 0.10
        signals.append(f"industry hint: {industry}")

    _, tier = detect.infer_size(result.html)
    if tier is not None:
        score += 0.15
        signals.append("explicit headcount on page")

    if tech_stack:
        score += 0.10
        signals.append(f"{sum(len(v) for v in tech_stack.values())} tech signatures matched")

    if result.resolved_ips:
        score += 0.05
        signals.append("DNS resolved")

    return min(score, 0.97), signals


def _estimate_tier_from_tech(tech_stack: dict) -> tuple[int, EmployeeTier]:
    """Guess a headcount band from tooling when the page states nothing."""
    tools = {tool for group in tech_stack.values() for tool in group}
    enterprise_hits = len(tools & _ENTERPRISE_TOOLS)
    if enterprise_hits >= 3:
        return 450, EmployeeTier.LARGE
    if enterprise_hits >= 1:
        return 120, EmployeeTier.MEDIUM
    return 35, EmployeeTier.SMALL


class LeadEnricher:
    """Async, injectable enrichment service.

    Args:
        client: Optional shared ``httpx.AsyncClient`` (owned by the caller).
        timeout: Per-request timeout in seconds.
        allow_mock: When ``True`` (default) a fallback payload is always
            returned. When ``False`` an unrecoverable fetch raises
            :class:`EnrichmentError` instead.
        dns_resolver: Injectable DNS resolver, primarily for tests.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        allow_mock: bool = True,
        dns_resolver: DnsResolver = resolve_dns,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._allow_mock = allow_mock
        self._dns = dns_resolver

    async def enrich(self, domain: str) -> EnrichResponse:
        """Enrich a single canonical domain. Never raises unless mock is off."""
        ips = await self._dns(domain)

        try:
            result = await fetch_site(domain, client=self._client, timeout=self._timeout)
        except FetchError as exc:
            logger.info("live fetch failed for %s: %s", domain, exc)
            return self._fallback(domain, ips, reason=str(exc))

        result.resolved_ips = ips
        tech_stack = detect.detect_tech(result.html, result.header_block)
        industry = detect.infer_industry(result.html)

        meta = detect.extract_metadata(result.html)
        company_name = detect.company_name_from_metadata(meta, registrable_stem(domain))

        headcount, tier = detect.infer_size(result.html)
        if tier is None:
            headcount, tier = _estimate_tier_from_tech(tech_stack)

        score, signals = _score_live(result, tech_stack, industry)

        # If the page yielded essentially nothing, a live answer would be
        # misleading -- fall back to the deterministic mock instead.
        if not tech_stack and industry is None and not meta:
            return self._fallback(domain, ips, reason="live page yielded no usable signals")

        return EnrichResponse(
            domain=domain,
            company_name=company_name,
            industry=industry or build_mock_profile(domain).industry,
            employee_tier=tier,
            estimated_employees=headcount,
            tech_stack=tech_stack,
            confidence=round(score, 2),
            source=SourceKind.LIVE,
            signals=signals,
        )

    def _fallback(self, domain: str, ips: list[str], *, reason: str) -> EnrichResponse:
        if not self._allow_mock:
            raise EnrichmentError(f"enrichment failed for {domain}: {reason}")

        profile = build_mock_profile(domain)
        signals = [f"fallback: {reason}"]
        score = 0.20
        if ips:
            score += 0.10
            signals.append("DNS resolved (host exists)")
        else:
            signals.append("DNS did not resolve")
        signals.append("firmographics synthesized (mock)")

        return EnrichResponse(
            domain=domain,
            company_name=profile.company_name,
            industry=profile.industry,
            employee_tier=profile.employee_tier,
            estimated_employees=profile.estimated_employees,
            tech_stack=profile.tech_stack,
            confidence=round(min(score, 0.5), 2),
            source=SourceKind.MOCK,
            signals=signals,
        )
