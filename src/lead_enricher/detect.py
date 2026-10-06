"""Signature-based tech-stack detection from HTTP headers and HTML.

Detection is intentionally dependency-free and explainable: every match is a
simple, auditable substring/regex rule. No JS execution, no fingerprinting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lead_enricher.models import EmployeeTier


@dataclass(frozen=True)
class TechSignature:
    """A single detector: a category, a tool name, and how to spot it."""

    category: str
    tool: str
    pattern: re.Pattern[str]
    # "html" scans the response body; "header" scans the raw header block.
    where: str = "html"


def _sig(category: str, tool: str, needle: str, where: str = "html") -> TechSignature:
    return TechSignature(category, tool, re.compile(needle, re.IGNORECASE), where)


# Order is irrelevant; categories are grouped in the output. Rules are kept
# deliberately broad-but-distinct to avoid double-counting the same vendor.
SIGNATURES: tuple[TechSignature, ...] = (
    # --- analytics -------------------------------------------------------
    _sig("analytics", "Google Analytics", r"google-analytics\.com|gtag\(|G-[A-Z0-9]{8,}"),
    _sig("analytics", "Google Tag Manager", r"googletagmanager\.com|gtm\.js"),
    _sig("analytics", "Segment", r"cdn\.segment\.com|analytics\.js"),
    _sig("analytics", "Mixpanel", r"cdn\.mxpnl\.com|mixpanel"),
    _sig("analytics", "Hotjar", r"static\.hotjar\.com|hj\("),
    _sig("analytics", "Plausible", r"plausible\.io"),
    _sig("analytics", "Matomo", r"matomo\.js|piwik\.js"),
    _sig("analytics", "Amplitude", r"cdn\.amplitude\.com|amplitude"),
    # --- crm -------------------------------------------------------------
    _sig("crm", "HubSpot", r"hs-scripts\.com|hubspot|hs-analytics"),
    _sig("crm", "Salesforce", r"salesforce\.com|force\.com|pardot"),
    _sig("crm", "Intercom", r"widget\.intercom\.io|intercomsettings"),
    _sig("crm", "Drift", r"js\.driftt\.com|drift\.com"),
    # --- marketing -------------------------------------------------------
    _sig("marketing", "Marketo", r"munchkin\.js|marketo\.com"),
    _sig("marketing", "Mailchimp", r"chimpstatic\.com|mailchimp"),
    _sig("marketing", "Klaviyo", r"static\.klaviyo\.com|klaviyo"),
    _sig("marketing", "Braze", r"braze|appboy"),
    # --- support ---------------------------------------------------------
    _sig("support", "Zendesk", r"zdassets\.com|zendesk"),
    _sig("support", "Freshdesk", r"freshdesk|freshworks"),
    _sig("support", "Crisp", r"client\.crisp\.chat|crisp\.chat"),
    # --- payments --------------------------------------------------------
    _sig("payments", "Stripe", r"js\.stripe\.com|stripe\.com/v3"),
    _sig("payments", "PayPal", r"paypal\.com/sdk|paypalobjects\.com"),
    _sig("payments", "Braintree", r"braintree"),
    # --- ecommerce -------------------------------------------------------
    _sig("ecommerce", "Shopify", r"cdn\.shopify\.com|shopify\.theme"),
    _sig("ecommerce", "WooCommerce", r"woocommerce"),
    _sig("ecommerce", "Magento", r"magento|mage/cookies"),
    _sig("ecommerce", "BigCommerce", r"bigcommerce"),
    # --- framework / cms -------------------------------------------------
    _sig("framework", "React", r"react(?:-dom)?[.\-]|data-reactroot|__next"),
    _sig("framework", "Next.js", r"/_next/static|__next_data__"),
    _sig("framework", "Vue.js", r"vue(?:\.min)?\.js|data-v-"),
    _sig("framework", "Angular", r"ng-version|angular(?:\.min)?\.js"),
    _sig("framework", "WordPress", r"wp-content|wp-includes"),
    _sig("framework", "Webflow", r"webflow"),
    _sig("framework", "Squarespace", r"squarespace"),
    _sig("framework", "Drupal", r"drupal"),
    # --- hosting / infra (headers) --------------------------------------
    _sig("cloud", "Cloudflare", r"cloudflare", where="header"),
    _sig("cloud", "Amazon CloudFront", r"cloudfront", where="header"),
    _sig("cloud", "Amazon S3", r"amazons3|x-amz", where="header"),
    _sig("cloud", "Vercel", r"vercel", where="header"),
    _sig("cloud", "Netlify", r"netlify", where="header"),
    _sig("cloud", "Fastly", r"fastly", where="header"),
    _sig("cloud", "Akamai", r"akamai", where="header"),
    _sig("cloud", "Google Cloud", r"google frontend|gws|google cloud", where="header"),
    _sig("cloud", "Microsoft Azure", r"azure|microsoft-iis|windows-azure", where="header"),
    _sig("cloud", "GitHub Pages", r"github\.com|github\.io", where="header"),
    _sig("cloud", "Nginx", r"nginx", where="header"),
)

# Industry hints, checked in order; the first hit wins. Kept few and obvious.
INDUSTRY_HINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-commerce", re.compile(r"add to cart|shopify|woocommerce|checkout", re.I)),
    ("Financial Services", re.compile(r"bank|fintech|payment|invest|loan|insurance", re.I)),
    ("Healthcare", re.compile(r"health|medical|clinic|patient|pharma", re.I)),
    ("Education", re.compile(r"university|school|student|course|edtech", re.I)),
    ("Software / SaaS", re.compile(r"saas|api|platform|dashboard|pricing", re.I)),
    ("Marketing / Agency", re.compile(r"marketing|agency|seo|campaign", re.I)),
    ("Media / Publishing", re.compile(r"news|blog|magazine|publish", re.I)),
    ("Travel / Hospitality", re.compile(r"travel|hotel|booking|flight", re.I)),
    ("Real Estate", re.compile(r"real estate|property|realtor|apartment", re.I)),
    ("Non-profit", re.compile(r"nonprofit|non-profit|charity|donate", re.I)),
)

# Headcount cues found in page copy, ordered from largest to smallest so the
# most specific phrasing wins.
SIZE_HINTS: tuple[tuple[int, EmployeeTier, re.Pattern[str]], ...] = (
    (
        10000,
        EmployeeTier.GLOBAL_ENTERPRISE,
        re.compile(r"over\s+10[,.]?000\s+employees|10000\+?\s+employees", re.I),
    ),
    (
        5000,
        EmployeeTier.GLOBAL_ENTERPRISE,
        re.compile(r"5[,.]?000\+?\s+employees", re.I),
    ),
    (2500, EmployeeTier.ENTERPRISE, re.compile(r"over\s+2[,.]?500\s+employees", re.I)),
    (1000, EmployeeTier.ENTERPRISE, re.compile(r"1[,.]?000\+?\s+employees", re.I)),
    (500, EmployeeTier.LARGE, re.compile(r"500\+?\s+employees", re.I)),
    (250, EmployeeTier.LARGE, re.compile(r"250\+?\s+employees", re.I)),
    (200, EmployeeTier.MEDIUM, re.compile(r"200\+?\s+employees", re.I)),
    (100, EmployeeTier.MEDIUM, re.compile(r"100\+?\s+employees", re.I)),
    (50, EmployeeTier.SMALL, re.compile(r"50\+?\s+employees", re.I)),
    (10, EmployeeTier.MICRO, re.compile(r"10\+?\s+employees", re.I)),
    (1, EmployeeTier.SOLO, re.compile(r"sole\s+founder|indie\s+hacker|one[- ]person", re.I)),
)


def detect_tech(html: str, headers: str) -> dict[str, list[str]]:
    """Return ``{category: [tool, ...]}`` for every signature that matches.

    ``headers`` should be the raw header block rendered as text (one
    ``Name: value`` per line) so a single regex pass can cover it.
    """
    found: dict[str, set[str]] = {}
    for signature in SIGNATURES:
        haystack = headers if signature.where == "header" else html
        if signature.pattern.search(haystack):
            found.setdefault(signature.category, set()).add(signature.tool)
    return {category: sorted(tools) for category, tools in sorted(found.items())}


def infer_industry(html: str) -> str | None:
    """Return the first matching industry hint, or ``None``."""
    for label, pattern in INDUSTRY_HINTS:
        if pattern.search(html):
            return label
    return None


def infer_size(html: str) -> tuple[int | None, EmployeeTier | None]:
    """Return a ``(headcount, tier)`` pair parsed from explicit page copy."""
    for count, tier, pattern in SIZE_HINTS:
        if pattern.search(html):
            return count, tier
    return None, None


_META_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("description", re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', re.I)),
    ("og_site_name", re.compile(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', re.I)),
    ("og_title", re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', re.I)),
    ("twitter_title", re.compile(r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)', re.I)),
    ("title", re.compile(r"<title[^>]*>([^<]+)</title>", re.I)),
)


def extract_metadata(html: str) -> dict[str, str]:
    """Pull title/description/og tags out of raw HTML into a flat dict."""
    meta: dict[str, str] = {}
    for key, pattern in _META_PATTERNS:
        match = pattern.search(html)
        if match:
            value = " ".join(match.group(1).split())
            if value:
                meta[key] = value
    return meta


_BRAND_SUFFIXES = re.compile(
    r"\s*[\|\-–—:·]\s*(home|official site|welcome|the .* company)\s*$", re.I
)


def company_name_from_metadata(meta: dict[str, str], fallback_stem: str) -> str:
    """Derive a readable company name, preferring structured OG data."""
    candidate = meta.get("og_site_name") or meta.get("og_title") or meta.get("title") or ""
    # A common pattern is "Brand | Tagline" or "Tagline - Brand"; take the head.
    if candidate:
        candidate = re.split(r"\s[\|\-–—:·]\s", candidate, maxsplit=1)[0]
        candidate = _BRAND_SUFFIXES.sub("", candidate).strip()
    if candidate and 1 < len(candidate) <= 80:
        return candidate
    return fallback_stem.capitalize()
