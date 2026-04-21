from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OptionType = Literal["call", "put"]


class OptionContract(BaseModel):
    ticker: str
    spot: float
    strike: float
    expiration: datetime
    option_type: OptionType
    bid: float
    ask: float
    mid_price: float
    last_price: float
    volume: float
    open_interest: float
    implied_volatility: float
    days_to_expiry: int = Field(ge=0)
    in_the_money: bool

    @field_validator("expiration")
    @classmethod
    def _ensure_tzaware(cls, v: datetime) -> datetime:
        return v if v.tzinfo is not None else v.replace(tzinfo=timezone.utc)


class OptionsRequest(BaseModel):
    tickers: list[str]


class ScanRequest(BaseModel):
    cash_balance: float = Field(ge=0)
    positions: dict[str, int] = Field(default_factory=dict)
    target_weekly_yield_pct: float = Field(ge=0, le=20)
    tickers: list[str] | None = None  # defaults to eligible 34


class RecommendRequest(BaseModel):
    contract: dict
    ticker: str
