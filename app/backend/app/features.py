from __future__ import annotations

import numpy as np
import pandas as pd

ALL_FEATURES: list[str] = [
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "ret_5d_minus_20d",
    "ret_20d_minus_60d",
    "vol_20d",
    "vol_60d",
    "vol_ratio_20_60",
    "parkinson_vol_20d",
    "close_to_ma20",
    "close_to_ma50",
    "close_to_ma200",
    "ma20_to_ma50",
    "max_dd_60d",
    "dist_from_52w_high",
    "rsi_14",
    "zscore_20d",
    "bbands_pos",
    "volume_ratio_20d",
    "log_volume",
    "spy_ret_20d",
    "spy_vol_20d",
    "spy_close_to_ma50",
]

STATIC_INPUTS: list[str] = [*ALL_FEATURES, "otm_pct", "type_cc"]


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def compute_features(ticker_df: pd.DataFrame, spy_df: pd.DataFrame) -> pd.DataFrame:
    close = ticker_df["adjusted_close"]
    high = ticker_df["high"]
    low = ticker_df["low"]
    volume = ticker_df["volume"]
    log_ret = np.log(close / close.shift(1))

    feat = pd.DataFrame(index=ticker_df.index)

    feat["ret_5d"] = close / close.shift(5) - 1
    feat["ret_20d"] = close / close.shift(20) - 1
    feat["ret_60d"] = close / close.shift(60) - 1
    feat["ret_5d_minus_20d"] = feat["ret_5d"] - feat["ret_20d"]
    feat["ret_20d_minus_60d"] = feat["ret_20d"] - feat["ret_60d"]

    feat["vol_20d"] = log_ret.rolling(20).std() * np.sqrt(252)
    feat["vol_60d"] = log_ret.rolling(60).std() * np.sqrt(252)
    feat["vol_ratio_20_60"] = feat["vol_20d"] / feat["vol_60d"]
    hl_sq = np.log(high / low) ** 2 / (4 * np.log(2))
    feat["parkinson_vol_20d"] = np.sqrt(hl_sq.rolling(20).mean() * 252)

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    feat["close_to_ma20"] = close / ma20 - 1
    feat["close_to_ma50"] = close / ma50 - 1
    feat["close_to_ma200"] = close / ma200 - 1
    feat["ma20_to_ma50"] = ma20 / ma50 - 1

    feat["max_dd_60d"] = close / close.rolling(60).max() - 1
    feat["dist_from_52w_high"] = close / close.rolling(252).max() - 1

    feat["rsi_14"] = compute_rsi(close, 14)
    sd20 = close.rolling(20).std()
    feat["zscore_20d"] = (close - ma20) / sd20
    feat["bbands_pos"] = (close - (ma20 - 2 * sd20)) / (4 * sd20)

    feat["volume_ratio_20d"] = volume / volume.rolling(20).mean()
    feat["log_volume"] = np.log(volume.replace(0, 1))

    spy_close = spy_df["adjusted_close"]
    spy_log_ret = np.log(spy_close / spy_close.shift(1))
    spy_feat = pd.DataFrame(index=spy_df.index)
    spy_feat["spy_ret_20d"] = spy_close / spy_close.shift(20) - 1
    spy_feat["spy_vol_20d"] = spy_log_ret.rolling(20).std() * np.sqrt(252)
    spy_feat["spy_close_to_ma50"] = spy_close / spy_close.rolling(50).mean() - 1

    return feat.join(spy_feat, how="left")
