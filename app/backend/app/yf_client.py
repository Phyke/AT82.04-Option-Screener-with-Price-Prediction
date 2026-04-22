from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pandas as pd
import yfinance as yf
from loguru import logger

from app.cache import get_pickle, set_pickle, delete as cache_delete
from app.config import settings


def _normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "adjusted_close",
            "Volume": "volume",
        }
    )[["open", "high", "low", "adjusted_close", "volume"]].astype(float)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out.index.name = "date"
    out = out.dropna(subset=["open", "high", "low", "adjusted_close"])
    return out


def _fetch_history_sync(ticker: str) -> pd.DataFrame:
    raw = yf.Ticker(ticker).history(period="2y", auto_adjust=True)
    if raw.empty:
        raise RuntimeError(f"yfinance returned empty history for {ticker}")
    return _normalize_history(raw)


async def get_daily_history(ticker: str) -> pd.DataFrame:
    ticker = ticker.upper()
    key = f"daily:{ticker}"
    cached = await get_pickle(key)
    if isinstance(cached, pd.DataFrame) and not cached.empty:
        return cached
    logger.info(f"fetching daily history for {ticker}")
    df = await asyncio.to_thread(_fetch_history_sync, ticker)
    await set_pickle(key, df, settings.DAILY_HISTORY_TTL_SECONDS)
    return df


@dataclass
class ChainFetch:
    spot: float
    calls: pd.DataFrame
    puts: pd.DataFrame


def _fetch_chain_sync(ticker: str, expiry: str) -> ChainFetch:
    tk = yf.Ticker(ticker)
    try:
        spot = float(tk.fast_info.last_price)
    except Exception:
        spot = float("nan")
    chain = tk.option_chain(expiry)
    return ChainFetch(spot=spot, calls=chain.calls, puts=chain.puts)


async def get_option_chain(ticker: str, expiry: str, *, bypass_cache: bool = False) -> ChainFetch:
    ticker = ticker.upper()
    key = f"chain:{ticker}:{expiry}"
    if not bypass_cache:
        cached = await get_pickle(key)
        if isinstance(cached, ChainFetch):
            return cached
    logger.info(f"fetching option chain for {ticker} @ {expiry}")
    fetched = await asyncio.to_thread(_fetch_chain_sync, ticker, expiry)
    await set_pickle(key, fetched, settings.OPTION_CHAIN_TTL_SECONDS)
    return fetched


async def clear_chain_cache() -> None:
    await cache_delete("chain:*")
