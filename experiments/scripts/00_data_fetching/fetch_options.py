"""Fetch historical options chains from AlphaVantage HISTORICAL_OPTIONS.

For each ticker, iterates trading days between
`max(settings.UNIVERSE_START_DATE, ticker's first daily bar)` and
`settings.UNIVERSE_END_DATE`, saving one CSV per (ticker, date) under
`data/options_alpha/<TICKER>/`.

Tickers that IPO'd after UNIVERSE_START_DATE start from their first daily
bar (avoids wasted API calls on pre-IPO dates). Tickers with daily history
before UNIVERSE_START_DATE still start on UNIVERSE_START_DATE.

Usage:
    uv run python scripts/00_data_fetching/fetch_options.py
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from loguru import logger
from tqdm import tqdm

from config import UNIVERSE_TICKERS, settings

DATA_DIR = Path("data")
OPTIONS_DIR = DATA_DIR / "options_alpha"
DAILY_ALPHA_DIR = DATA_DIR / "daily_alpha"


def fetch_options_data(symbol: str, date: str | None = None) -> pd.DataFrame | None:
    params = {
        "function": "HISTORICAL_OPTIONS",
        "symbol": symbol,
        "datatype": "csv",
        "apikey": settings.ALPHAVANTAGE_API_KEY.get_secret_value(),
    }
    if date:
        params["date"] = date

    try:
        response = requests.get(
            settings.ALPHAVANTAGE_API_URL, params=params, timeout=30
        )
        text = response.text.strip()

        if text.startswith("{") or text.startswith("["):
            try:
                j = json.loads(text)
                if any(
                    k in j
                    for k in (
                        "Error Message",
                        "Note",
                        "Information",
                        "message",
                        "endpoint",
                    )
                ):
                    return None
            except Exception:
                pass
            return None

        df = pd.read_csv(io.StringIO(text))
        if df.empty:
            return None
        return df

    except Exception as e:
        tqdm.write(f"Error fetching options for {symbol} {date}: {e}")
        return None


def generate_trading_days(start_date: str, end_date: str) -> list[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    trading_days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            trading_days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return trading_days


def get_ticker_start_date(symbol: str, universe_start: str) -> str:
    """Return max(universe_start, ticker's first daily bar date).

    Skips pre-IPO dates for late-listed tickers. Falls back to universe_start
    if the daily CSV is missing.
    """
    csv_path = DAILY_ALPHA_DIR / f"{symbol}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, nrows=1)
            if not df.empty and "date" in df.columns:
                first = str(df["date"].iloc[0]).split()[0]
                return max(first, universe_start)
        except Exception:
            pass
    return universe_start


def main():
    OPTIONS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Fetching options for {len(UNIVERSE_TICKERS)} tickers...")
    logger.info(
        f"  AV rate limit: {settings.ALPHAVANTAGE_RATE_PER_MIN}/min "
        f"({settings.ALPHAVANTAGE_SLEEP:.2f}s sleep)"
    )
    logger.info(
        f"  Window: {settings.UNIVERSE_START_DATE} -> {settings.UNIVERSE_END_DATE}"
    )
    logger.info(f"  Save to: {OPTIONS_DIR}")

    for symbol in tqdm(UNIVERSE_TICKERS, desc="Processing tickers"):
        ticker_start = get_ticker_start_date(symbol, settings.UNIVERSE_START_DATE)
        ticker_trading_days = generate_trading_days(
            ticker_start, settings.UNIVERSE_END_DATE
        )

        ticker_dir = OPTIONS_DIR / symbol
        ticker_dir.mkdir(parents=True, exist_ok=True)

        skipped_count = 0
        fetched_count = 0

        for date in tqdm(ticker_trading_days, desc=f"{symbol} dates", leave=False):
            date_file = ticker_dir / f"{symbol}_options_{date}.csv"

            if date_file.exists():
                skipped_count += 1
                continue

            options_df = fetch_options_data(symbol, date)

            if options_df is not None:
                fetched_count += 1
                options_df.to_csv(date_file, index=False)

            time.sleep(settings.ALPHAVANTAGE_SLEEP)

        tqdm.write(
            f"[DONE] {symbol}: Skipped: {skipped_count} | Fetched: {fetched_count}"
        )


if __name__ == "__main__":
    main()
