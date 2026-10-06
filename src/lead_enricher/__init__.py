"""lead-enricher: turn a company domain into structured enrichment signals."""

from lead_enricher.enricher import LeadEnricher
from lead_enricher.models import EmployeeTier, EnrichRequest, EnrichResponse

__all__ = ["LeadEnricher", "EnrichRequest", "EnrichResponse", "EmployeeTier"]

__version__ = "0.1.0"
