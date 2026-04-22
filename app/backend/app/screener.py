from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Awaitable, Callable

import pandas as pd
from loguru import logger

from app.calendar import current_expiry, market_now
from app.config import settings
from app.greeks import bs_delta
from app.research import research_for, tier_for
from app.schemas import CCPick, CSPPick, IVTier, Policy, ResearchHint, ScreenerResponse, SkippedTicker, ToleranceMode
from app.universe import HIGH_QUALITY_TICKERS
from app.yf_client import ChainFetch, get_option_chain

ChainProvider = Callable[[str, str], Awaitable[ChainFetch]]

MIN_BID = 0.05
MIN_OPEN_INTEREST = 10
YIELD_MATCH_REL = 0.25
YIELD_MATCH_ABS_CAP = 0.005  # 0.5 percentage points


def _yield_tolerance(yield_target: float, mode: ToleranceMode) -> float:
    rel = yield_target * YIELD_MATCH_REL
    if mode == "tight":
        return min(rel, YIELD_MATCH_ABS_CAP)
    return rel


@dataclass
class TickerState:
    ticker: str
    shares: int
    avg_cost: float


def _clean_chain(side: pd.DataFrame) -> pd.DataFrame:
    df = side.copy()
    for col in ("bid", "ask", "lastPrice", "strike", "openInterest", "volume", "impliedVolatility"):
        if col not in df.columns:
            df[col] = 0.0
    df["bid"] = df["bid"].fillna(0.0)
    df["ask"] = df["ask"].fillna(0.0)
    df["lastPrice"] = df["lastPrice"].fillna(0.0)
    df["openInterest"] = df["openInterest"].fillna(0).astype(int)
    df["volume"] = df["volume"].fillna(0).astype(int)
    df["impliedVolatility"] = df["impliedVolatility"].fillna(0.0)
    mark_mid = (df["bid"] + df["ask"]) / 2
    df["mark"] = mark_mid.where((df["bid"] > 0) & (df["ask"] > 0), df["lastPrice"])
    df = df[(df["bid"] >= MIN_BID) & (df["openInterest"] >= MIN_OPEN_INTEREST)]
    return df.reset_index(drop=True)


def _closest_to_target(df: pd.DataFrame, yield_target: float) -> dict:
    idx = (df["yield_actual"] - yield_target).abs().idxmin()
    return df.loc[idx].to_dict()


def _pick_csp(
    puts: pd.DataFrame,
    spot: float,
    cash: float,
    yield_target: float,
    tolerance_mode: ToleranceMode,
) -> tuple[dict | None, str | None]:
    otm = puts[puts["strike"] < spot].copy()
    if otm.empty:
        return None, "no OTM puts"
    otm["yield_actual"] = otm["mark"] / otm["strike"]
    otm["collateral"] = otm["strike"] * 100
    affordable = otm[otm["collateral"] <= cash]
    if affordable.empty:
        return None, "insufficient cash for any OTM strike"
    tol = _yield_tolerance(yield_target, tolerance_mode)
    within = affordable[(affordable["yield_actual"] - yield_target).abs() <= tol]
    if within.empty:
        return None, f"no contract within {tol * 100:.2f}pp of yield target"
    return _closest_to_target(within, yield_target), None


def _pick_cc(
    calls: pd.DataFrame,
    spot: float,
    avg_cost: float,
    yield_target: float,
    policy: Policy,
    tolerance_mode: ToleranceMode,
) -> tuple[dict | None, str | None]:
    otm = calls[calls["strike"] > spot].copy()
    if otm.empty:
        return None, "no OTM calls"
    otm["yield_actual"] = otm["mark"] / spot
    tol = _yield_tolerance(yield_target, tolerance_mode)
    within = otm[(otm["yield_actual"] - yield_target).abs() <= tol]
    if policy == "aggressive":
        if within.empty:
            return None, f"no contract within {tol * 100:.2f}pp of yield target"
        return _closest_to_target(within, yield_target), None
    above = within[within["strike"] >= avg_cost]
    if policy == "strict":
        if above.empty:
            return None, "strict policy: no strike >= cost basis"
        return _closest_to_target(above, yield_target), None
    if policy == "safe":
        if not above.empty:
            return _closest_to_target(above, yield_target), None
        fallback = otm.sort_values("strike", ascending=False)
        if fallback.empty:
            return None, "safe policy: no OTM strike passes gates"
        return fallback.iloc[0].to_dict(), None
    return None, f"unknown policy {policy}"


def _pack_cc(ticker: str, row: dict, spot: float, avg_cost: float, shares: int, yield_target: float, dte_days: int) -> CCPick:
    strike = float(row["strike"])
    bid = float(row["bid"])
    iv = float(row["impliedVolatility"])
    yield_actual = float(row["yield_actual"])
    return CCPick(
        ticker=ticker,
        strike=strike,
        spot=spot,
        bid=bid,
        ask=float(row["ask"]),
        mark=float(row["mark"]),
        implied_volatility=iv,
        delta=round(bs_delta(spot, strike, iv, dte_days, "call"), 4),
        open_interest=int(row["openInterest"]),
        volume=int(row["volume"]),
        yield_actual=yield_actual,
        yield_gap=yield_actual - yield_target,
        premium_dollars=round(bid * 100, 2),
        shares_required=100,
        max_contracts=shares // 100,
        cost_basis_gap=round(strike - avg_cost, 4),
        below_cost_basis=strike < avg_cost,
        iv_tier=tier_for(ticker),
    )


