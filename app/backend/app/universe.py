HIGH_QUALITY_TICKERS: list[str] = [
    "AAPL", "AMAT", "AMD", "AMZN", "APLD", "AVGO", "BBAI", "BULL",
    "COIN", "DELL", "GME", "GOOGL", "INTC", "IONQ", "LRCX", "META",
    "MSFT", "NFLX", "NVDA", "OKLO", "PLTR", "QBTS", "QCOM", "QS",
    "QUBT", "RBLX", "RGTI", "RKLB", "SMCI", "SMR", "SOUN", "TLRY",
    "TSLA", "TSM", "UUUU",
]

UNIVERSE_SET = frozenset(HIGH_QUALITY_TICKERS)


def is_universe_ticker(ticker: str) -> bool:
    return ticker.upper() in UNIVERSE_SET
