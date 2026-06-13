"""The catalogue of supported stocks.

The brief asks us to pick exactly 5 supported tickers. These are the only
tickers a user is allowed to subscribe to. Each entry carries a friendly
company name and a realistic starting price that the price engine then
random-walks away from.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedStock:
    ticker: str        # e.g. "GOOG" — the code users type to subscribe
    name: str          # e.g. "Alphabet Inc."
    seed_price: float   # starting price for the random-walk simulation
    volatility: float   # per-tick std-dev as a fraction (0.006 = ~0.6% moves)


# The 5 supported stocks from the brief. `volatility` is tuned per name so the
# dashboard feels realistic: NVDA/TSLA swing harder than GOOG/AMZN.
SUPPORTED_STOCKS: list[SupportedStock] = [
    SupportedStock("GOOG", "Alphabet Inc.", 175.40, volatility=0.004),
    SupportedStock("TSLA", "Tesla, Inc.", 248.50, volatility=0.009),
    SupportedStock("AMZN", "Amazon.com, Inc.", 185.10, volatility=0.005),
    SupportedStock("META", "Meta Platforms, Inc.", 505.75, volatility=0.006),
    SupportedStock("NVDA", "NVIDIA Corporation", 122.30, volatility=0.010),
]

# Fast lookup set/dict by ticker for validation and metadata.
SUPPORTED_TICKERS: set[str] = {s.ticker for s in SUPPORTED_STOCKS}
STOCK_BY_TICKER: dict[str, SupportedStock] = {s.ticker: s for s in SUPPORTED_STOCKS}


def is_supported(ticker: str) -> bool:
    """Case-insensitive check that a ticker is in our catalogue."""
    return ticker.strip().upper() in SUPPORTED_TICKERS