def _pack_csp(ticker: str, row: dict, spot: float, cash: float, yield_target: float, dte_days: int) -> CSPPick:
    strike = float(row["strike"])
    bid = float(row["bid"])
    iv = float(row["impliedVolatility"])
    yield_actual = float(row["yield_actual"])
    collateral = strike * 100
    return CSPPick(
        ticker=ticker,
        strike=strike,
        spot=spot,
        bid=bid,
        ask=float(row["ask"]),
        mark=float(row["mark"]),
        implied_volatility=iv,
        delta=round(bs_delta(spot, strike, iv, dte_days, "put"), 4),
        open_interest=int(row["openInterest"]),
        volume=int(row["volume"]),
        yield_actual=yield_actual,
        yield_gap=yield_actual - yield_target,
        premium_dollars=round(bid * 100, 2),
        collateral_required=round(collateral, 2),
        max_contracts=math.floor(cash / collateral) if collateral > 0 else 0,
        fits_cash=collateral <= cash,
        iv_tier=tier_for(ticker),
    )


async def _screen_one(
    ticker: str,
    holdings: dict[str, TickerState],
    cash: float,
    policy: Policy,
    yield_target: float,
    tolerance_mode: ToleranceMode,
    expiry: str,
    dte_days: int,
    sem: asyncio.Semaphore,
    chain_provider: ChainProvider,
) -> tuple[CCPick | None, CSPPick | None, SkippedTicker | None, float | None]:
    async with sem:
        try:
            chain: ChainFetch = await chain_provider(ticker, expiry)
        except Exception as exc:
            logger.warning(f"{ticker}: upstream fetch failed: {exc}")
            return None, None, SkippedTicker(ticker=ticker, reason="upstream fetch failed"), None

        spot = float(chain.spot)
        if not math.isfinite(spot) or spot <= 0:
            return None, None, SkippedTicker(ticker=ticker, reason="no spot price available"), None

        state = holdings.get(ticker)
        holding_100_plus = state is not None and state.shares >= 100

        if holding_100_plus:
            calls = _clean_chain(chain.calls)
            if calls.empty:
                return None, None, SkippedTicker(ticker=ticker, reason="no weekly Friday chain"), spot
            assert state is not None
            pick, reason = _pick_cc(calls, spot, state.avg_cost, yield_target, policy, tolerance_mode)
            if pick is None:
                return None, None, SkippedTicker(ticker=ticker, reason=reason or "no CC pick"), spot
            return _pack_cc(ticker, pick, spot, state.avg_cost, state.shares, yield_target, dte_days), None, None, spot

        puts = _clean_chain(chain.puts)
        if puts.empty:
            return None, None, SkippedTicker(ticker=ticker, reason="no weekly Friday chain"), spot
        pick, reason = _pick_csp(puts, spot, cash, yield_target, tolerance_mode)
        if pick is None:
            return None, None, SkippedTicker(ticker=ticker, reason=reason or "no CSP pick"), spot
        return None, _pack_csp(ticker, pick, spot, cash, yield_target, dte_days), None, spot


async def run_screener(
    cash: float,
    holdings_list: list[TickerState],
    policy: Policy,
    yield_target: float,
    tolerance_mode: ToleranceMode,
    iv_tiers: list[IVTier] | None = None,
    *,
    universe: list[str] | None = None,
    expiry: date | None = None,
    as_of: datetime | None = None,
    chain_provider: ChainProvider = get_option_chain,
) -> ScreenerResponse:
    if expiry is None:
        expiry = current_expiry()
    if as_of is None:
        as_of = market_now()
    expiry_s = expiry.isoformat()
    dte_days = max(1, (expiry - as_of.date()).days)
    holdings = {h.ticker: h for h in holdings_list}
    sem = asyncio.Semaphore(settings.YF_CONCURRENCY)

    base_universe = universe if universe is not None else HIGH_QUALITY_TICKERS
    selected_tiers = set(iv_tiers) if iv_tiers else None
    universe = [
        t for t in base_universe
        if selected_tiers is None or tier_for(t) in selected_tiers
    ]

    tasks = [
        _screen_one(t, holdings, cash, policy, yield_target, tolerance_mode, expiry_s, dte_days, sem, chain_provider)
        for t in universe
    ]
    results = await asyncio.gather(*tasks)

    cc_picks: list[CCPick] = []
    csp_picks: list[CSPPick] = []
    skipped: list[SkippedTicker] = []
    spots: dict[str, float] = {}
    for ticker, (cc, csp, sk, spot) in zip(universe, results):
        if cc is not None:
            cc_picks.append(cc)
        if csp is not None:
            csp_picks.append(csp)
        if sk is not None:
            skipped.append(sk)
        if spot is not None:
            spots[ticker] = spot

    cc_picks.sort(key=lambda p: (-p.yield_actual, -p.open_interest))
    csp_picks.sort(key=lambda p: (-p.yield_actual, -p.open_interest))

    upstream_healthy = any(r[0] is not None or r[1] is not None for r in results)

    tiers_to_hint = selected_tiers if selected_tiers is not None else {"low", "mid", "high"}
    research_by_tier: dict[str, ResearchHint] = {}
    for t in tiers_to_hint:
        hint = research_for(t, yield_target)  # type: ignore[arg-type]
        if hint is not None:
            research_by_tier[t] = ResearchHint(**hint)

    return ScreenerResponse(
        expiry=expiry,
        as_of=as_of,
        upstream_healthy=upstream_healthy,
        cc_picks=cc_picks,
        csp_picks=csp_picks,
        skipped=skipped,
        spots=spots,
        research_by_tier=research_by_tier,
    )
