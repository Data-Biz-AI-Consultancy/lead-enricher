# AGENTS.md

Persistent context for agents working in this repository.

## Standing user preferences

- **Containerization is the default for every app.** Do not ship an application
  without a `Dockerfile`. For services, also provide a `compose.yaml` and a
  `.dockerignore`. This applies to all new apps, not just this repo.
- Prefer **`uv`** for Python dependency and environment management.
- Keep git history **atomic**: one logical change per commit.

## Repository conventions

- **Layout**: `src/` layout, package `lead_enricher` under `src/`.
- **Runtime deps**: FastAPI, Pydantic v2, httpx.
- **Dev deps**: pytest, pytest-asyncio, pytest-cov, asgi-lifespan (`--extra dev`).
- **Tests**: `uv run pytest`. Coverage floor is enforced at 80% via
  `[tool.coverage.report] fail_under`; currently ~93%.
- **Lint**: `uv run ruff check .` (config in `pyproject.toml`).
- **Default branch**: `main`.

## Containerization

- `Dockerfile` is multi-stage: a `builder` stage (based on
  `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`) resolves dependencies with
  `uv sync --frozen`, then a `python:3.13-slim-bookworm` runtime stage ships only
  the virtualenv.
- The project is installed **non-editable** (`--no-editable`) in the builder so
  the runtime stage does not need the source tree. Using the default editable
  install breaks the runtime image with `ModuleNotFoundError`.
- Dependencies are copied and synced **before** the source so the dependency
  layer caches independently of source edits.
- Runs as non-root (`uid 10001`), binds `0.0.0.0:8000`, and exposes a
  `HEALTHCHECK` against `/healthz`.
- `compose.yaml` hardens further: `read_only` rootfs, `no-new-privileges`,
  `tmpfs` on `/tmp`.

## Remote

- `origin` = `https://github.com/Data-Biz-AI-Consultancy/lead-enricher.git`
  (org: Data Biz - AI Consultancy).
- Note: the CI token is a GitHub App installation token with `contents: write`
  but **no `administration` permission**, so it cannot create repositories. Repos
  must be created by a human; pushing to an existing repo works.
