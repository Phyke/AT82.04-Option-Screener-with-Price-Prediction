"""Standalone yfinance-based weekly direction predictor.

Loads pre-trained per-ticker LightGBM models from `backend/models/per_ticker/`
and generates a probability that next Friday's close >= last Monday's close.

No external project dependencies — only yfinance + lightgbm + numpy + pandas.
Mirrors the training feature schema (ohlcv, window=10) exactly.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BACKEND_DIR / "models" / "per_ticker"
ELIGIBLE_PATH = BACKEND_DIR / "data" / "eligible_tickers.json"

WINDOW = 10
SPLIT_LOOKBACK_DAYS = 14


# ── Eligible universe ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def eligible_tickers() -> list[str]:
    if not ELIGIBLE_PATH.exists():
        return []
    return sorted(json.loads(ELIGIBLE_PATH.read_text())["eligible_tickers"])


@lru_cache(maxsize=1)
def vol_buckets() -> dict[str, list[str]]:
    if not ELIGIBLE_PATH.exists():
        return {}
    data = json.loads(ELIGIBLE_PATH.read_text())
    return {name: cfg["tickers"] for name, cfg in data["vol_buckets"].items()}


# ── Feature builder (mirrors training: pipeline.features.price_features) ──

def _build_ohlcv_features(window: pd.DataFrame) -> dict[str, float]:
    """Returns the same 50 features the model was trained on (ohlcv level)."""
    closes = window["close"].values
    log_rets = np.diff(np.log(closes))
    vols = np.log1p(window["volume"].values)
    o = window["open"].values
    h = window["high"].values
    l = window["low"].values
    c = window["close"].values

    feats: dict[str, float] = {f"ret_{i}": float(v) for i, v in enumerate(log_rets)}
    for i, v in enumerate(vols):
        feats[f"logvol_{i}"] = float(v)
    for i in range(len(window)):
        ci = c[i] if c[i] != 0 else 1e-8
        feats[f"body_{i}"] = float((c[i] - o[i]) / ci)
        feats[f"range_{i}"] = float((h[i] - l[i]) / ci)
        feats[f"uwck_{i}"] = float((h[i] - max(o[i], c[i])) / ci)
        feats[f"lwck_{i}"] = float((min(o[i], c[i]) - l[i]) / ci)
    return feats


# ── yfinance fetch ─────────────────────────────────────────────────────

def fetch_recent_daily(ticker: str, days: int = 60) -> pd.DataFrame:
    """Pull recent daily OHLCV. auto_adjust=True matches the training schema."""
    end = datetime.now().date() + timedelta(days=1)
    start = end - timedelta(days=days * 2)
    df = yf.download(ticker, start=start, end=end, interval="1d",
                     auto_adjust=True, progress=False, threads=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "open", "high", "low", "close", "volume"]]


def detect_recent_splits(ticker: str, lookback_days: int = SPLIT_LOOKBACK_DAYS) -> list[dict]:
    """Return any splits in the last `lookback_days` calendar days."""
    try:
        actions = yf.Ticker(ticker).actions
    except Exception:
        return []
    if actions is None or actions.empty or "Stock Splits" not in actions.columns:
        return []
    splits = actions[actions["Stock Splits"] > 0]
    if splits.empty:
        return []
    cutoff = pd.Timestamp(datetime.now().date() - timedelta(days=lookback_days))
    idx_naive = splits.index.tz_localize(None) if splits.index.tz is not None else splits.index
    recent = splits[idx_naive >= cutoff]
    return [
        {"date": str(idx.date()), "ratio": float(row["Stock Splits"])}
        for idx, row in recent.iterrows()
    ]


# ── Model loading ──────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def _load_model(ticker: str) -> tuple[lgb.Booster, dict] | None:
    booster_path = MODELS_DIR / f"{ticker}.lgb"
    meta_path = MODELS_DIR / f"{ticker}.meta.json"
    if not booster_path.exists() or not meta_path.exists():
        return None
    booster = lgb.Booster(model_file=str(booster_path))
    meta = json.loads(meta_path.read_text())
    return booster, meta


def is_supported(ticker: str) -> bool:
    return _load_model(ticker.upper()) is not None


# ── Inference ──────────────────────────────────────────────────────────

def predict_ticker(ticker: str) -> dict:
    """Generate one prediction for one ticker. Returns a structured dict."""
    ticker = ticker.upper()
    out: dict = {"ticker": ticker, "warnings": []}

    loaded = _load_model(ticker)
    if loaded is None:
        out["error"] = "no model for this ticker"
        out["supported"] = False
        return out
    booster, meta = loaded

    daily = fetch_recent_daily(ticker)
    if daily.empty or len(daily) < WINDOW:
        out["error"] = f"insufficient yfinance data ({len(daily)} rows, need {WINDOW})"
        return out

    decision_date = daily["date"].iloc[-1].date().isoformat()
    last_close = float(daily["close"].iloc[-1])

    splits = detect_recent_splits(ticker)
    if splits:
        out["warnings"].append({
            "type": "recent_split",
            "message": (
                f"Stock split detected within last {SPLIT_LOOKBACK_DAYS} days. "
                "Volume features may have a brief discontinuity. "
                "Verify model output before placing trades."
            ),
            "splits": splits,
        })

    feat_cols = meta["feature_cols"]
    win = daily.tail(WINDOW).reset_index(drop=True)
    feats = _build_ohlcv_features(win)
    missing = [c for c in feat_cols if c not in feats]
    if missing:
        out["error"] = f"feature build incomplete: missing {missing[:5]}"
        return out

    X = np.array([[feats[c] for c in feat_cols]])
    prob_up = float(booster.predict(X, num_iteration=meta.get("best_iteration"))[0])
    threshold = float(meta.get("tuned_threshold", 0.625))
    signal = "TRADE" if prob_up >= threshold else "SKIP"

    out.update({
        "supported": True,
        "decision_date": decision_date,
        "last_close": round(last_close, 2),
        "probability_up": round(prob_up, 4),
        "probability_down": round(1.0 - prob_up, 4),
        "tuned_threshold": threshold,
        "signal": signal,
        "expected_test_precision": meta.get("tuned_test_precision"),
        "model": {
            "feature_set": "ohlcv",
            "window": WINDOW,
            "n_features": meta["n_features"],
            "trained_at": meta.get("trained_at"),
        },
    })
    return out
