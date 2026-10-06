"""FastAPI application exposing the enrichment endpoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from lead_enricher import __version__
from lead_enricher.enricher import EnrichmentError, LeadEnricher
from lead_enricher.fetch import USER_AGENT
from lead_enricher.models import EnrichRequest, EnrichResponse

logger = logging.getLogger("lead_enricher")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own a single pooled HTTP client for the app's lifetime."""
    client = httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
    )
    app.state.client = client
    app.state.enricher = LeadEnricher(client=client)
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(
    title="lead-enricher",
    version=__version__,
    summary="Turn a company domain into structured firmographic and tech-stack signals.",
    lifespan=lifespan,
)


@app.exception_handler(EnrichmentError)
async def _enrichment_error_handler(request: Request, exc: EnrichmentError) -> JSONResponse:
    """Surface upstream failures as 502 when mock fallback is disabled."""
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def get_enricher(request: Request) -> LeadEnricher:
    """FastAPI dependency returning the shared enricher instance."""
    return request.app.state.enricher


@app.get("/healthz", tags=["ops"], summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/enrich", response_model=EnrichResponse, tags=["enrichment"])
async def enrich_post(
    payload: EnrichRequest,
    enricher: LeadEnricher = Depends(get_enricher),
) -> EnrichResponse:
    """Enrich a company domain supplied as a JSON body."""
    return await enricher.enrich(payload.domain)


@app.get("/enrich", response_model=EnrichResponse, tags=["enrichment"])
async def enrich_get(
    domain: str = Query(
        ...,
        min_length=1,
        max_length=253,
        description="Company domain or URL, e.g. 'stripe.com'.",
        examples=["stripe.com"],
    ),
    enricher: LeadEnricher = Depends(get_enricher),
) -> EnrichResponse:
    """Enrich a company domain supplied as a query parameter."""
    try:
        payload = EnrichRequest(domain=domain)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False, include_input=False),
        ) from exc
    return await enricher.enrich(payload.domain)
