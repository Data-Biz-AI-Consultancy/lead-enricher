"""Deterministic mock enrichment used when live evidence is unavailable.

The service must never fail a caller just because a site is down, blocking
bots, or absent from DNS. When live fetching yields nothing usable we synthesize
a *plausible* payload seeded from the domain itself, so results are stable
across runs and reproducible in tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from lead_enricher.domain import registrable_stem
from lead_enricher.models import EmployeeTier

_INDUSTRIES = (
    "Software / SaaS",
    "E-commerce",
    "Financial Services",
    "Healthcare",
    "Marketing / Agency",
    "Media / Publishing",
    "Education",
    "Professional Services",
)

_TECH_CATALOG: dict[str, tuple[str, ...]] = {
    "analytics": ("Google Analytics", "Google Tag Manager", "Segment", "Mixpanel", "Plausible"),
    "crm": ("HubSpot", "Salesforce", "Intercom", "Pipedrive"),
    "marketing": ("Mailchimp", "Klaviyo", "Marketo", "Braze"),
    "payments": ("Stripe", "PayPal", "Braintree", "Adyen"),
    "cloud": ("Amazon Web Services", "Cloudflare", "Vercel", "Google Cloud"),
    "framework": ("React", "Next.js", "Vue.js", "WordPress"),
}

_TIERS: tuple[tuple[EmployeeTier, int], ...] = (
    (EmployeeTier.SOLO, 1),
    (EmployeeTier.MICRO, 8),
    (EmployeeTier.SMALL, 35),
    (EmployeeTier.MEDIUM, 120),
    (EmployeeTier.LARGE, 450),
    (EmployeeTier.ENTERPRISE, 2500),
    (EmployeeTier.GLOBAL_ENTERPRISE, 9000),
)


@dataclass
class MockProfile:
    """A synthesized enrichment profile."""

    company_name: str
    industry: str
    employee_tier: EmployeeTier
    estimated_employees: int
    tech_stack: dict[str, list[str]]


def _seed(domain: str) -> int:
    """Stable integer seed derived from the domain (not Python's salted hash)."""
    digest = hashlib.sha256(domain.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _pick_tools(seed: int, tools: tuple[str, ...], count: int) -> list[str]:
    """Pick ``count`` distinct tools, rotating the window so we never loop."""
    start = seed % len(tools)
    chosen = [tools[(start + i) % len(tools)] for i in range(count)]
    return sorted(chosen)


def build_mock_profile(domain: str) -> MockProfile:
    """Build a deterministic mock profile for ``domain``."""
    seed = _seed(domain)
    stem = registrable_stem(domain)

    industry = _INDUSTRIES[seed % len(_INDUSTRIES)]
    tier, headcount = _TIERS[(seed >> 8) % len(_TIERS)]

    tech_stack: dict[str, list[str]] = {}
    for offset, (category, tools) in enumerate(_TECH_CATALOG.items()):
        # Always include one tool per category; sometimes a second.
        count = 1 + ((seed >> (12 + offset)) & 1)
        tech_stack[category] = _pick_tools(seed >> (16 + offset), tools, count)

    return MockProfile(
        company_name=stem.replace("-", " ").title(),
        industry=industry,
        employee_tier=tier,
        estimated_employees=headcount,
        tech_stack=tech_stack,
    )
