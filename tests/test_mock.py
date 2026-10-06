"""Tests for the deterministic mock profile generator."""

from __future__ import annotations

from lead_enricher.models import EmployeeTier
from lead_enricher.mock import build_mock_profile


def test_mock_profile_is_deterministic() -> None:
    first = build_mock_profile("acme.com")
    second = build_mock_profile("acme.com")
    assert first == second


def test_mock_profile_varies_by_domain() -> None:
    signatures = {
        (
            build_mock_profile(f"site{i}.com").industry,
            build_mock_profile(f"site{i}.com").employee_tier,
        )
        for i in range(20)
    }
    # Not a strict guarantee for every pair, but the seed space is large.
    assert len(signatures) > 1


def test_mock_profile_shape() -> None:
    profile = build_mock_profile("my-startup.io")
    assert profile.company_name == "My Startup"
    assert profile.industry
    assert isinstance(profile.employee_tier, EmployeeTier)
    assert profile.estimated_employees >= 1
    assert set(profile.tech_stack) == {
        "analytics",
        "crm",
        "marketing",
        "payments",
        "cloud",
        "framework",
    }
    for tools in profile.tech_stack.values():
        assert 1 <= len(tools) <= 2
        assert tools == sorted(tools)
