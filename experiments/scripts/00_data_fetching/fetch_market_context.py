"""Fetch broad market / cross-asset context ETFs and indices from yfinance.

These tickers are used as complementary features to SPY in the price
prediction feature engineering step. They capture volatility regime,
sector rotation, rates, credit, dollar, and commodities in a way that
is *not* multicollinear with SPY returns alone.

Saved files are named by the "safe" symbol (no `^`, `=`, `-`) so downstream
code can reference them simply. The mapping between yfinance ticker and
safe filename is printed at the top of each run.

Usage:
    uv run python scripts/00_data_fetching/fetch_market_context.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

DATA_DIR = Path("data")
DAILY_YF_DIR = DATA_DIR / "daily_yf"

MARKET_CONTEXT = {
    "VIX": "^VIX",
    "VIX9D": "^VIX9D",
    "TNX": "^TNX",
    "FVX": "^FVX",
    "IRX": "^IRX",
    "DXY": "DX-Y.NYB",
    "XLK": "XLK",
    "XLF": "XLF",
    "XLE": "XLE",
    "XLV": "XLV",
    "XLY": "XLY",
    "XLI": "XLI",
    "XLU": "XLU",
    "XLP": "XLP",
    "XLB": "XLB",
    "XLC": "XLC",
    "XLRE": "XLRE",
    "HYG": "HYG",
    "LQD": "LQD",
    "TLT": "TLT",
    "IEF": "IEF",
    "SHY": "SHY",
    "GLD": "GLD",
    "USO": "USO",
    "UUP": "UUP",
    "QQQ": "QQQ",
    "IWM": "IWM",
}


def fetch_yfinance(ticker: str) -> pd.DataFrame:
    yt = yf.Ticker(ticker)
    df = yt.history(period="max", auto_adjust=False, actions=True)
    if df.empty:
        raise RuntimeError(f"YF empty for {ticker}")
    df = df.reset_index()
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    if "adj_close" in df.columns:
        df = df.rename(columns={"adj_close": "adjusted_close"})
    if "stock_splits" in df.columns:
        df = df.rename(columns={"stock_splits": "split_coefficient"})
        df["split_coefficient"] = df["split_coefficient"].replace(0, 1.0)
    if "dividends" in df.columns:
        df = df.rename(columns={"dividends": "dividend_amount"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.sort_values("date").reset_index(drop=True)
    df["source"] = "yfinance"
    keep = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
        "dividend_amount",
        "split_coefficient",
        "source",
    ]
    for c in keep:
        if c not in df.columns:
            df[c] = np.nan
    if "adjusted_close" not in df.columns or df["adjusted_close"].isna().all():
        df["adjusted_close"] = df["close"]
    return df[keep]


def main():
    DAILY_YF_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"Fetching {len(MARKET_CONTEXT)} market context tickers -> {DAILY_YF_DIR}"
    )

    ok, fail = 0, 0
    for safe, yt in MARKET_CONTEXT.items():
        try:
            df = fetch_yfinance(yt)
            out = DAILY_YF_DIR / f"{safe}.csv"
            df.to_csv(out, index=False)
            logger.info(
                f"  {safe:<6} ({yt:<12}) n={len(df):>5}  {df['date'].min().date()} -> {df['date'].max().date()}"
            )
            ok += 1
        except Exception as e:
            logger.error(f"  {safe:<6} ({yt:<12}) FAIL: {e}")
            fail += 1

    logger.info(f"Done. ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
