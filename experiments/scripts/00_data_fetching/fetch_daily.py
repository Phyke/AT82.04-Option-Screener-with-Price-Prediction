"""Fetch daily OHLCV from AlphaVantage and Yahoo Finance, compare, and persist.

For each ticker, downloads:
  - AlphaVantage TIME_SERIES_DAILY_ADJUSTED (premium endpoint, full history)
  - yfinance daily history (auto_adjust=False so we get raw + adjusted)

Then compares them on a common date range and reports any material disagreements.

Usage:
    uv run python scripts/00_data_fetching/fetch_daily.py                 # all universe tickers, save both
    uv run python scripts/00_data_fetching/fetch_daily.py AAPL TSLA NFLX  # specific tickers
    uv run python scripts/00_data_fetching/fetch_daily.py --compare_only  # skip save, only compare
"""

from __future__ import annotations

import sys
import time
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from loguru import logger

from config import UNIVERSE_TICKERS, settings

DATA_DIR = Path("data")
DAILY_AV_DIR = DATA_DIR / "daily_alpha"
DAILY_YF_DIR = DATA_DIR / "daily_yf"


# AlphaVantage


def fetch_alphavantage(ticker: str) -> pd.DataFrame:
    """TIME_SERIES_DAILY_ADJUSTED, full history, CSV format."""
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "outputsize": "full",
        "datatype": "csv",
        "apikey": settings.ALPHAVANTAGE_API_KEY.get_secret_value(),
    }
    r = requests.get(settings.ALPHAVANTAGE_API_URL, params=params, timeout=60)
    r.raise_for_status()
    text = r.text
    if text.startswith("{") or "Error" in text[:200] or "Note" in text[:200]:
        raise RuntimeError(f"AV error for {ticker}: {text[:300]}")
    df = pd.read_csv(StringIO(text))
    df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["source"] = "alphavantage"
    return df[
        [
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
    ]


# Yahoo Finance


def fetch_yfinance(ticker: str) -> pd.DataFrame:
    """yfinance daily, full history, raw + adjusted."""
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
    return df[keep]


# Comparison


def compare_one(ticker: str, av: pd.DataFrame, yfdf: pd.DataFrame) -> dict:
    """Inner-join on date, compute diffs on close / adjusted_close / volume."""
    a = av.set_index("date")[["close", "adjusted_close", "volume"]].add_suffix("_av")
    y = yfdf.set_index("date")[["close", "adjusted_close", "volume"]].add_suffix("_yf")
    j = a.join(y, how="inner").dropna()
    if j.empty:
        return {"ticker": ticker, "n": 0, "note": "no overlap"}

    def reldiff(a, b):
        return (a - b) / ((a + b) / 2) * 1e4  # basis points

    j["d_close_bps"] = reldiff(j["close_av"], j["close_yf"]).abs()
    j["d_adj_bps"] = reldiff(j["adjusted_close_av"], j["adjusted_close_yf"]).abs()
    j["d_vol_pct"] = (
        (j["volume_av"] - j["volume_yf"]).abs()
        / ((j["volume_av"] + j["volume_yf"]) / 2)
        * 100
    )

    return {
        "ticker": ticker,
        "n": len(j),
        "first_date": j.index.min().strftime("%Y-%m-%d"),
        "last_date": j.index.max().strftime("%Y-%m-%d"),
        "av_only_days": len(av) - len(j),
        "yf_only_days": len(yfdf) - len(j),
        "med_close_bps": float(j["d_close_bps"].median()),
        "p95_close_bps": float(j["d_close_bps"].quantile(0.95)),
        "max_close_bps": float(j["d_close_bps"].max()),
        "med_adj_bps": float(j["d_adj_bps"].median()),
        "p95_adj_bps": float(j["d_adj_bps"].quantile(0.95)),
        "max_adj_bps": float(j["d_adj_bps"].max()),
        "med_vol_pct": float(j["d_vol_pct"].median()),
        "p95_vol_pct": float(j["d_vol_pct"].quantile(0.95)),
        "av_last": av["date"].max().strftime("%Y-%m-%d"),
        "yf_last": yfdf["date"].max().strftime("%Y-%m-%d"),
    }


# Main


def fetch_one(ticker: str, save: bool) -> dict | None:
    try:
        av = fetch_alphavantage(ticker)
    except Exception as e:
        logger.error(f"{ticker}: AV FAIL: {e}")
        return None
    time.sleep(settings.ALPHAVANTAGE_SLEEP)
    try:
        yfdf = fetch_yfinance(ticker)
    except Exception as e:
        logger.error(f"{ticker}: YF FAIL: {e}")
        return None

    if save:
        DAILY_AV_DIR.mkdir(parents=True, exist_ok=True)
        DAILY_YF_DIR.mkdir(parents=True, exist_ok=True)
        av.to_csv(DAILY_AV_DIR / f"{ticker}.csv", index=False)
        yfdf.to_csv(DAILY_YF_DIR / f"{ticker}.csv", index=False)

    cmp = compare_one(ticker, av, yfdf)
    logger.info(
        f"{ticker}: AV={len(av):>5} YF={len(yfdf):>5} | "
        f"med_adj={cmp['med_adj_bps']:.1f}bps max_adj={cmp['max_adj_bps']:.1f}bps "
        f"med_vol={cmp['med_vol_pct']:.2f}%"
    )
    return cmp


def main():
    args = sys.argv[1:]
    save = "--compare_only" not in args
    cli_tickers = [a.upper() for a in args if not a.startswith("--")]
    tickers = cli_tickers if cli_tickers else list(UNIVERSE_TICKERS)

    logger.info(f"Fetching {len(tickers)} tickers from AlphaVantage + yfinance...")
    logger.info(
        f"  AV rate limit: {settings.ALPHAVANTAGE_RATE_PER_MIN}/min "
        f"({settings.ALPHAVANTAGE_SLEEP:.2f}s sleep)"
    )
    logger.info(f"  Save to: {DAILY_AV_DIR} and {DAILY_YF_DIR}")

    rows = []
    for tk in tickers:
        r = fetch_one(tk, save=save)
        if r:
            rows.append(r)

    if rows:
        df = pd.DataFrame(rows)
        logger.info(
            f"Aggregate: median adj_close diff = {df['med_adj_bps'].median():.2f} bps"
        )
        logger.info(
            f"           tickers with max adj diff > 100 bps = {(df['max_adj_bps'] > 100).sum()}"
        )


if __name__ == "__main__":
    main()
