from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.universe import HIGH_QUALITY_TICKERS  # noqa: E402
from app.yf_client import ChainFetch  # noqa: E402

DEFAULT_LIVE_DIR = ROOT.parent / "live" / "live"
DEFAULT_OUT = ROOT / "data" / "demo_snapshot.pkl"
DEFAULT_SNAPSHOT = "2026-04-20_21-07"
DEFAULT_EXPIRY = "2026-04-24"
DEFAULT_SOURCE_TZ = "Asia/Bangkok"
TARGET_TZ = "America/New_York"

CHAIN_COLUMNS = [
    "contractSymbol", "lastTradeDate", "strike", "lastPrice",
    "bid", "ask", "change", "percentChange", "volume",
    "openInterest", "impliedVolatility", "inTheMoney",
    "contractSize", "currency",
]


def _parse_taken_at(snapshot: str, source_tz: str) -> datetime:
    naive = datetime.strptime(snapshot, "%Y-%m-%d_%H-%M")
    local = naive.replace(tzinfo=ZoneInfo(source_tz))
    return local.astimezone(ZoneInfo(TARGET_TZ))


def _load_prices(prices_path: Path) -> pd.DataFrame:
    with prices_path.open() as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.set_index("date").rename(
        columns={"Open": "open", "High": "high", "Low": "low", "Close": "adjusted_close", "Volume": "volume"},
    )[["open", "high", "low", "adjusted_close", "volume"]].astype(float)
    df = df.dropna(subset=["open", "high", "low", "adjusted_close"])
    return df


def _load_chain(options_path: Path, expiry: str, spot: float) -> ChainFetch:
    with options_path.open() as f:
        d = json.load(f)
    ch = d["chains"][expiry]
    calls = pd.DataFrame(ch["calls"])
    puts = pd.DataFrame(ch["puts"])
    for col in CHAIN_COLUMNS:
        if col not in calls.columns:
            calls[col] = pd.NA
        if col not in puts.columns:
            puts[col] = pd.NA
    return ChainFetch(spot=float(spot), calls=calls, puts=puts)


def build(live_dir: Path, snapshot: str, expiry: str, source_tz: str, out_path: Path) -> None:
    opts_dir = live_dir / "options" / snapshot
    prx_dir = live_dir / "prices" / snapshot
    if not opts_dir.is_dir() or not prx_dir.is_dir():
        raise FileNotFoundError(f"snapshot {snapshot} not found under {live_dir}")

    snap_tickers = {p.stem for p in opts_dir.glob("*.json")}
    intersect = sorted(set(HIGH_QUALITY_TICKERS) & snap_tickers)
    logger.info(f"snapshot={snapshot}  expiry={expiry}  intersect_tickers={len(intersect)}")
    missing_universe = sorted(set(HIGH_QUALITY_TICKERS) - snap_tickers)
    if missing_universe:
        logger.info(f"universe tickers absent from snapshot: {missing_universe}")

    daily: dict[str, pd.DataFrame] = {}
    chains: dict[str, ChainFetch] = {}
    skipped: list[tuple[str, str]] = []

    for t in intersect:
        prx_path = prx_dir / f"{t}.json"
        opt_path = opts_dir / f"{t}.json"
        try:
            df = _load_prices(prx_path)
            spot = float(df["adjusted_close"].iloc[-1])
            chain = _load_chain(opt_path, expiry, spot)
        except Exception as exc:
            skipped.append((t, str(exc)))
            continue
        daily[t] = df
        chains[f"{t}:{expiry}"] = chain
        logger.info(f"{t}: prices={len(df)} rows, calls={len(chain.calls)}, puts={len(chain.puts)}, spot={spot:.2f}")

    if skipped:
        logger.warning(f"skipped {len(skipped)} tickers: {skipped}")

    taken_at = _parse_taken_at(snapshot, source_tz)
    snapshot_obj = {
        "taken_at": taken_at,
        "expiry": expiry,
        "daily": daily,
        "chains": chains,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        pickle.dump(snapshot_obj, f)
    size_mb = out_path.stat().st_size / 1024 / 1024
    logger.info(
        f"wrote {out_path}  taken_at={taken_at.isoformat()}  daily={len(daily)}  chains={len(chains)}  size={size_mb:.2f} MiB"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build demo snapshot pkl from app/live JSON dump")
    parser.add_argument("--live-dir", type=Path, default=DEFAULT_LIVE_DIR)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    parser.add_argument("--expiry", default=DEFAULT_EXPIRY)
    parser.add_argument("--source-tz", default=DEFAULT_SOURCE_TZ, help="timezone the snapshot folder name is in")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.live_dir, args.snapshot, args.expiry, args.source_tz, args.out)


if __name__ == "__main__":
    main()
