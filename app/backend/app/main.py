from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Awaitable, Callable

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import demo
from app.cache import close_cache, init_cache
from app.calendar import current_expiry, market_now, most_recent_completed_session
from app.config import settings
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
    app.state.model = load_model(settings.MODEL_PATH, settings.FEATURE_SCALER_PATH)
    app.state.demo = demo.load_snapshot(settings.DEMO_SNAPSHOT_PATH)
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
        iv_tiers=req.iv_tiers,
    )


@app.post("/screener/refresh", response_model=ScreenerResponse)
async def screener_refresh(req: ScreenerRequest) -> ScreenerResponse:
    await clear_chain_cache()
    return await screener(req)


DailyProvider = Callable[[str], Awaitable[pd.DataFrame]]


async def _predict_per_ticker(
    tickers: list[str],
    anchor_date,
    daily_provider: DailyProvider,
) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    model = app.state.model
    preds: dict[str, float] = {}
    spots: dict[str, float] = {}
    errors: dict[str, str] = {}
    for t in tickers:
        if not model.has_ticker(t):
            errors[t] = "ticker not in model training set"
            continue
        try:
            hist = await daily_provider(t)
        except Exception as exc:
            errors[t] = f"daily history fetch failed: {exc}"
            continue
        sliced = hist.loc[:anchor_date]
        if len(sliced) < model.window:
            errors[t] = "insufficient history"
            continue
        anchor = sliced.index[-1]
        try:
            pred = model.predict_friday_close(t, sliced)
        except Exception as exc:
            errors[t] = f"prediction failed: {exc}"
            continue
        if pred is None:
            errors[t] = "prediction unavailable"
            continue
        preds[t] = pred
        spots[t] = float(sliced["adjusted_close"].loc[anchor])
    return preds, spots, errors


async def _predict(
    req: PredictRequest,
    *,
    as_of: datetime,
    anchor_date: date,
    daily_provider: DailyProvider,
) -> PredictResponse:
    anchor = pd.Timestamp(anchor_date)
    tickers = sorted({c.ticker for c in req.contracts})
    preds, spots, per_ticker_errors = await _predict_per_ticker(tickers, anchor, daily_provider)

    outputs: list[Prediction] = []
    for c in req.contracts:
        if c.ticker in per_ticker_errors:
            outputs.append(Prediction(
                ticker=c.ticker, strike=c.strike, type=c.type,
                error=per_ticker_errors[c.ticker],
            ))
            continue
        outputs.append(Prediction(
            ticker=c.ticker, strike=c.strike, type=c.type,
            pred_friday_close=round(preds[c.ticker], 4),
            spot_used=spots[c.ticker],
        ))

    return PredictResponse(
        as_of=as_of,
        model_input_date=anchor.date(),
        predictions=outputs,
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    return await _predict(
        req,
        as_of=market_now(),
        anchor_date=most_recent_completed_session(),
        daily_provider=get_daily_history,
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
    return _history_to_candles(ticker, df)


def _history_to_candles(ticker: str, df: pd.DataFrame) -> dict:
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


def _demo() -> demo.DemoSnapshot:
    return app.state.demo


async def _demo_chain_provider(ticker: str, expiry: str):
    return _demo().get_chain(ticker, expiry)


async def _demo_daily_provider(ticker: str) -> pd.DataFrame:
    return _demo().get_daily(ticker)


@app.get("/demo/universe", response_model=UniverseResponse)
async def demo_universe() -> UniverseResponse:
    snap = _demo()
    return UniverseResponse(
        tickers=snap.tickers(),
        policies=POLICIES,
        yield_targets=YIELD_TARGETS,
        expiry=snap.expiry,
        as_of=snap.taken_at,
    )


@app.post("/demo/screener", response_model=ScreenerResponse)
async def demo_screener(req: ScreenerRequest) -> ScreenerResponse:
    snap = _demo()
    holdings_list = [TickerState(h.ticker, h.shares, h.avg_cost) for h in req.holdings]
    return await run_screener(
        cash=req.cash,
        holdings_list=holdings_list,
        policy=req.policy,
        yield_target=req.yield_target,
        tolerance_mode=req.tolerance_mode,
        iv_tiers=req.iv_tiers,
        universe=snap.tickers(),
        expiry=snap.expiry,
        as_of=snap.taken_at,
        chain_provider=_demo_chain_provider,
    )


@app.post("/demo/screener/refresh", response_model=ScreenerResponse)
async def demo_screener_refresh(req: ScreenerRequest) -> ScreenerResponse:
    return await demo_screener(req)


@app.post("/demo/predict", response_model=PredictResponse)
async def demo_predict(req: PredictRequest) -> PredictResponse:
    snap = _demo()
    return await _predict(
        req,
        as_of=snap.taken_at,
        anchor_date=most_recent_completed_session(snap.taken_at),
        daily_provider=_demo_daily_provider,
    )


@app.get("/demo/history/{ticker}")
async def demo_history(ticker: str) -> dict:
    ticker = ticker.upper()
    snap = _demo()
    if ticker not in snap.daily:
        raise HTTPException(status_code=404, detail={"code": "TICKER_NOT_IN_DEMO"})
    return _history_to_candles(ticker, snap.get_daily(ticker))
