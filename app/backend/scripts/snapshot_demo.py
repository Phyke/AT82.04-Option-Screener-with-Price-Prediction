from __future__ import annotations

import argparse
import asyncio
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

from app.calendar import current_expiry, market_now  # noqa: E402
from app.universe import HIGH_QUALITY_TICKERS  # noqa: E402
from app.yf_client import _fetch_chain_sync, _fetch_history_sync  # noqa: E402


DEFAULT_OUT = ROOT / "data" / "demo_snapshot.pkl"


async def build_snapshot(out_path: Path, concurrency: int = 8) -> None:
    expiry = current_expiry()
    expiry_s = expiry.isoformat()
    taken_at = market_now()
    tickers = list(HIGH_QUALITY_TICKERS)

    sem = asyncio.Semaphore(concurrency)

    async def fetch_daily(t: str) -> tuple[str, object]:
        async with sem:
            try:
                df = await asyncio.to_thread(_fetch_history_sync, t)
                logger.info(f"daily {t}: {len(df)} rows")
                return t, df
            except Exception as exc:
                logger.warning(f"daily {t} failed: {exc}")
                return t, None

    async def fetch_chain(t: str) -> tuple[str, object]:
        async with sem:
            try:
                chain = await asyncio.to_thread(_fetch_chain_sync, t, expiry_s)
                logger.info(f"chain {t}: calls={len(chain.calls)} puts={len(chain.puts)}")
                return t, chain
            except Exception as exc:
                logger.warning(f"chain {t} failed: {exc}")
                return t, None

    logger.info(f"taken_at={taken_at}  expiry={expiry_s}")
    logger.info(f"fetching daily history ({len(tickers) + 1} symbols)")
    daily_results = await asyncio.gather(*[fetch_daily(t) for t in tickers + ["SPY"]])
    daily = {t: df for t, df in daily_results if df is not None}

    logger.info(f"fetching option chains ({len(tickers)} tickers)")
    chain_results = await asyncio.gather(*[fetch_chain(t) for t in tickers])
    chains = {f"{t}:{expiry_s}": c for t, c in chain_results if c is not None}

    snapshot = {
        "taken_at": taken_at,
        "expiry": expiry_s,
        "daily": daily,
        "chains": chains,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        pickle.dump(snapshot, f)
    size_mb = out_path.stat().st_size / 1024 / 1024
    logger.info(
        f"wrote snapshot -> {out_path}  "
        f"daily={len(daily)}  chains={len(chains)}  size={size_mb:.2f} MiB"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot yfinance data for demo mode")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output pickle path")
    parser.add_argument("--concurrency", type=int, default=8, help="parallel yfinance fetches")
    args = parser.parse_args()
    asyncio.run(build_snapshot(args.out, args.concurrency))


if __name__ == "__main__":
    main()
