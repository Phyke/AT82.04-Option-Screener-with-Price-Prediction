from __future__ import annotations

import math

import pandas as pd
import yfinance as yf
from loguru import logger


def fetch_spot(ticker: str) -> float | None:
    """Return the most current tradable price for a ticker, trying multiple yfinance APIs."""
    try:
        t = yf.Ticker(ticker)

        fi = getattr(t, "fast_info", None)
        if fi:
            for key in ("last_price", "lastPrice", "regularMarketPrice", "last_traded_price"):
                try:
                    val = float(fi.get(key))
                    if math.isfinite(val) and val > 0:
                        return val
                except Exception:
                    pass

        for kwargs in (
            {"period": "1d", "interval": "1m", "prepost": True},
            {"period": "1d"},
        ):
            try:
                hist = t.history(**kwargs)
                if not hist.empty:
                    val = float(hist["Close"].iloc[-1])
                    if math.isfinite(val) and val > 0:
                        return val
            except Exception:
                pass

    except Exception as exc:
        logger.error(f"fetch_spot failed for {ticker}: {exc!s}")

    return None


def fetch_stock_history(ticker: str, period: str = "6mo", interval: str = "1d") -> list[dict]:
    """Return OHLCV candles formatted for lightweight-charts."""
    try:
        hist = yf.Ticker(ticker).history(period=period, interval=interval)
        if hist.empty:
            return []

        hist = hist.reset_index()
        result = []
        for _, row in hist.iterrows():
            date_val = row["Date"]
            date_str = (
                date_val.strftime("%Y-%m-%d")
                if isinstance(date_val, pd.Timestamp)
                else str(date_val).split(" ")[0]
            )
            result.append({
                "time": date_str,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })
        return result

    except Exception as exc:
        logger.error(f"fetch_stock_history failed for {ticker}: {exc!s}")
        return []
