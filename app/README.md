# Options Wheel Advisor

Full-stack web application that screens live option chains for cash-secured put (CSP) and covered call (CC) opportunities on a 35-ticker high-quality universe, predicts the Friday close price with a shared Random Forest model, and surfaces backtesting-backed policy hints drawn from the six-year study in `experiments/`.

For deployment instructions, see [DEPLOY.md](DEPLOY.md) and [DEPLOY-traefik.md](DEPLOY-traefik.md) (Traefik + HTTPS).


## Table of contents
- [Options Wheel Advisor](#options-wheel-advisor)
  - [Table of contents](#table-of-contents)
  - [Architecture](#architecture)
  - [Backend modules (`backend/app/`)](#backend-modules-backendapp)
  - [API endpoints](#api-endpoints)
  - [Quick start (local)](#quick-start-local)
  - [Quick start (Docker Compose)](#quick-start-docker-compose)
  - [Configuration](#configuration)
  - [Policy semantics (covered calls)](#policy-semantics-covered-calls)
  - [Data and persistence](#data-and-persistence)


## Architecture

```
+------------------+       +-------------------------+       +---------+
|  SvelteKit UI    |       |  FastAPI (async)        |       |         |
|  port 5173       | <---> |  port 8000              | <---> | Redis   |
|  Svelte 5 runes  |       |  RF model in-process    |       | (opt.)  |
|  Tailwind CSS 4  |       |  Black-Scholes delta    |       |         |
+------------------+       +-------------------------+       +---------+
                                       |
                                       v
                              +-------------------+
                              | yfinance (15-min  |
                              | delayed chains,   |
                              | 2yr OHLCV)        |
                              +-------------------+
```

Redis is optional: if unreachable the backend runs without caching and logs a warning. The Random Forest model (`models/price_model.pkl`) and per-ticker scalers (`models/feature_scaler.pkl`) are loaded once at startup via a `lifespan` context manager. A pre-captured demo snapshot (`data/demo_snapshot.pkl`) powers offline `/demo/*` routes.

## Backend modules (`backend/app/`)

| Module | Role |
|---|---|
| `main.py` | FastAPI app, lifespan, routes |
| `universe.py` | `HIGH_QUALITY_TICKERS` (35 tickers) and IV-tier classification |
| `yf_client.py` | yfinance fetch with Redis TTL caching (chains 5 min, daily 24 h) |
| `screener.py` | CSP/CC selection, policy logic (strict/safe/aggressive), yield matching |
| `greeks.py` | Black-Scholes delta in-process (`r = 4%`) |
| `model.py` + `features.py` | RF inference with per-ticker mean-variance standardization |
| `research.py` | Lookup tables from the 2020-2026 and 2024-2026 backtests |
| `demo.py` | Pre-captured snapshot loader for offline demonstrations |
| `cache.py` | Redis wrapper with graceful fallback |
| `calendar.py` | U.S. market session + current Friday expiry helpers |
| `config.py` | `pydantic-settings` configuration |
| `schemas.py` | Request/response Pydantic models |

## API endpoints

Live (yfinance-backed):

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/universe` | 35-ticker universe, available policies, yield targets, current Friday expiry |
| POST | `/screener` | Run the screener; accepts cash, holdings, policy, yield target, tolerance mode, IV-tier filter |
| POST | `/screener/refresh` | Clear Redis chain cache and re-run |
| POST | `/predict` | Predict Friday close for a list of `{ticker, strike, type}` |
| GET | `/history/{ticker}` | Last 252 daily candles for candlestick rendering |

Five `/demo/*` routes mirror the non-health endpoints against the embedded snapshot, so the UI can be demonstrated without live market hours.

## Quick start (local)

```bash
# Backend (Python 3.12+, uv)
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend (Node 20+, npm)
cd ../frontend
npm install
npm run dev
```

Backend: http://localhost:8000 (docs at `/docs`). Frontend: http://localhost:5173.

## Quick start (Docker Compose)

```bash
docker compose up --build
```

Starts both services with hot reload. Backend is reachable at `http://backend:8000` from within the network (used by the Vite dev server via `VITE_API_URL`) and at `http://localhost:8000` from the host.

Production variants:

- `docker-compose.prod.yml` - bare production images without Traefik
- `docker-compose.prod.traefik.yml` + `docker-compose.traefik.yml` - HTTPS via Traefik (see `DEPLOY-traefik.md`)

## Configuration

Backend settings come from `.env` (pydantic-settings). Defaults:

| Variable | Default | Notes |
|---|---|---|
| `MODEL_PATH` | `models/price_model.pkl` | Shared Random Forest |
| `FEATURE_SCALER_PATH` | `models/feature_scaler.pkl` | Per-ticker mean/std |
| `DEMO_SNAPSHOT_PATH` | `data/demo_snapshot.pkl` | Pre-captured chains for `/demo/*` |
| `OPTION_CHAIN_TTL_SECONDS` | `300` | Redis TTL for live chains |
| `DAILY_HISTORY_TTL_SECONDS` | `86400` | Redis TTL for 2y OHLCV |
| `YF_CONCURRENCY` | `8` | Max concurrent yfinance calls |
| `REDIS_URL` | `redis://localhost:6379/0` | Unset is fine; backend degrades |
| `REDIS_PREFIX` | `options-app` | Namespace for all keys |
| `CORS_ORIGINS` | `[]` | Comma-separated allowlist |
| `CORS_ORIGIN_REGEX` | localhost pattern | Default permits `localhost`/`127.0.0.1` |
| `LOG_LEVEL` | `INFO` | `loguru` level |

Frontend: `VITE_API_URL` controls the base URL the browser uses to reach the backend (defaults to the dev proxy in `vite.config.ts`).

## Policy semantics (covered calls)

- **Strict** - CC strike must be >= average cost basis; refuses to recommend otherwise
- **Safe** - prefers above-cost-basis; falls back to farthest-OTM strike if none qualify
- **Aggressive** - selects the closest-to-target yield regardless of cost basis

Each screener response includes `research_by_tier` with the historically best policy, cumulative return, annualized Sharpe, and a `stable` flag indicating whether the 2024-2026 and 2020-2026 windows agree. The underlying tables live in `research.py` and were generated by `experiments/05_options_income_strategies_backtesting.ipynb`.

## Data and persistence

No persistent data warehouse. All operational data is fetched live from yfinance with Redis TTL caching; all model state is encapsulated in the two pickled artifacts in `backend/models/`. The historical Alpha Vantage dataset used to train the model and build the policy matrix lives in `experiments/` and is not required at runtime.
