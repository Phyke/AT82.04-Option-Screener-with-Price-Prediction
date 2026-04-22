from __future__ import annotations

import pickle
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

_snapshot: dict | None = None


def load(path: Path) -> None:
    global _snapshot
    with path.open("rb") as f:
        _snapshot = pickle.load(f)
    logger.info(
        f"demo snapshot loaded: taken_at={_snapshot['taken_at']} expiry={_snapshot['expiry']} "
        f"daily={len(_snapshot['daily'])} chains={len(_snapshot['chains'])}"
    )


def is_enabled() -> bool:
    return _snapshot is not None


def taken_at() -> datetime:
    if _snapshot is None:
        raise RuntimeError("demo snapshot not loaded")
    return _snapshot["taken_at"]


def expiry() -> date:
    if _snapshot is None:
        raise RuntimeError("demo snapshot not loaded")
    return date.fromisoformat(_snapshot["expiry"])


def daily(ticker: str) -> pd.DataFrame | None:
    if _snapshot is None:
        return None
    return _snapshot["daily"].get(ticker.upper())


def chain(ticker: str, expiry_s: str) -> Any:
    if _snapshot is None:
        return None
    return _snapshot["chains"].get(f"{ticker.upper()}:{expiry_s}")
