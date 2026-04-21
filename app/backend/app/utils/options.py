from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from loguru import logger

from app.models import OptionContract
from app.utils.market_data import fetch_spot


# ── Time helpers ──────────────────────────────────────────────────────────────

def end_of_next_month_utc(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_next = (first_this + timedelta(days=32)).replace(day=1)
    return ((first_next + timedelta(days=32)).replace(day=1)) - timedelta(seconds=1)


# ── yfinance helpers ──────────────────────────────────────────────────────────

def _valid_expirations(stock: yf.Ticker, deadline: datetime) -> list[str]:
    out = []
    for exp_str in stock.options or []:
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if exp_date <= deadline:
            out.append(exp_str)
    return out


def _option_frames(stock: yf.Ticker, expirations: list[str]) -> list[pd.DataFrame]:
    frames = []
    for exp in expirations:
        try:
            chain = stock.option_chain(exp)
        except Exception as exc:
            logger.warning(f"option_chain failed for {stock.ticker} {exp}: {exc!s}")
            continue
        for df, opt_type in ((chain.calls, "call"), (chain.puts, "put")):
            if not df.empty:
                tagged = df.copy()
                tagged["expiration"] = exp
                tagged["option_type"] = opt_type
                frames.append(tagged)
    return frames


def _fetch_chain(ticker: str, deadline: datetime) -> pd.DataFrame | None:
    try:
        stock = yf.Ticker(ticker)
    except Exception as exc:
        logger.error(f"Ticker init failed for {ticker}: {exc!s}")
        return None

    expirations = _valid_expirations(stock, deadline)
    if not expirations:
        logger.warning(f"No options expiring by {deadline.date()} for {ticker}")
        return None

    frames = _option_frames(stock, expirations)
    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    required = {"bid", "ask", "strike", "expiration", "option_type"}
    if not required.issubset(df.columns):
        logger.warning(f"Missing required columns for {ticker}")
        return None

    return df.dropna(subset=["bid", "ask", "strike"])


# ── Row mapping ───────────────────────────────────────────────────────────────

def _safe_float(row: pd.Series, key: str) -> float:
    val = row.get(key)
    return float(val) if pd.notna(val) else 0.0


def _compute_mid(bid: float, ask: float) -> float:
    b = 0.0 if not math.isfinite(bid) else max(0.0, bid)
    a = float(ask) if math.isfinite(ask) and ask > 0 else b
    return (b + a) / 2.0


def _build_contract(ticker: str, spot: float, row: pd.Series) -> OptionContract | None:
    try:
        exp_date = datetime.strptime(str(row["expiration"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_to_expiry = (exp_date - datetime.now(timezone.utc)).days
        if days_to_expiry < 0:
            return None

        bid = float(row["bid"])
        ask = float(row["ask"])

        return OptionContract(
            ticker=ticker,
            spot=spot,
            strike=float(row["strike"]),
            expiration=exp_date,
            option_type=row["option_type"],
            bid=bid,
            ask=ask,
            mid_price=_compute_mid(bid, ask),
            last_price=_safe_float(row, "lastPrice"),
            volume=_safe_float(row, "volume"),
            open_interest=_safe_float(row, "openInterest"),
            implied_volatility=_safe_float(row, "impliedVolatility"),
            in_the_money=bool(row.get("inTheMoney", False)),
            days_to_expiry=days_to_expiry,
        )
    except Exception as exc:
        logger.debug(f"Skipping row for {ticker}: {exc!s}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_options(tickers: list[str]) -> list[OptionContract]:
    """Fetch option contracts for the given tickers, sorted by expiration then strike."""
    deadline = end_of_next_month_utc()
    logger.info(f"Scanning options up to {deadline.date()}")

    contracts: list[OptionContract] = []

    for ticker in tickers:
        logger.info(f"Processing {ticker}...")
        spot = fetch_spot(ticker)
        if spot is None:
            logger.warning(f"Could not get spot price for {ticker}, skipping")
            continue

        chain = _fetch_chain(ticker, deadline)
        if chain is None or chain.empty:
            continue

        for _, row in chain.iterrows():
            contract = _build_contract(ticker, spot, row)
            if contract is not None:
                contracts.append(contract)

    contracts.sort(key=lambda c: (c.expiration, c.strike))
    return contracts
