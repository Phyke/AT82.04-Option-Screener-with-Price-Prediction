from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.universe import is_universe_ticker

Policy = Literal["strict", "safe", "aggressive"]
ToleranceMode = Literal["research", "tight"]
OptionType = Literal["call", "put"]
IVTier = Literal["low", "mid", "high"]


class Holding(BaseModel):
    ticker: str
    shares: int = Field(gt=0)
    avg_cost: float = Field(gt=0)

    @field_validator("ticker")
    @classmethod
    def uppercase_and_validate(cls, v: str) -> str:
        upper = v.upper()
        if not is_universe_ticker(upper):
            raise ValueError(f"{upper} is not in the universe")
        return upper


class UniverseResponse(BaseModel):
    tickers: list[str]
    policies: list[str]
    yield_targets: list[float]
    expiry: date
    as_of: datetime


class ScreenerRequest(BaseModel):
    cash: float = Field(ge=0)
    holdings: list[Holding] = Field(default_factory=list)
    policy: Policy
    yield_target: float = Field(gt=0, le=0.1)
    tolerance_mode: ToleranceMode = "research"
    iv_tiers: list[IVTier] | None = None


class CCPick(BaseModel):
    ticker: str
    type: Literal["call"] = "call"
    strike: float
    spot: float
    bid: float
    ask: float
    mark: float
    implied_volatility: float
    delta: float
    open_interest: int
    volume: int
    yield_actual: float
    yield_gap: float
    premium_dollars: float
    shares_required: int
    max_contracts: int
    cost_basis_gap: float
    below_cost_basis: bool
    iv_tier: IVTier | None = None


class CSPPick(BaseModel):
    ticker: str
    type: Literal["put"] = "put"
    strike: float
    spot: float
    bid: float
    ask: float
    mark: float
    implied_volatility: float
    delta: float
    open_interest: int
    volume: int
    yield_actual: float
    yield_gap: float
    premium_dollars: float
    collateral_required: float
    max_contracts: int
    fits_cash: bool
    iv_tier: IVTier | None = None


class ResearchHint(BaseModel):
    policy: Literal["strict", "safe", "aggressive", "skip"]
    total_return: float
    sharpe: float
    stable: bool
    alt_policy_2020: str | None = None
    yield_rounded: float


class SkippedTicker(BaseModel):
    ticker: str
    reason: str


class ScreenerResponse(BaseModel):
    expiry: date
    as_of: datetime
    upstream_healthy: bool
    cc_picks: list[CCPick]
    csp_picks: list[CSPPick]
    skipped: list[SkippedTicker]
    spots: dict[str, float]
    research_by_tier: dict[str, ResearchHint] = Field(default_factory=dict)


class ContractRequest(BaseModel):
    ticker: str
    strike: float
    type: OptionType

    @field_validator("ticker")
    @classmethod
    def uppercase_and_validate(cls, v: str) -> str:
        upper = v.upper()
        if not is_universe_ticker(upper):
            raise ValueError(f"{upper} is not in the universe")
        return upper


class PredictRequest(BaseModel):
    contracts: list[ContractRequest]


class Prediction(BaseModel):
    ticker: str
    strike: float
    type: OptionType
    pred_friday_close: float | None = None
    spot_used: float | None = None
    error: str | None = None


class PredictResponse(BaseModel):
    as_of: datetime
    model_input_date: date
    predictions: list[Prediction]
