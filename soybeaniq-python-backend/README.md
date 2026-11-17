# SoybeanIQ Python Optimization Backend

FastAPI + Google OR-Tools CP-SAT service for procurement allocation. Designed to run as a separate Render Web Service while the existing SoybeanIQ Hatchable app remains the authenticated frontend and system of record.

## Endpoints

- `GET /health` — public health check.
- `POST /v1/optimize` — private optimization endpoint; requires `X-SoybeanIQ-Service-Key`.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export SOYBEANIQ_SERVICE_KEY='replace-with-a-long-random-secret'
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pytest -q
```

## Render deployment

Create a Render Web Service from this repository with:

- Runtime: Docker
- Dockerfile path: `./Dockerfile`
- Region: Singapore (closest listed region to Tamil Nadu)
- Health check path: `/health`
- Environment variable: `SOYBEANIQ_SERVICE_KEY` = a long random secret

Then add these Hatchable project secrets (server-side only):

- `SOYBEANIQ_OPTIMIZER_URL` = the Render service base URL
- `SOYBEANIQ_SERVICE_KEY` = exactly the same secret

Never put the service key in `public/` files or browser JavaScript.

## Optimization model

- Exact demand fulfillment at 1 kg quantity granularity.
- Minimizes landed procurement cost (purchase + transport per MT).
- Enforces eligible quote availability, registered supplier capacity, expiry, quality thresholds, delivery deadline, min/max supplier count and budget.
- Aggregates selected quote quantities by supplier for supplier-count and capacity constraints.
- Returns CP-SAT status, feasibility, allocation, excluded quotes, and optimality diagnostics.

Quality percentages are only as trustworthy as the source data. Missing test results fail a requested quality threshold. Human review remains mandatory before purchase approval.

## Integration contract

Hatchable should call `POST {SOYBEANIQ_OPTIMIZER_URL}/v1/optimize` from a server-side API route after authenticating the user and resolving their workspace. Send the quotes and constraints from that workspace only. Do not accept arbitrary user IDs or quote data from the browser as authoritative. Persist successful results to `procurement_plans` and write an audit event using the existing Hatchable database/workspace pattern.
