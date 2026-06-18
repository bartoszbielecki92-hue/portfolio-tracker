import streamlit as st
import yfinance as yf
from typing import Optional


def _yf_ticker(symbol: str) -> str:
    """Convert internal symbol to Yahoo Finance format.
    ETH/USD → ETH-USD, everything else passes through as-is.
    """
    return symbol.replace("/", "-")


@st.cache_data(ttl=900)
def fetch_prices(tickers: tuple) -> dict:
    """Fetch current prices for a tuple of tickers. Returns {ticker: price or None}."""
    if not tickers:
        return {}
    result = {}
    yf_symbols = [_yf_ticker(t) for t in tickers]
    try:
        data = yf.Tickers(" ".join(yf_symbols))
        for orig, yf_sym in zip(tickers, yf_symbols):
            try:
                price = data.tickers[yf_sym].fast_info["lastPrice"]
                result[orig] = float(price) if price else None
            except Exception:
                result[orig] = None
    except Exception:
        return {t: None for t in tickers}
    return result


@st.cache_data(ttl=900)
def fetch_fx_rates() -> dict:
    """Fetch USD/PLN, EUR/PLN, GBP/PLN via Yahoo Finance. Returns {currency: rate_to_pln}."""
    pairs = {"USD": "USDPLN=X", "EUR": "EURPLN=X", "GBP": "GBPPLN=X"}
    rates = {"PLN": 1.0}
    try:
        data = yf.Tickers(" ".join(pairs.values()))
        for currency, yf_sym in pairs.items():
            try:
                rate = data.tickers[yf_sym].fast_info["lastPrice"]
                if rate:
                    rates[currency] = float(rate)
            except Exception:
                pass
    except Exception:
        pass
    return rates


def to_pln(amount: float, currency: str, fx_rates: dict) -> Optional[float]:
    """Convert amount to PLN using fetched rates. Returns None if rate unavailable."""
    if currency == "PLN":
        return amount
    rate = fx_rates.get(currency)
    return round(amount * rate, 2) if rate else None
