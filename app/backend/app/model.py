from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from loguru import logger

from app.features import STATIC_INPUTS


class PriceModel:
    def __init__(self, artifact: dict):
        self.model = artifact["model"]
        self.feature_names: list[str] = list(artifact["feature_names"])
        self.name = artifact.get("name", "unknown")
        if self.feature_names != STATIC_INPUTS:
            raise RuntimeError(
                "feature_names in model artifact do not match STATIC_INPUTS.\n"
                f"  model: {self.feature_names}\n"
                f"  code:  {STATIC_INPUTS}"
            )

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        if list(features.columns) != self.feature_names:
            raise RuntimeError(
                f"column mismatch.\n  got: {list(features.columns)}\n  want: {self.feature_names}"
            )
        X = features.to_numpy(dtype=float)
        return self.model.predict_proba(X)[:, 1]


def load_model(path: Path) -> PriceModel:
    logger.info(f"loading price model from {path}")
    artifact = joblib.load(path)
    return PriceModel(artifact)
