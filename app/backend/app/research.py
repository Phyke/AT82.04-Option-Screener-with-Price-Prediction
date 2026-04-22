"""Research-derived constants for the screener.

Source: experiments/output/03_weekly_strategy_labels/strategy_labels.parquet
and experiments/output/06_options_income_strategies_backtesting/.

Regenerate with scripts/sync_research.py if the experiments are re-run.
"""

from __future__ import annotations

from typing import Literal

Tier = Literal["low", "mid", "high"]
Policy = Literal["strict", "safe", "aggressive", "skip"]

# Tercile cutoffs on each ticker's median IV across all historical trades.
IV_TIER_LOW_MAX: float = 0.5319
IV_TIER_MID_MAX: float = 1.1044

# 35-ticker HQ universe classified into IV terciles.
# median_iv column kept as a comment for traceability.
IV_TIER: dict[str, Tier] = {
    # Low-IV (<0.53)
    "MSFT":  "low",   # 0.3368
    "GOOGL": "low",   # 0.3758
    "AAPL":  "low",   # 0.3856
    "AMZN":  "low",   # 0.4149
    "META":  "low",   # 0.4246
    "TSM":   "low",   # 0.4344
    "QCOM":  "low",   # 0.4441
    "AVGO":  "low",   # 0.4539
    "NFLX":  "low",   # 0.4539
    "AMAT":  "low",   # 0.5027
    "DELL":  "low",   # 0.5222
    # Mid-IV (0.53-1.10)
    "LRCX":  "mid",   # 0.5319
    "INTC":  "mid",   # 0.5319
    "NVDA":  "mid",   # 0.5710
    "AMD":   "mid",   # 0.5905
    "TSLA":  "mid",   # 0.7075
    "PLTR":  "mid",   # 0.7173
    "RBLX":  "mid",   # 0.7661
    "SMCI":  "mid",   # 0.8734
    "COIN":  "mid",   # 0.8831
    "BULL":  "mid",   # 1.0149
    "RKLB":  "mid",   # 1.0197
    "QS":    "mid",   # 1.0588
    # High-IV (>1.10)
    "GME":   "high",  # 1.1173
    "IONQ":  "high",  # 1.1271
    "UUUU":  "high",  # 1.1466
    "SMR":   "high",  # 1.1856
    "SOUN":  "high",  # 1.2246
    "TLRY":  "high",  # 1.2441
    "RGTI":  "high",  # 1.2441
    "APLD":  "high",  # 1.2636
    "QBTS":  "high",  # 1.2734
    "OKLO":  "high",  # 1.2734
    "QUBT":  "high",  # 1.3319
    "BBAI":  "high",  # 1.4587
}


class ResearchCell:
    __slots__ = ("policy", "total_return", "sharpe")

    def __init__(self, policy: Policy, total_return: float, sharpe: float) -> None:
        self.policy: Policy = policy
        self.total_return: float = total_return
        self.sharpe: float = sharpe

    def as_dict(self) -> dict:
        return {"policy": self.policy, "total_return": self.total_return, "sharpe": self.sharpe}


# Values read from experiments/output/06_.../since_2024/recommended_policy_matrix.png.
# total_return is full-window cumulative; sharpe is annualized on weekly returns.
# "skip" means the research cell winner was hold-idle / liquidate, i.e. don't
# sell a CC this week; the app surfaces this as a warning rather than a policy.
RESEARCH_SINCE_2024: dict[tuple[Tier, float], ResearchCell] = {
    ("low",  0.01): ResearchCell("aggressive", 0.83, 4.48),
    ("low",  0.02): ResearchCell("strict",     0.37, 1.39),
    ("low",  0.03): ResearchCell("strict",     0.22, 1.37),
    ("low",  0.04): ResearchCell("strict",     0.13, 1.32),
    ("low",  0.05): ResearchCell("strict",     0.09, 1.87),
    ("mid",  0.01): ResearchCell("aggressive", 1.15, 3.27),
    ("mid",  0.02): ResearchCell("strict",     1.18, 3.15),
    ("mid",  0.03): ResearchCell("aggressive", 1.01, 3.90),
    ("mid",  0.04): ResearchCell("safe",       0.69, 2.53),
    ("mid",  0.05): ResearchCell("safe",       0.35, 1.85),
    ("high", 0.01): ResearchCell("strict",     0.48, 0.94),
    ("high", 0.02): ResearchCell("strict",     0.91, 1.77),
    ("high", 0.03): ResearchCell("strict",     1.09, 1.75),
    ("high", 0.04): ResearchCell("strict",     0.99, 1.57),
    ("high", 0.05): ResearchCell("strict",     0.97, 1.63),
}

# Full history (2020-2026) - used as a second opinion for regime robustness.
RESEARCH_SINCE_2020: dict[tuple[Tier, float], ResearchCell] = {
    ("low",  0.01): ResearchCell("aggressive", 2.19, 3.55),
    ("low",  0.02): ResearchCell("strict",     1.18, 1.66),
    ("low",  0.03): ResearchCell("strict",     0.79, 1.80),
    ("low",  0.04): ResearchCell("strict",     0.37, 1.04),
    ("low",  0.05): ResearchCell("skip",       0.22, 1.04),   # hold-idle winner
    ("mid",  0.01): ResearchCell("aggressive", 2.90, 3.09),
    ("mid",  0.02): ResearchCell("aggressive", 2.97, 2.86),
    ("mid",  0.03): ResearchCell("aggressive", 2.49, 3.07),
    ("mid",  0.04): ResearchCell("aggressive", 1.53, 2.23),
    ("mid",  0.05): ResearchCell("safe",       1.15, 2.02),
    ("high", 0.01): ResearchCell("strict",     0.80, 0.85),
    ("high", 0.02): ResearchCell("aggressive", 1.68, 1.90),
    ("high", 0.03): ResearchCell("strict",     1.53, 1.27),
    ("high", 0.04): ResearchCell("strict",     1.83, 1.33),
    ("high", 0.05): ResearchCell("strict",     2.25, 1.53),
}


def tier_for(ticker: str) -> Tier | None:
    return IV_TIER.get(ticker.upper())


def _nearest_yield(yield_target: float) -> float:
    # Research grid is 1%..5% in 1% steps. Snap the app's finer grid
    # (0.5% increments) to the closest researched bucket.
    return max(0.01, min(0.05, round(yield_target * 100) / 100))


def research_for(tier: Tier, yield_target: float) -> dict | None:
    """Return recommendation with regime-disagreement flag.

    Output keys: policy, total_return, sharpe, stable (bool), alt_policy_2020 (str|None).
    stable=True when since_2024 and since_2020 windows pick the same policy.
    """
    y = _nearest_yield(yield_target)
    recent = RESEARCH_SINCE_2024.get((tier, y))
    full = RESEARCH_SINCE_2020.get((tier, y))
    if recent is None:
        return None
    stable = full is not None and full.policy == recent.policy
    return {
        "policy": recent.policy,
        "total_return": recent.total_return,
        "sharpe": recent.sharpe,
        "stable": stable,
        "alt_policy_2020": None if stable or full is None else full.policy,
        "yield_rounded": y,
    }
