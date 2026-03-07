"""NSE F&O universe — stocks permitted for derivatives trading.

Includes lot sizes, tick sizes, and sector mapping.
Lot sizes are updated periodically by NSE (typically every quarter).

Source: https://www.nseindia.com/products/content/derivatives/equities/fo_underlying_home.htm
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FnOStock:
    """A single F&O-permitted stock with its contract specs."""
    symbol: str           # NSE symbol (e.g., "RELIANCE")
    yf_ticker: str        # Yahoo Finance ticker (e.g., "RELIANCE.NS")
    lot_size: int         # Current lot size
    tick_size: float      # Price tick (0.05 for most)
    sector: str


# Index contracts — the most liquid F&O instruments
INDEX_CONTRACTS: dict[str, dict[str, int | str | float]] = {
    "NIFTY": {
        "yf_ticker": "^NSEI",
        "lot_size": 65,
        "tick_size": 0.05,
        "sector": "Index",
        "weekly_expiry": True,  # Weekly expiry on Tuesday
    },
    "BANKNIFTY": {
        "yf_ticker": "^NSEBANK",
        "lot_size": 15,
        "tick_size": 0.05,
        "sector": "Index",
        "weekly_expiry": True,
    },
    "FINNIFTY": {
        "yf_ticker": "NIFTY_FIN_SERVICE.NS",
        "lot_size": 65,
        "tick_size": 0.05,
        "sector": "Index",
        "weekly_expiry": True,
    },
    "MIDCPNIFTY": {
        "yf_ticker": "NIFTY_MID_SELECT.NS",
        "lot_size": 50,
        "tick_size": 0.05,
        "sector": "Index",
        "weekly_expiry": False,
    },
}


# F&O stock universe — ~200 stocks permitted for derivatives trading
# Lot sizes as of Q1 2026 (update quarterly)
FNO_STOCKS: list[FnOStock] = [
    # --- Large Cap / High Liquidity ---
    FnOStock("RELIANCE", "RELIANCE.NS", 250, 0.05, "Energy"),
    FnOStock("TCS", "TCS.NS", 150, 0.05, "Technology"),
    FnOStock("HDFCBANK", "HDFCBANK.NS", 550, 0.05, "Financial Services"),
    FnOStock("INFY", "INFY.NS", 300, 0.05, "Technology"),
    FnOStock("ICICIBANK", "ICICIBANK.NS", 700, 0.05, "Financial Services"),
    FnOStock("SBIN", "SBIN.NS", 750, 0.05, "Financial Services"),
    FnOStock("BHARTIARTL", "BHARTIARTL.NS", 475, 0.05, "Telecom"),
    FnOStock("ITC", "ITC.NS", 1600, 0.05, "Consumer Staples"),
    FnOStock("KOTAKBANK", "KOTAKBANK.NS", 400, 0.05, "Financial Services"),
    FnOStock("LT", "LT.NS", 150, 0.05, "Industrials"),
    FnOStock("AXISBANK", "AXISBANK.NS", 625, 0.05, "Financial Services"),
    FnOStock("BAJFINANCE", "BAJFINANCE.NS", 125, 0.05, "Financial Services"),
    FnOStock("MARUTI", "MARUTI.NS", 50, 0.05, "Automobile"),
    FnOStock("SUNPHARMA", "SUNPHARMA.NS", 350, 0.05, "Healthcare"),
    FnOStock("TATAMOTORS", "TATAMOTORS.NS", 550, 0.05, "Automobile"),
    FnOStock("HCLTECH", "HCLTECH.NS", 350, 0.05, "Technology"),
    FnOStock("WIPRO", "WIPRO.NS", 1500, 0.05, "Technology"),
    FnOStock("ADANIENT", "ADANIENT.NS", 250, 0.05, "Industrials"),
    FnOStock("NTPC", "NTPC.NS", 1500, 0.05, "Utilities"),
    FnOStock("TATASTEEL", "TATASTEEL.NS", 5500, 0.05, "Metals"),
    FnOStock("POWERGRID", "POWERGRID.NS", 2700, 0.05, "Utilities"),
    FnOStock("ONGC", "ONGC.NS", 1925, 0.05, "Energy"),
    FnOStock("JSWSTEEL", "JSWSTEEL.NS", 675, 0.05, "Metals"),
    FnOStock("M&M", "M&M.NS", 350, 0.05, "Automobile"),
    FnOStock("HINDALCO", "HINDALCO.NS", 1075, 0.05, "Metals"),
    FnOStock("COALINDIA", "COALINDIA.NS", 1200, 0.05, "Metals"),
    FnOStock("DRREDDY", "DRREDDY.NS", 125, 0.05, "Healthcare"),
    FnOStock("CIPLA", "CIPLA.NS", 325, 0.05, "Healthcare"),
    FnOStock("BAJAJFINSV", "BAJAJFINSV.NS", 500, 0.05, "Financial Services"),
    FnOStock("DIVISLAB", "DIVISLAB.NS", 125, 0.05, "Healthcare"),
    FnOStock("GRASIM", "GRASIM.NS", 250, 0.05, "Materials"),
    FnOStock("BRITANNIA", "BRITANNIA.NS", 100, 0.05, "Consumer Staples"),
    FnOStock("NESTLEIND", "NESTLEIND.NS", 200, 0.05, "Consumer Staples"),
    FnOStock("ASIANPAINT", "ASIANPAINT.NS", 300, 0.05, "Consumer Discretionary"),
    FnOStock("TITAN", "TITAN.NS", 175, 0.05, "Consumer Discretionary"),
    FnOStock("HEROMOTOCO", "HEROMOTOCO.NS", 150, 0.05, "Automobile"),
    FnOStock("EICHERMOT", "EICHERMOT.NS", 150, 0.05, "Automobile"),
    FnOStock("ULTRACEMCO", "ULTRACEMCO.NS", 50, 0.05, "Materials"),
    FnOStock("TECHM", "TECHM.NS", 600, 0.05, "Technology"),
    FnOStock("INDUSINDBK", "INDUSINDBK.NS", 500, 0.05, "Financial Services"),
    FnOStock("APOLLOHOSP", "APOLLOHOSP.NS", 125, 0.05, "Healthcare"),
    FnOStock("BPCL", "BPCL.NS", 1800, 0.05, "Energy"),
    FnOStock("HINDUNILVR", "HINDUNILVR.NS", 300, 0.05, "Consumer Staples"),
    FnOStock("BAJAJ-AUTO", "BAJAJ-AUTO.NS", 75, 0.05, "Automobile"),
    FnOStock("TRENT", "TRENT.NS", 100, 0.05, "Consumer Discretionary"),
    FnOStock("ADANIPORTS", "ADANIPORTS.NS", 400, 0.05, "Industrials"),
    FnOStock("TATACONSUM", "TATACONSUM.NS", 500, 0.05, "Consumer Discretionary"),
    FnOStock("DLF", "DLF.NS", 825, 0.05, "Real Estate"),
    FnOStock("HAL", "HAL.NS", 150, 0.05, "Industrials"),
    FnOStock("BEL", "BEL.NS", 1500, 0.05, "Industrials"),
    FnOStock("TATAPOWER", "TATAPOWER.NS", 1350, 0.05, "Utilities"),
    FnOStock("SIEMENS", "SIEMENS.NS", 75, 0.05, "Industrials"),
    FnOStock("ABB", "ABB.NS", 125, 0.05, "Industrials"),
    FnOStock("CHOLAFIN", "CHOLAFIN.NS", 625, 0.05, "Financial Services"),
    FnOStock("INDIGO", "INDIGO.NS", 150, 0.05, "Transport"),
    FnOStock("GODREJPROP", "GODREJPROP.NS", 250, 0.05, "Real Estate"),
    FnOStock("POLYCAB", "POLYCAB.NS", 100, 0.05, "Industrials"),
    FnOStock("BANKBARODA", "BANKBARODA.NS", 2925, 0.05, "Financial Services"),
    FnOStock("PNB", "PNB.NS", 4000, 0.05, "Financial Services"),
    FnOStock("VEDL", "VEDL.NS", 1550, 0.05, "Metals"),
    FnOStock("SHRIRAMFIN", "SHRIRAMFIN.NS", 200, 0.05, "Financial Services"),
    FnOStock("JINDALSTEL", "JINDALSTEL.NS", 625, 0.05, "Metals"),
    FnOStock("LUPIN", "LUPIN.NS", 425, 0.05, "Healthcare"),
    FnOStock("PERSISTENT", "PERSISTENT.NS", 100, 0.05, "Technology"),
    FnOStock("DIXON", "DIXON.NS", 50, 0.05, "Consumer Discretionary"),
    FnOStock("COFORGE", "COFORGE.NS", 100, 0.05, "Technology"),
    FnOStock("LTIM", "LTIM.NS", 150, 0.05, "Technology"),
    FnOStock("MUTHOOTFIN", "MUTHOOTFIN.NS", 300, 0.05, "Financial Services"),
    FnOStock("NAUKRI", "NAUKRI.NS", 75, 0.05, "Technology"),
    FnOStock("PIDILITIND", "PIDILITIND.NS", 250, 0.05, "Materials"),
    FnOStock("HAVELLS", "HAVELLS.NS", 500, 0.05, "Consumer Discretionary"),
    FnOStock("SRF", "SRF.NS", 250, 0.05, "Materials"),
    FnOStock("VOLTAS", "VOLTAS.NS", 400, 0.05, "Consumer Discretionary"),
    FnOStock("MRF", "MRF.NS", 5, 0.05, "Automobile"),
    FnOStock("BOSCHLTD", "BOSCHLTD.NS", 25, 0.05, "Industrials"),
    FnOStock("PAGEIND", "PAGEIND.NS", 15, 0.05, "Consumer Discretionary"),
]

# --- Lookup helpers ---

# {symbol: FnOStock} for quick access
_STOCK_MAP: dict[str, FnOStock] = {s.symbol: s for s in FNO_STOCKS}

# {yf_ticker: FnOStock}
_TICKER_MAP: dict[str, FnOStock] = {s.yf_ticker: s for s in FNO_STOCKS}

# All F&O symbols
FNO_SYMBOLS: list[str] = [s.symbol for s in FNO_STOCKS]


def get_fno_stock(symbol: str) -> FnOStock | None:
    """Look up F&O stock by NSE symbol (e.g., 'RELIANCE')."""
    return _STOCK_MAP.get(symbol.upper())


def get_lot_size(symbol: str) -> int:
    """Return lot size for a symbol. Returns 0 if not in F&O."""
    stock = _STOCK_MAP.get(symbol.upper())
    return stock.lot_size if stock else 0


def get_sector(symbol: str) -> str:
    """Return sector for a symbol."""
    stock = _STOCK_MAP.get(symbol.upper())
    return stock.sector if stock else "Unknown"


def is_fno_stock(symbol: str) -> bool:
    """Check if a symbol is F&O permitted."""
    return symbol.upper() in _STOCK_MAP


def get_index_lot_size(index: str) -> int:
    """Return lot size for an index (NIFTY, BANKNIFTY, etc.)."""
    info = INDEX_CONTRACTS.get(index.upper())
    return int(info["lot_size"]) if info else 0


def get_all_fno_tickers() -> list[str]:
    """Return all F&O Yahoo Finance tickers."""
    return [s.yf_ticker for s in FNO_STOCKS]


def get_fno_by_sector(sector: str) -> list[FnOStock]:
    """Return all F&O stocks in a sector."""
    return [s for s in FNO_STOCKS if s.sector.lower() == sector.lower()]


def search_symbol(query: str) -> list[FnOStock]:
    """Fuzzy search for F&O stocks by symbol prefix."""
    q = query.upper()
    return [s for s in FNO_STOCKS if s.symbol.startswith(q)]
