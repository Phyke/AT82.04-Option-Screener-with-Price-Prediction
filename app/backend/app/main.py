from app.models import OptionContract, OptionsRequest, RecommendRequest, ScanRequest
from app.utils.market_data import fetch_stock_history
from app.utils.options import fetch_options
from app.utils.predict import eligible_tickers, is_supported, predict_ticker, vol_buckets
from app.utils.recommend import build_recommendation
from app.utils.screener import scan_for_user
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/options", response_model=list[OptionContract])
async def get_options(request: OptionsRequest):
    try:
        return fetch_options(request.tickers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/history/{ticker}")
async def get_history(ticker: str):
    try:
        data = fetch_stock_history(ticker)
        logger.info(f"Fetched history for {ticker}: {len(data)} records")
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Eligible universe ────────────────────────────────────────────────────────

@app.get("/universe")
async def get_universe():
    """Return the curated trading universe + vol bucket assignments."""
    return {
        "tickers": eligible_tickers(),
        "vol_buckets": vol_buckets(),
        "n_tickers": len(eligible_tickers()),
    }


# ── Personalized scan ────────────────────────────────────────────────────────

@app.post("/scan")
async def post_scan(request: ScanRequest):
    """Filter the eligible universe to actionable CSP/CC opportunities for a user.

    Body:
        cash_balance: cash available for CSP collateral
        positions: {ticker: shares_owned} for CC writing
        target_weekly_yield_pct: minimum acceptable weekly premium yield
        tickers: optional override (defaults to eligible 34)
    """
    try:
        return scan_for_user(
            cash_balance=request.cash_balance,
            positions=request.positions,
            target_weekly_yield_pct=request.target_weekly_yield_pct,
            tickers=request.tickers,
        )
    except Exception as exc:
        logger.exception("scan failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Friday-close direction prediction ────────────────────────────────────────

@app.get("/predict/{ticker}")
async def get_prediction(ticker: str):
    """Run the per-ticker LightGBM model to predict whether Friday close >= Monday close."""
    if not is_supported(ticker):
        raise HTTPException(
            status_code=404,
            detail=f"No model trained for {ticker}. Eligible: {eligible_tickers()}",
        )
    try:
        return predict_ticker(ticker)
    except Exception as exc:
        logger.exception(f"predict failed for {ticker}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Combined recommendation ──────────────────────────────────────────────────

@app.post("/recommend")
async def post_recommend(request: RecommendRequest):
    """Combine a screener contract + a model prediction into a natural-language card."""
    if not is_supported(request.ticker):
        raise HTTPException(
            status_code=404,
            detail=f"No model trained for {request.ticker}",
        )
    try:
        prediction = predict_ticker(request.ticker)
        if prediction.get("error"):
            raise HTTPException(status_code=500, detail=prediction["error"])
        return build_recommendation(request.contract, prediction)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("recommend failed")
        raise HTTPException(status_code=500, detail=str(exc))
