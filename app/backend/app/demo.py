from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from app.yf_client import ChainFetch


@dataclass
class DemoSnapshot:
    taken_at: datetime
    expiry: date
    daily: dict[str, pd.DataFrame]
    chains: dict[str, ChainFetch]

    def tickers(self) -> list[str]:
        return sorted(self.daily.keys())

    def get_daily(self, ticker: str) -> pd.DataFrame:
        df = self.daily.get(ticker.upper())
        if df is None or df.empty:
            raise RuntimeError(f"demo snapshot has no daily history for {ticker}")
        return df

    def get_chain(self, ticker: str, expiry: str) -> ChainFetch:
        c = self.chains.get(f"{ticker.upper()}:{expiry}")
        if c is None:
            raise RuntimeError(f"demo snapshot has no chain for {ticker} @ {expiry}")
        return c


def load_snapshot(path: Path) -> DemoSnapshot:
    with path.open("rb") as f:
        raw = pickle.load(f)
    expiry = raw["expiry"]
    if isinstance(expiry, str):
        expiry = date.fromisoformat(expiry)
    snap = DemoSnapshot(
        taken_at=raw["taken_at"],
        expiry=expiry,
        daily=raw["daily"],
        chains=raw["chains"],
    )
    logger.info(
        f"demo snapshot loaded from {path}: taken_at={snap.taken_at} expiry={snap.expiry} "
        f"daily={len(snap.daily)} chains={len(snap.chains)}"
    )
    return snap
