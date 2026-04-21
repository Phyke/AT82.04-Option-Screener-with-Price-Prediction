"""Generate a natural-language recommendation for one (contract, prediction) pair.

The template is deterministic — fills in slots based on:
  - The model's probability of an UP week
  - The contract's strategy (CSP/CC)
  - Strike vs spot, premium, capital required
  - Whether a recent split was detected (degrades confidence)

The output is a single multi-line string + a structured "verdict" enum so the
frontend can color-code the card.
"""

from __future__ import annotations

from typing import Literal

Verdict = Literal["STRONG_BUY", "BUY", "NEUTRAL", "AVOID", "STRONG_AVOID"]


def _verdict_csp(prob_up: float, threshold: float) -> Verdict:
    """For CSP selling: HIGH prob_up = good (stock won't drop below strike).

    Tiers expand symmetrically around the per-ticker tuned threshold.
    """
    if prob_up >= threshold + 0.10:
        return "STRONG_BUY"
    if prob_up >= threshold:
        return "BUY"
    if prob_up >= threshold - 0.05:
        return "NEUTRAL"
    if prob_up >= threshold - 0.15:
        return "AVOID"
    return "STRONG_AVOID"


def _verdict_cc(prob_up: float, threshold: float) -> Verdict:
    """For CC writing: LOW prob_up = good (stock won't rip past strike).

    Mirror of CSP logic. We use (1 - prob_up) for the "down/flat" probability.
    """
    prob_down = 1.0 - prob_up
    inv_threshold = 1.0 - threshold
    if prob_down >= inv_threshold + 0.10:
        return "STRONG_BUY"
    if prob_down >= inv_threshold:
        return "BUY"
    if prob_down >= inv_threshold - 0.05:
        return "NEUTRAL"
    if prob_down >= inv_threshold - 0.15:
        return "AVOID"
    return "STRONG_AVOID"


VERDICT_HEADLINE = {
    "STRONG_BUY":   "STRONG SELL — model confidence very high.",
    "BUY":          "SELL — model confidence above threshold.",
    "NEUTRAL":      "MARGINAL — close to threshold, consider sizing down or skipping.",
    "AVOID":        "AVOID — model leans against this trade.",
    "STRONG_AVOID": "DO NOT TRADE — model strongly against.",
}

VERDICT_COLOR = {
    "STRONG_BUY":   "#16a34a",
    "BUY":          "#65a30d",
    "NEUTRAL":      "#ca8a04",
    "AVOID":        "#dc2626",
    "STRONG_AVOID": "#991b1b",
}


def _format_dollars(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if abs(x) >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


def build_recommendation(contract: dict, prediction: dict) -> dict:
    """Combine a screener contract dict + a predict_ticker output into a card."""
    strategy = contract["strategy"]
    ticker = contract["ticker"]
    strike = contract["strike"]
    spot = contract["spot"]
    bid = contract["bid"]
    dte = contract["days_to_expiry"]
    premium_total = contract["premium_total"]
    collateral = contract["collateral_required"]
    weekly_y = contract["weekly_yield_pct"]
    moneyness = contract["moneyness_pct"]
    expiration = contract["expiration"]

    prob_up = prediction.get("probability_up", 0.5)
    prob_down = prediction.get("probability_down", 1.0 - prob_up)
    threshold = prediction.get("tuned_threshold", 0.625)
    expected_prec = prediction.get("expected_test_precision")

    if strategy == "CSP":
        verdict = _verdict_csp(prob_up, threshold)
        favorable_prob = prob_up
        favorable_label = "Friday close ≥ Monday close"
    else:  # CC
        verdict = _verdict_cc(prob_up, threshold)
        favorable_prob = prob_down
        favorable_label = "Friday close ≤ Monday close"

    headline = VERDICT_HEADLINE[verdict]
    color = VERDICT_COLOR[verdict]

    # Capital efficiency line
    if strategy == "CSP":
        capital_line = (
            f"Selling this put ties up {_format_dollars(collateral)} of cash as collateral. "
            f"You'd collect {_format_dollars(premium_total)} in premium upfront — "
            f"a {weekly_y:.2f}% weekly yield on collateral."
        )
        risk_line = (
            f"If {ticker} closes below ${strike:.2f} by {expiration[:10]} (DTE={dte}), "
            f"you'll be assigned 100 shares at ${strike:.2f} — currently ${spot - strike:.2f} "
            f"below market ({-moneyness:.1f}% OTM cushion)."
        )
    else:
        n_writable = contract.get("n_contracts_writable", 1)
        capital_line = (
            f"You own {contract.get('shares_owned', n_writable * 100)} shares of {ticker}, "
            f"enough to write {n_writable} contract{'s' if n_writable != 1 else ''}. "
            f"Each contract collects {_format_dollars(premium_total)} in premium upfront — "
            f"a {weekly_y:.2f}% weekly yield on the share value."
        )
        risk_line = (
            f"If {ticker} closes above ${strike:.2f} by {expiration[:10]} (DTE={dte}), "
            f"your shares will be called away at ${strike:.2f} — currently ${strike - spot:.2f} "
            f"above market ({moneyness:.1f}% OTM cushion). You'd give up further upside."
        )

    # Model verdict block
    model_line = (
        f"Model probability of {favorable_label}: {favorable_prob*100:.1f}% "
        f"(threshold for this ticker: {threshold*100:.1f}%)."
    )
    if expected_prec is not None:
        model_line += (
            f" Backtest precision at this threshold: {expected_prec*100:.0f}%."
        )

    # Warnings (e.g., recent split)
    warning_lines = []
    for w in prediction.get("warnings", []) or []:
        warning_lines.append(f"⚠️ {w.get('message', 'warning')}")

    body = "\n\n".join([
        f"**{headline}**",
        capital_line,
        risk_line,
        model_line,
        *warning_lines,
    ])

    return {
        "ticker": ticker,
        "strategy": strategy,
        "verdict": verdict,
        "headline": headline,
        "color": color,
        "body": body,
        "metrics": {
            "favorable_probability": round(favorable_prob, 4),
            "tuned_threshold": round(threshold, 4),
            "weekly_yield_pct": weekly_y,
            "premium_total": premium_total,
            "collateral_required": collateral,
            "moneyness_pct": moneyness,
            "days_to_expiry": dte,
        },
        "warnings": prediction.get("warnings", []),
    }
