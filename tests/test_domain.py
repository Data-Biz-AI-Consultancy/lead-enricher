"""Tests for input normalization and validation."""

from __future__ import annotations

import pytest

from lead_enricher.domain import InvalidDomainError, normalize_domain, registrable_stem


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("stripe.com", "stripe.com"),
        ("Stripe.com", "stripe.com"),
        ("  stripe.com  ", "stripe.com"),
        ("www.stripe.com", "stripe.com"),
        ("WWW.STRIPE.COM", "stripe.com"),
        ("https://stripe.com", "stripe.com"),
        ("http://stripe.com/pricing?utm=1#x", "stripe.com"),
        ("https://www.stripe.com/pricing", "stripe.com"),
        ("https://user:pass@stripe.com:8443/a/b", "stripe.com"),
        ("foo.bar.co.uk", "foo.bar.co.uk"),
        ("stripe.com.", "stripe.com"),
        ("my-startup.io", "my-startup.io"),
    ],
)
def test_normalize_domain_accepts_and_canonicalizes(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        None,
        "localhost",
        "http://localhost",
        "192.168.1.1",
        "https://10.0.0.1/admin",
        "[::1]",
        "not_a_domain.com",
        "-bad.com",
        "bad-.com",
        "no-tld",
        "spaces in name.com",
        "http://",
    ],
)
def test_normalize_domain_rejects_invalid(raw: str | None) -> None:
    with pytest.raises(InvalidDomainError):
        normalize_domain(raw)


def test_registrable_stem() -> None:
    assert registrable_stem("stripe.com") == "stripe"
    assert registrable_stem("foo.bar.co.uk") == "foo"
