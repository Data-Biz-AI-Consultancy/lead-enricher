"""Pydantic v2 request/response contracts for the enrichment service."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lead_enricher.domain import InvalidDomainError, normalize_domain


class EmployeeTier(str, Enum):
    """Coarse headcount band, the unit sales teams actually segment on."""

    SOLO = "solo"  # 1
    MICRO = "micro"  # 2-10
    SMALL = "small"  # 11-50
    MEDIUM = "medium"  # 51-200
    LARGE = "large"  # 201-1000
    ENTERPRISE = "enterprise"  # 1001-5000
    GLOBAL_ENTERPRISE = "global_enterprise"  # 5000+

    @classmethod
    def from_count(cls, count: int) -> "EmployeeTier":
        if count <= 1:
            return cls.SOLO
        if count <= 10:
            return cls.MICRO
        if count <= 50:
            return cls.SMALL
        if count <= 200:
            return cls.MEDIUM
        if count <= 1000:
            return cls.LARGE
        if count <= 5000:
            return cls.ENTERPRISE
        return cls.GLOBAL_ENTERPRISE


class SourceKind(str, Enum):
    """Where a payload's evidence ultimately came from."""

    LIVE = "live"
    MOCK = "mock"


class EnrichRequest(BaseModel):
    """Input for ``POST /enrich`` and ``GET /enrich``."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(
        ...,
        min_length=1,
        max_length=253,
        description="Company domain or URL, e.g. 'stripe.com' or 'https://www.stripe.com'.",
        examples=["stripe.com"],
    )

    @field_validator("domain")
    @classmethod
    def _validate_domain(cls, value: str) -> str:
        try:
            return normalize_domain(value)
        except InvalidDomainError as exc:
            raise ValueError(str(exc)) from exc


class EnrichResponse(BaseModel):
    """Structured enrichment payload returned to callers."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(..., description="Canonical domain that was enriched.")
    company_name: str = Field(..., description="Best-effort company/brand name.")
    industry: str = Field(..., description="Industry hint inferred from page content.")
    employee_tier: EmployeeTier = Field(..., description="Coarse headcount band.")
    estimated_employees: int | None = Field(
        None, description="Point estimate when available, otherwise null."
    )
    tech_stack: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Detected tools grouped by category (analytics, crm, cloud, ...).",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Enrichment confidence score in [0, 1]."
    )
    source: SourceKind = Field(..., description="Whether evidence was live or mocked.")
    signals: list[str] = Field(
        default_factory=list,
        description="Human-readable evidence trail behind the score.",
    )
