"""Filter option contracts to actionable CSP/CC opportunities for a user.

Inputs:
  - cash_balance: how much liquid cash the user has (for CSP collateral)
  - positions: dict {ticker: shares_owned} (for CC writing)
  - target_weekly_yield_pct: minimum acceptable premium-as-%-of-collateral per week
  - tickers: optional override; defaults to the eligible 34

Output: a list of "opportunities" with all metrics needed for the UI table
and the recommendation engine.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable

from loguru import logger

from app.models import OptionContract
from app.utils.options import fetch_options
from app.utils.predict import eligible_tickers, predict_ticker


SHARES_PER_CONTRACT = 100
MIN_OPEN_INTEREST = 50    # liquidity floor
MIN_BID = 0.05            # ignore zero-bid contracts
DEFAULT_PRECISION = 0.5   # fallback when model has no backtest precision


def annual_yield_to_weekly(annual_pct: float) -> float:
    """Crude conversion: 26% annual ≈ 0.5% weekly. Linearized, not compounded."""
    return annual_pct / 52.0


def weekly_yield_pct(premium: float, collateral: float, days_to_expiry: int) -> float:
    """Premium / collateral, scaled to a 7-day basis (linearized for short DTE)."""
    if collateral <= 0 or days_to_expiry <= 0:
        return 0.0
    period_yield = premium / collateral * 100.0
    weeks = days_to_expiry / 7.0
    return period_yield / max(weeks, 0.5)


def _put_collateral(strike: float) -> float:
    """For an unleveraged CSP, capital tied up = strike * 100."""
    return strike * SHARES_PER_CONTRACT


def filter_csp_candidates(
    contracts: Iterable[OptionContract],
    cash_balance: float,
    target_weekly_yield_pct: float,
) -> list[dict]:
    """Filter PUTs the user can actually sell with their cash balance."""
    out = []
    for c in contracts:
        if c.option_type != "put":
            continue
        if c.bid < MIN_BID or c.open_interest < MIN_OPEN_INTEREST:
            continue
        # Only OTM puts (strike below spot) for "safe" CSP selling
        if c.strike >= c.spot:
            continue
        collateral = _put_collateral(c.strike)
        if collateral > cash_balance:
            continue
        weekly = weekly_yield_pct(c.bid, collateral, c.days_to_expiry)
        if weekly < target_weekly_yield_pct:
            continue
        moneyness_pct = (c.strike - c.spot) / c.spot * 100.0  # negative = OTM put
        out.append({
            "ticker": c.ticker,
            "strategy": "CSP",
            "option_type": "put",
            "strike": c.strike,
            "spot": c.spot,
            "expiration": c.expiration.isoformat(),
            "days_to_expiry": c.days_to_expiry,
            "bid": c.bid,
            "ask": c.ask,
            "mid_price": c.mid_price,
            "implied_volatility": c.implied_volatility,
            "open_interest": c.open_interest,
            "volume": c.volume,
            "collateral_required": round(collateral, 2),
            "premium_total": round(c.bid * SHARES_PER_CONTRACT, 2),
            "weekly_yield_pct": round(weekly, 3),
            "moneyness_pct": round(moneyness_pct, 2),
        })
    return out


def filter_cc_candidates(
    contracts: Iterable[OptionContract],
    positions: dict[str, int],
    target_weekly_yield_pct: float,
) -> list[dict]:
    """Filter CALLs the user can write against shares they already own."""
    out = []
    for c in contracts:
        if c.option_type != "call":
            continue
        if c.bid < MIN_BID or c.open_interest < MIN_OPEN_INTEREST:
            continue
        owned = positions.get(c.ticker, 0)
        if owned < SHARES_PER_CONTRACT:
            continue
        # Only OTM calls (strike above spot) for "safe" CC writing
        if c.strike <= c.spot:
            continue
        # CC collateral is the SHARES, value = spot * 100
        collateral = c.spot * SHARES_PER_CONTRACT
        weekly = weekly_yield_pct(c.bid, collateral, c.days_to_expiry)
        if weekly < target_weekly_yield_pct:
            continue
        moneyness_pct = (c.strike - c.spot) / c.spot * 100.0  # positive = OTM call
        n_contracts_writable = owned // SHARES_PER_CONTRACT
        out.append({
            "ticker": c.ticker,
            "strategy": "CC",
            "option_type": "call",
            "strike": c.strike,
            "spot": c.spot,
            "expiration": c.expiration.isoformat(),
            "days_to_expiry": c.days_to_expiry,
            "bid": c.bid,
            "ask": c.ask,
            "mid_price": c.mid_price,
            "implied_volatility": c.implied_volatility,
            "open_interest": c.open_interest,
            "volume": c.volume,
            "collateral_required": round(collateral, 2),
            "premium_total": round(c.bid * SHARES_PER_CONTRACT, 2),
            "weekly_yield_pct": round(weekly, 3),
            "moneyness_pct": round(moneyness_pct, 2),
            "n_contracts_writable": n_contracts_writable,
            "shares_owned": owned,
        })
    return out


def _predict_universe(tickers: Iterable[str]) -> dict[str, dict]:
    """Run the model once per unique ticker. Returns {ticker: prediction_dict}."""
    cache: dict[str, dict] = {}
    for t in {t.upper() for t in tickers}:
        try:
            cache[t] = predict_ticker(t)
        except Exception as e:
            logger.warning(f"prediction failed for {t}: {e}")
            cache[t] = {"ticker": t, "error": str(e), "warnings": []}
    return cache


def _enrich_with_model(opp: dict, pred: dict) -> dict:
    """Add p_favorable, signal, backtest_precision, edge_score to one opportunity.

    For CSPs (selling puts), favorable = stock holds or rises → use prob_up.
    For CCs (selling calls), favorable = stock holds or falls → use prob_down.
    """
    prob_up = pred.get("probability_up")
    threshold = pred.get("tuned_threshold")
    precision = pred.get("expected_test_precision")

    if prob_up is None or threshold is None:
        # Model unavailable or errored — flag the row but don't drop it.
        opp["model_p_favorable"] = None
        opp["model_signal"] = "UNKNOWN"
        opp["model_backtest_precision"] = None
        opp["edge_score"] = 0.0
        return opp

    if opp["strategy"] == "CSP":
        p_fav = float(prob_up)
    else:  # CC
        p_fav = 1.0 - float(prob_up)

    signal = "TRADE" if p_fav >= float(threshold) else "SKIP"
    prec = float(precision) if precision is not None else DEFAULT_PRECISION
    # Edge score: yield × directional confidence × sqrt(historical reliability).
    # sqrt damps the precision factor so a 60% precision model isn't punished too hard.
    edge = opp["weekly_yield_pct"] * p_fav * math.sqrt(max(prec, 0.0))

    opp["model_p_favorable"] = round(p_fav, 4)
    opp["model_signal"] = signal
    opp["model_backtest_precision"] = round(prec, 4)
    opp["edge_score"] = round(edge, 4)
    return opp


def scan_for_user(
    cash_balance: float,
    positions: dict[str, int],
    target_weekly_yield_pct: float,
    tickers: list[str] | None = None,
) -> dict:
    """Top-level scanner: returns CSP + CC opportunities ranked by edge score."""
    universe = [t.upper() for t in (tickers or eligible_tickers())]
    if not universe:
        return {"error": "no eligible tickers configured", "csps": [], "ccs": []}

    contracts = fetch_options(universe)

    csps = filter_csp_candidates(contracts, cash_balance, target_weekly_yield_pct)
    ccs = filter_cc_candidates(contracts, positions, target_weekly_yield_pct)

    # Run the model once per unique ticker that survived the filter.
    needed_tickers = {o["ticker"] for o in csps} | {o["ticker"] for o in ccs}
    predictions = _predict_universe(needed_tickers)

    for o in csps:
        _enrich_with_model(o, predictions.get(o["ticker"], {}))
    for o in ccs:
        _enrich_with_model(o, predictions.get(o["ticker"], {}))

    # Default sort: edge score (yield × directional confidence × reliability) desc.
    csps.sort(key=lambda x: -x["edge_score"])
    ccs.sort(key=lambda x: -x["edge_score"])

    n_trade = sum(
        1 for o in (*csps, *ccs) if o.get("model_signal") == "TRADE"
    )
    n_skip = sum(
        1 for o in (*csps, *ccs) if o.get("model_signal") == "SKIP"
    )

    return {
        "config": {
            "cash_balance": cash_balance,
            "target_weekly_yield_pct": target_weekly_yield_pct,
            "n_positions": len(positions),
            "universe_size": len(universe),
        },
        "summary": {
            "n_csp_candidates": len(csps),
            "n_cc_candidates": len(ccs),
            "n_contracts_scanned": len(contracts),
            "n_model_trade": n_trade,
            "n_model_skip": n_skip,
            "n_tickers_predicted": len(predictions),
        },
        "csps": csps,
        "ccs": ccs,
    }
