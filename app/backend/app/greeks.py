from __future__ import annotations

import math

RISK_FREE_RATE = 0.04  # approximation; OK for 1-week options


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_delta(spot: float, strike: float, iv: float, dte_days: int, option_type: str) -> float:
    """Black-Scholes delta (r=RISK_FREE_RATE, q=0).

    Returns 0.0 when inputs are degenerate. For calls, result is in [0, 1].
    For puts, result is in [-1, 0].
    """
    if iv <= 0 or dte_days <= 0 or spot <= 0 or strike <= 0 or not math.isfinite(iv):
        return 0.0
    T = dte_days / 365.0
    vol_sqrt_T = iv * math.sqrt(T)
    d1 = (math.log(spot / strike) + (RISK_FREE_RATE + 0.5 * iv * iv) * T) / vol_sqrt_T
    call_delta = _norm_cdf(d1)
    if option_type == "call":
        return call_delta
    return call_delta - 1.0
