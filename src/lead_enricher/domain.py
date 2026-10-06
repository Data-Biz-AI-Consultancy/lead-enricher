"""Domain normalization and validation.

The enricher accepts whatever an operator pastes in -- a bare host, a full URL,
or a host with a ``www.`` prefix -- and reduces it to a canonical registrable
host before any network work happens.
"""

from __future__ import annotations

import ipaddress
import re

# A pragmatic hostname pattern: labels of alphanumerics/hyphens separated by
# dots, ending in a 2+ character alphabetic TLD. Deliberately rejects
# underscores, trailing dots, and single-label hosts such as ``localhost``.
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST_RE = re.compile(rf"^(?:{_LABEL}\.)+[a-z]{{2,63}}$")

# Anything before the first slash that looks like a scheme is dropped.
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)


class InvalidDomainError(ValueError):
    """Raised when an input cannot be reduced to a usable domain name."""


def normalize_domain(raw: str) -> str:
    """Reduce an operator-supplied string to a canonical ``host`` form.

    ``"https://WWW.Stripe.com/pricing?utm=1"`` becomes ``"stripe.com"``.

    Raises:
        InvalidDomainError: if the input is empty, is an IP address, or does not
            look like a public domain name.
    """
    if raw is None:
        raise InvalidDomainError("domain is required")

    value = raw.strip().lower()
    if not value:
        raise InvalidDomainError("domain must not be empty")

    # Drop scheme, then everything from the first path/query/fragment char.
    value = _SCHEME_RE.sub("", value)
    value = re.split(r"[/?#]", value, maxsplit=1)[0]

    # Drop userinfo and port.
    value = value.rsplit("@", 1)[-1]
    if value.startswith("["):  # bracketed IPv6 literal
        raise InvalidDomainError("IP addresses are not supported")
    value = value.split(":", 1)[0]

    # Strip a single leading www.
    if value.startswith("www."):
        value = value[4:]

    value = value.rstrip(".")

    if not value:
        raise InvalidDomainError("domain must not be empty")

    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise InvalidDomainError("IP addresses are not supported")

    if not _HOST_RE.match(value):
        raise InvalidDomainError(f"{raw!r} is not a valid domain name")

    return value


def registrable_stem(domain: str) -> str:
    """Return the brand-ish stem of a domain, e.g. ``stripe`` for ``stripe.com``."""
    return domain.split(".", 1)[0]
