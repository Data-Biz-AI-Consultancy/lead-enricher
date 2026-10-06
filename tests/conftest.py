"""Shared fixtures for the lead-enricher test suite."""

from __future__ import annotations

import httpx
import pytest

from lead_enricher.enricher import LeadEnricher

# A realistic homepage: OG metadata, an explicit headcount, and several
# detectable tech signatures spread across HTML and headers.
SAMPLE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>Acme Robotics | Industrial automation platform</title>
  <meta name="description" content="Acme builds robots for warehouses." />
  <meta property="og:site_name" content="Acme Robotics" />
  <meta property="og:title" content="Acme Robotics" />
  <script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABC123"></script>
  <script src="https://js.stripe.com/v3/"></script>
  <script src="https://cdn.segment.com/analytics.js"></script>
</head>
<body>
  <h1>Trusted by 500+ employees worldwide</h1>
  <div class="hs-scripts">HubSpot</div>
</body>
</html>
"""

SAMPLE_HEADERS = {
    "content-type": "text/html; charset=utf-8",
    "server": "cloudflare",
    "x-powered-by": "Next.js",
}


def make_client(
    *,
    html: str = SAMPLE_HTML,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Build an httpx client backed by a MockTransport returning fixed data."""
    response_headers = headers if headers is not None else SAMPLE_HEADERS

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers=response_headers, text=html)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def sample_html() -> str:
    return SAMPLE_HTML


@pytest.fixture
async def mock_client() -> httpx.AsyncClient:
    client = make_client()
    try:
        yield client
    finally:
        await client.aclose()


async def _fake_dns(domain: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def enricher(mock_client: httpx.AsyncClient) -> LeadEnricher:
    return LeadEnricher(client=mock_client, dns_resolver=_fake_dns)
