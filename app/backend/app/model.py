from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from loguru import logger

from app.features import build_feature_row


class PriceModel:
    def __init__(self, model_artifact: dict, scaler_artifact: dict):
        self.model = model_artifact["model"]
        self.cols: list[str] = list(model_artifact["cols"])
        self.window: int = int(model_artifact["window"])
        self.tier: str = model_artifact["tier"]
        self.name: str = model_artifact["model_name"]
        self.scalers: dict = scaler_artifact["scalers"]

    def has_ticker(self, ticker: str) -> bool:
        return ticker in self.scalers

    def predict_friday_close(self, ticker: str, hist_df: pd.DataFrame) -> float | None:
        if ticker not in self.scalers:
            return None
        row = build_feature_row(hist_df, self.window)
        if row is None:
            return None
        row = row.loc[self.cols]
        sc = self.scalers[ticker]
        feat_mean = sc["feat_mean"].loc[self.cols].to_numpy(dtype=float)
        feat_std = sc["feat_std"].loc[self.cols].to_numpy(dtype=float)
        scaled = (row.to_numpy(dtype=float) - feat_mean) / feat_std
        X = scaled.reshape(1, -1)
        y_scaled = float(self.model.predict(X)[0])
        pred = y_scaled * sc["close_std"] + sc["close_mean"]
        if not np.isfinite(pred):
            return None
        return float(pred)


def load_model(model_path: Path, scaler_path: Path) -> PriceModel:
    logger.info(f"loading price model from {model_path}")
    model_artifact = joblib.load(model_path)
    logger.info(f"loading feature scaler from {scaler_path}")
    scaler_artifact = joblib.load(scaler_path)
    model = PriceModel(model_artifact, scaler_artifact)
    logger.info(
        f"model ready: {model.name} window={model.window} tier={model.tier} "
        f"tickers={len(model.scalers)} cols={len(model.cols)}"
    )
    return model
