"""Tests for signature-based detection helpers."""

from __future__ import annotations

from lead_enricher.detect import (
    company_name_from_metadata,
    detect_tech,
    extract_metadata,
    infer_industry,
    infer_size,
)
from lead_enricher.models import EmployeeTier

from tests.conftest import SAMPLE_HTML


def test_detect_tech_from_html_and_headers() -> None:
    stack = detect_tech(SAMPLE_HTML, "server: cloudflare\nx-powered-by: Next.js")
    assert "Google Tag Manager" in stack["analytics"]
    assert "Segment" in stack["analytics"]
    assert "Stripe" in stack["payments"]
    assert "HubSpot" in stack["crm"]
    assert "Cloudflare" in stack["cloud"]
    # Categories are returned sorted for stable output.
    assert list(stack) == sorted(stack)


def test_detect_tech_empty_when_nothing_matches() -> None:
    assert detect_tech("<html><body>plain</body></html>", "server: foo") == {}


def test_detect_tech_header_signatures_ignore_body() -> None:
    # "cloudflare" appears only in the body, not headers -> not detected.
    stack = detect_tech("<html>cloudflare</html>", "")
    assert "cloud" not in stack


def test_infer_industry_prefers_first_hint() -> None:
    assert infer_industry(SAMPLE_HTML) == "Software / SaaS"
    assert infer_industry("<html>add to cart</html>") == "E-commerce"
    assert infer_industry("<html>nothing here</html>") is None


def test_infer_size_explicit_headcount() -> None:
    count, tier = infer_size(SAMPLE_HTML)
    assert count == 500
    assert tier is EmployeeTier.LARGE


def test_infer_size_none_when_absent() -> None:
    assert infer_size("<html>hello</html>") == (None, None)


def test_extract_metadata() -> None:
    meta = extract_metadata(SAMPLE_HTML)
    assert meta["og_site_name"] == "Acme Robotics"
    assert meta["description"] == "Acme builds robots for warehouses."
    assert "Acme Robotics" in meta["title"]


def test_company_name_prefers_og_site_name() -> None:
    meta = {"og_site_name": "Acme Robotics", "title": "Whatever | Tagline"}
    assert company_name_from_metadata(meta, "acme") == "Acme Robotics"


def test_company_name_strips_tagline_from_title() -> None:
    meta = {"title": "Acme Robotics | Industrial automation platform"}
    assert company_name_from_metadata(meta, "acme") == "Acme Robotics"


def test_company_name_falls_back_to_stem() -> None:
    assert company_name_from_metadata({}, "acme") == "Acme"
    assert company_name_from_metadata({"title": "x" * 200}, "acme") == "Acme"
