from __future__ import annotations

from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.cache import close_cache, init_cache
from app.calendar import current_expiry, market_now, most_recent_completed_session
from app.config import settings
from app.features import STATIC_INPUTS, compute_features
from app.logging_config import setup_logging
from app.model import load_model
from app.schemas import (
    PredictRequest,
    PredictResponse,
    Prediction,
    ScreenerRequest,
    ScreenerResponse,
    UniverseResponse,
)
from app.screener import TickerState, run_screener
from app.universe import HIGH_QUALITY_TICKERS, is_universe_ticker
from app.yf_client import clear_chain_cache, get_daily_history

YIELD_TARGETS = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05]
POLICIES = ["strict", "safe", "aggressive"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting backend")
    app.state.model = load_model(settings.MODEL_PATH)
    await init_cache()
    yield
    await close_cache()
    logger.info("shutting down backend")


app = FastAPI(title="Options Wheel Advisor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/universe", response_model=UniverseResponse)
async def universe() -> UniverseResponse:
    return UniverseResponse(
        tickers=list(HIGH_QUALITY_TICKERS),
        policies=POLICIES,
        yield_targets=YIELD_TARGETS,
        expiry=current_expiry(),
        as_of=market_now(),
    )


@app.post("/screener", response_model=ScreenerResponse)
async def screener(req: ScreenerRequest) -> ScreenerResponse:
    holdings_list = [TickerState(h.ticker, h.shares, h.avg_cost) for h in req.holdings]
    return await run_screener(
        cash=req.cash,
        holdings_list=holdings_list,
        policy=req.policy,
        yield_target=req.yield_target,
        tolerance_mode=req.tolerance_mode,
    )


@app.post("/screener/refresh", response_model=ScreenerResponse)
async def screener_refresh(req: ScreenerRequest) -> ScreenerResponse:
    await clear_chain_cache()
    return await screener(req)


async def _load_features_for(tickers: list[str], anchor_date) -> tuple[dict[str, pd.Series], dict[str, float], dict[str, str]]:
    spy = await get_daily_history("SPY")
    rows: dict[str, pd.Series] = {}
    spots: dict[str, float] = {}
    errors: dict[str, str] = {}
    for t in tickers:
        try:
            hist = await get_daily_history(t)
        except Exception as exc:
            errors[t] = f"daily history fetch failed: {exc}"
            continue
        if len(hist) < 252:
            errors[t] = "insufficient history"
            continue
        sliced = hist.loc[:anchor_date]
        if sliced.empty:
            errors[t] = "no history on or before anchor"
            continue
        anchor = sliced.index[-1]
        try:
            feats = compute_features(hist, spy)
            feat_row = feats.loc[anchor]
        except Exception as exc:
            errors[t] = f"feature compute failed: {exc}"
            continue
        if feat_row.isna().any():
            errors[t] = "NaN in features"
            continue
        rows[t] = feat_row
        spots[t] = float(hist["adjusted_close"].loc[anchor])
    return rows, spots, errors


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    model = app.state.model
    anchor = pd.Timestamp(most_recent_completed_session())
    tickers = sorted({c.ticker for c in req.contracts})
    feat_rows, spots, per_ticker_errors = await _load_features_for(tickers, anchor)

    rows: list[dict] = []
    outputs: list[Prediction] = []
    row_index_for_pred: list[int] = []

    for i, c in enumerate(req.contracts):
        if c.ticker in per_ticker_errors:
            outputs.append(Prediction(
                ticker=c.ticker, strike=c.strike, type=c.type,
                error=per_ticker_errors[c.ticker],
            ))
            continue
        spot = spots[c.ticker]
        otm_pct = (c.strike - spot) / spot if c.type == "call" else (spot - c.strike) / spot
        type_cc = 1 if c.type == "call" else 0
        row_dict = feat_rows[c.ticker].to_dict()
        row_dict["otm_pct"] = otm_pct
        row_dict["type_cc"] = type_cc
        rows.append({k: row_dict[k] for k in STATIC_INPUTS})
        outputs.append(Prediction(
            ticker=c.ticker, strike=c.strike, type=c.type,
            otm_pct=round(otm_pct, 6), spot_used=spot,
            ood=otm_pct > 0.05 or otm_pct < 0.01,
        ))
        row_index_for_pred.append(i)

    if rows:
        X = pd.DataFrame(rows, columns=STATIC_INPUTS)
        probs = model.predict_proba(X)
        for idx, p in zip(row_index_for_pred, probs):
            outputs[idx].p_assigned = float(round(p, 4))

    return PredictResponse(
        as_of=market_now(),
        model_input_date=anchor.date(),
        predictions=outputs,
    )


@app.get("/history/{ticker}")
async def history(ticker: str) -> dict:
    ticker = ticker.upper()
    if not is_universe_ticker(ticker):
        raise HTTPException(status_code=400, detail={"code": "TICKER_OUTSIDE_UNIVERSE"})
    try:
        df = await get_daily_history(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "UPSTREAM_ERROR", "message": str(exc)})
    clean = df.dropna(subset=["open", "high", "low", "adjusted_close"]).tail(252)
    candles = [
        {
            "date": idx.date().isoformat(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["adjusted_close"]),
            "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
        }
        for idx, row in clean.iterrows()
    ]
    return {"ticker": ticker, "candles": candles}
