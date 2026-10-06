# lead-enricher

A lightweight, production-ready lead enrichment micro-service. Give it a company
domain, get back a structured JSON payload with the company name, an industry
hint, an employee tier, detected tech-stack signals, and a confidence score.

Built with **FastAPI**, **Pydantic v2**, and **httpx**, managed with **uv**.

---

## Quickstart

Spin it up locally (uv creates the environment and runs uvicorn in one shot):

```bash
uv run uvicorn lead_enricher.app:app --reload
```

The API is then live at `http://127.0.0.1:8000`. Interactive docs are at
`http://127.0.0.1:8000/docs`.

Prefer the packaged entry point? Both of these do the same thing:

```bash
uv run lead-enricher          # console script
uv run python -m lead_enricher # module form
```

## Try it immediately

```bash
curl -s -X POST http://127.0.0.1:8000/enrich \
  -H 'Content-Type: application/json' \
  -d '{"domain": "stripe.com"}' | python -m json.tool
```

A `GET` form is available too:

```bash
curl -s "http://127.0.0.1:8000/enrich?domain=stripe.com" | python -m json.tool
```

### Example response

Field values depend on what the target site actually exposes, so treat this as a
shape reference rather than a fixed answer:

```json
{
  "domain": "stripe.com",
  "company_name": "Stripe",
  "industry": "Financial Services",
  "employee_tier": "medium",
  "estimated_employees": 120,
  "tech_stack": {
    "analytics": ["Google Analytics"],
    "cloud": ["Cloudflare"],
    "framework": ["React"],
    "payments": ["Stripe"]
  },
  "confidence": 0.8,
  "source": "live",
  "signals": [
    "live HTML fetched",
    "HTTP 200",
    "HTML <title> present",
    "industry hint: Financial Services",
    "4 tech signatures matched",
    "DNS resolved"
  ]
}
```

When the site is unreachable or blocks bots you'll instead get a deterministic
mock profile with `"source": "mock"` and a confidence capped at `0.5`.

## How it works

The pipeline is deliberately simple and explainable:

1. **Normalize** the input — `https://WWW.Stripe.com/pricing` becomes `stripe.com`.
   IP addresses, empty strings, and single-label hosts are rejected with `422`.
2. **Resolve DNS** (best-effort) to confirm the host exists.
3. **Fetch** the homepage over HTTPS, falling back to HTTP only if the TLS
   connection itself fails. The body is capped at 512 KB — only `<head>`
   metadata matters.
4. **Detect** tech-stack signatures from HTTP headers and HTML, infer an
   industry hint, and parse an explicit headcount if the page states one.
5. **Score** confidence in `[0, 1]` from the evidence collected.
6. **Fall back** to a deterministic, domain-seeded mock profile when the site is
   unreachable, blocks bots, or yields no usable signals. Callers always get a
   well-formed payload.

`source` tells you which path produced the result:

- `"live"` — real evidence was fetched and parsed.
- `"mock"` — synthesized fallback (confidence is capped at `0.5`).

The mock is deterministic: the same domain always yields the same profile, so
results are reproducible in tests and demos.

## API

| Method | Path       | Input                                | Notes                          |
| ------ | ---------- | ------------------------------------ | ------------------------------ |
| `POST` | `/enrich`  | JSON body `{"domain": "stripe.com"}` | Primary endpoint               |
| `GET`  | `/enrich`  | `?domain=stripe.com`                 | Convenience for quick checks   |
| `GET`  | `/healthz` | —                                    | Liveness probe                 |

**Response fields**

| Field                 | Type                    | Description                                     |
| --------------------- | ----------------------- | ----------------------------------------------- |
| `domain`              | `string`                | Canonical domain that was enriched              |
| `company_name`        | `string`                | Best-effort company/brand name                  |
| `industry`            | `string`                | Industry hint inferred from page content        |
| `employee_tier`       | `enum`                  | `solo` … `global_enterprise`                    |
| `estimated_employees` | `int \| null`           | Point estimate when available                   |
| `tech_stack`          | `object`                | Detected tools grouped by category              |
| `confidence`          | `float` (0–1)           | Enrichment confidence score                     |
| `source`              | `enum` (`live`/`mock`)  | Whether evidence was live or synthesized        |
| `signals`             | `array[string]`         | Human-readable evidence trail behind the score  |

## Docker

Containerization is the default way to run this service.

```bash
# Build and run with Compose (recommended)
docker compose up --build

# ...or plain Docker
docker build -t lead-enricher .
docker run --rm -p 8000:8000 lead-enricher
```

Then hit it the same way as before:

```bash
curl -s -X POST http://127.0.0.1:8000/enrich \
  -H 'Content-Type: application/json' \
  -d '{"domain": "stripe.com"}' | python -m json.tool
```

The image is multi-stage: a `uv`-based builder resolves dependencies from
`uv.lock`, and the runtime stage ships only the virtualenv on
`python:3.13-slim-bookworm`. It runs as a non-root user (`uid 10001`), exposes
`8000`, and includes a `HEALTHCHECK` against `/healthz`. The Compose service
adds a read-only root filesystem, `no-new-privileges`, and a tmpfs `/tmp`.

## Development

```bash
uv sync --extra dev          # install runtime + dev dependencies
uv run pytest                # run the test suite
uv run pytest --cov          # run with coverage report (fails under threshold in CI)
```

The suite covers domain validation edge cases, network timeouts, successful
enrichment, tech detection, and the mock fallback, and holds **>80%** line
coverage.

## Configuration

| Env var  | Default     | Used by                                    |
| -------- | ----------- | ------------------------------------------ |
| `HOST`   | `127.0.0.1` | `lead-enricher` console entry point        |
| `PORT`   | `8000`      | `lead-enricher` console entry point        |
| `RELOAD` | unset       | Set to enable uvicorn auto-reload          |

## Project layout

```
src/lead_enricher/
  app.py       # FastAPI app, routes, dependency wiring
  enricher.py  # pipeline orchestration + confidence scoring
  fetch.py     # DNS resolution + HTML fetching
  detect.py    # tech-stack / industry / size signature detection
  mock.py      # deterministic fallback profiles
  domain.py    # input normalization and validation
  models.py    # Pydantic v2 contracts
tests/         # pytest suite
Dockerfile     # multi-stage container build
compose.yaml   # hardened local run
```

## License

MIT
