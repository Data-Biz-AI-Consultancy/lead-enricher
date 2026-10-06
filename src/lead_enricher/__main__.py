"""Console entry point: ``lead-enricher`` or ``python -m lead_enricher``."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "lead_enricher.app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("RELOAD")),
    )


if __name__ == "__main__":
    main()
