"""Consolidate data/options_alpha/<TICKER>/*.csv into data/options_parquet/<TICKER>.parquet.

One parquet per ticker, containing every row across every daily file with the
`date` column preserved (it's already in the source CSVs). Writes to a separate
directory so the raw CSVs are untouched until you confirm.

Reports per-ticker row count, source-bytes, parquet-bytes, and compression ratio,
then a total.

Usage:
    uv run python scripts/consolidate_options_to_parquet.py
    uv run python scripts/consolidate_options_to_parquet.py AAPL TSLA     # subset
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from loguru import logger
from tqdm import tqdm

DATA_DIR = Path("data")
OPTIONS_CSV_DIR = DATA_DIR / "options_alpha"
OPTIONS_PARQUET_DIR = DATA_DIR / "options_parquet"

# Explicit dtypes give tighter parquet output and avoid object-dtype columns for
# things that are numeric in reality.
DTYPES = {
    "contractID": "string",
    "symbol": "string",
    "expiration": "string",  # will convert to datetime after read
    "strike": "float32",
    "type": "string",
    "last": "float32",
    "mark": "float32",
    "bid": "float32",
    "bid_size": "Int32",
    "ask": "float32",
    "ask_size": "Int32",
    "volume": "Int64",
    "open_interest": "Int64",
    "date": "string",  # convert to datetime after read
    "implied_volatility": "float32",
    "delta": "float32",
    "gamma": "float32",
    "theta": "float32",
    "vega": "float32",
    "rho": "float32",
}


def folder_bytes(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def consolidate_ticker(ticker: str) -> dict | None:
    src_dir = OPTIONS_CSV_DIR / ticker
    if not src_dir.is_dir():
        return None
    csvs = sorted(src_dir.glob(f"{ticker}_options_*.csv"))
    if not csvs:
        return {"ticker": ticker, "files": 0, "rows": 0, "src_mb": 0, "parquet_mb": 0}

    dfs = []
    bad = 0
    for p in csvs:
        try:
            dfs.append(pd.read_csv(p, dtype=DTYPES))
        except Exception as e:
            bad += 1
            logger.warning(f"  {ticker} read fail on {p.name}: {e}")
            continue

    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if df.empty:
        return {
            "ticker": ticker,
            "files": len(csvs),
            "rows": 0,
            "src_mb": folder_bytes(src_dir) / 1e6,
            "parquet_mb": 0,
            "bad_files": bad,
        }

    df["expiration"] = pd.to_datetime(df["expiration"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Ensure no totally-null columns accidentally end up as object
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype("string")

    OPTIONS_PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    out = OPTIONS_PARQUET_DIR / f"{ticker}.parquet"
    df.to_parquet(out, index=False, compression="snappy")

    src_bytes = folder_bytes(src_dir)
    out_bytes = out.stat().st_size
    return {
        "ticker": ticker,
        "files": len(csvs),
        "rows": len(df),
        "src_mb": src_bytes / 1e6,
        "parquet_mb": out_bytes / 1e6,
        "ratio": src_bytes / out_bytes if out_bytes else 0.0,
        "bad_files": bad,
    }


def main():
    args = [a.upper() for a in sys.argv[1:]]
    all_tickers = sorted(d.name for d in OPTIONS_CSV_DIR.iterdir() if d.is_dir())
    tickers = args if args else all_tickers
    logger.info(f"Consolidating {len(tickers)} tickers -> {OPTIONS_PARQUET_DIR}")

    rows = []
    t0 = time.time()
    for t in tqdm(tickers, desc="consolidating"):
        r = consolidate_ticker(t)
        if r is not None:
            rows.append(r)
            tqdm.write(
                f"  {t:<6} files={r['files']:>5}  rows={r['rows']:>9,}  "
                f"src={r['src_mb']:>8,.1f} MB  parq={r['parquet_mb']:>6,.1f} MB  "
                f"ratio={r.get('ratio', 0):>5.1f}x"
            )

    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("Nothing consolidated.")
        return

    total_src = df["src_mb"].sum()
    total_parq = df["parquet_mb"].sum()
    logger.info(
        f"Done in {time.time() - t0:.1f}s. "
        f"src={total_src:,.0f} MB -> parquet={total_parq:,.0f} MB "
        f"(ratio={total_src / total_parq if total_parq else 0:.1f}x, "
        f"saved={total_src - total_parq:,.0f} MB)"
    )
    df.to_csv(OPTIONS_PARQUET_DIR / "_consolidation_summary.csv", index=False)


if __name__ == "__main__":
    main()
