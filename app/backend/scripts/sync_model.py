"""Copy the frozen RandomForest price model from experiments/output into the backend."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[3] / "experiments" / "output" / "08_price_prediction_modeling" / "price_model.pkl"
TARGET = Path(__file__).resolve().parent.parent / "models" / "price_model.pkl"


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: source model not found at {SOURCE}", file=sys.stderr)
        return 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)
    print(f"Copied {SOURCE} -> {TARGET} ({TARGET.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
