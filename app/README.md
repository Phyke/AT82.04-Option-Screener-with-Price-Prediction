# Options Scanner

A two-service web app that fetches live option chains and displays them in a filterable table alongside a candlestick chart.

## Architecture

```mermaid
graph LR
    subgraph Browser
        UI["SvelteKit UI\nport 5173"]
    end

    subgraph Backend["FastAPI · port 8000"]
        direction TB
        routes["main.py\n(routes)"]
        models["models.py\nOptionContract · OptionsRequest"]
        opts["utils/options.py\nfetch_options()"]
        md["utils/market_data.py\nfetch_spot() · fetch_stock_history()"]

        routes --> opts
        routes --> md
        opts --> models
        opts --> md
    end

    subgraph External
        YF["Yahoo Finance\n(via yfinance)"]
    end

    UI -- "POST /options" --> routes
    UI -- "GET /history/{ticker}" --> routes
    md -- "HTTP" --> YF
```

## Request Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant API as Backend
    participant YF as Yahoo Finance

    User->>UI: Enter tickers · click Scan
    UI->>API: POST /options {"tickers": [...]}

    loop for each ticker
        API->>YF: fetch_spot()
        YF-->>API: spot price
        API->>YF: option_chain(expiration)
        YF-->>API: calls + puts DataFrame
    end

    API-->>UI: list[OptionContract]
    UI-->>User: Filtered & sorted table

    User->>UI: Click a row
    UI->>API: GET /history/{ticker}
    API->>YF: ticker.history(period=6mo)
    YF-->>API: OHLCV data
    API-->>UI: list[Candle]
    UI-->>User: Candlestick chart + trade insight
```

## Stack

| Layer    | Technology                              |
|----------|-----------------------------------------|
| Frontend | SvelteKit 2 · Svelte 5 · Tailwind CSS 4 · lightweight-charts |
| Backend  | FastAPI · yfinance · pandas · Pydantic  |
| Runtime  | Python 3.14 (uv) · Node 20+ (npm)       |

## Quick Start

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload   # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```
