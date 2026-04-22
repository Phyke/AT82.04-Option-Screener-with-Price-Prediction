from __future__ import annotations

import pandas as pd

OHLCV_CHANNELS: list[str] = ["open", "high", "low", "close", "volume"]
WINDOW: int = 6

HISTORY_COL_BY_CHANNEL: dict[str, str] = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "adjusted_close",
    "volume": "volume",
}


def feature_columns(window: int = WINDOW) -> list[str]:
    return [f"{ch}_lag{k}" for k in range(1, window + 1) for ch in OHLCV_CHANNELS]


def build_feature_row(hist_df: pd.DataFrame, window: int = WINDOW) -> pd.Series | None:
    if len(hist_df) < window:
        return None
    recent = hist_df.iloc[-window:]
    needed = [HISTORY_COL_BY_CHANNEL[ch] for ch in OHLCV_CHANNELS]
    if recent[needed].isna().any().any():
        return None
    values: dict[str, float] = {}
    for lag in range(1, window + 1):
        bar = recent.iloc[-lag]
        for ch in OHLCV_CHANNELS:
            values[f"{ch}_lag{lag}"] = float(bar[HISTORY_COL_BY_CHANNEL[ch]])
    return pd.Series(values, index=feature_columns(window))
