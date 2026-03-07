"""Market data fetcher wrapping yfinance with retry logic and file cache.

Provides spot prices, historical data, and India VIX for options analysis.
Handles yfinance v2 MultiIndex columns transparently.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from diamond_options.config import get_config

logger = logging.getLogger(__name__)


def _cache_path(tickers: list[str], period_days: int) -> Path:
    """Generate a deterministic cache file path for a set of tickers."""
    key = hashlib.md5(f"{sorted(tickers)}_{period_days}".encode()).hexdigest()[:12]
    return get_config().cache_dir / "prices" / f"{key}.csv"


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance v2 MultiIndex columns to single level."""
    if isinstance(df.columns, pd.MultiIndex):
        if df.columns.nlevels == 2:
            tickers = df.columns.get_level_values(1).unique()
            if len(tickers) == 1:
                df.columns = df.columns.get_level_values(0)
            else:
                df.columns = [f"{col[0]}_{col[1]}" for col in df.columns]
    return df


def download_prices(
    tickers: list[str],
    period_days: int | None = None,
    retries: int = 3,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Download adjusted close prices for tickers.

    Args:
        tickers: List of Yahoo Finance tickers.
        period_days: Number of calendar days of history.
        retries: Number of retry attempts on failure.
        use_cache: Whether to use file cache.

    Returns:
        DataFrame with DatetimeIndex and one column per ticker (adjusted close).
    """
    cfg = get_config()
    if period_days is None:
        period_days = cfg.market.default_lookback_days

    cache_file = _cache_path(tickers, period_days)
    if use_cache and cache_file.exists():
        age_seconds = time.time() - cache_file.stat().st_mtime
        if age_seconds < cfg.cache.prices_ttl:
            return pd.read_csv(cache_file, index_col=0, parse_dates=True)

    period_str = f"{period_days}d"
    last_error = None

    for attempt in range(retries):
        try:
            raw = yf.download(
                tickers,
                period=period_str,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if raw is None or raw.empty:
                raise ValueError(f"Empty data for {tickers}")

            df = _flatten_columns(raw)

            if len(tickers) == 1:
                if "Close" in df.columns:
                    df = pd.DataFrame(df[["Close"]]).rename(columns={"Close": tickers[0]})
                else:
                    df = df.iloc[:, :1]
                    df.columns = pd.Index([tickers[0]])
            else:
                close_cols = [c for c in df.columns if str(c).startswith("Close_")]
                if close_cols:
                    df = df[close_cols]
                    df.columns = pd.Index([str(c).replace("Close_", "") for c in close_cols])

            df = pd.DataFrame(df.dropna(how="all"))

            if use_cache:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(cache_file)

            return df

        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2**attempt)

    raise RuntimeError(f"Failed to download prices after {retries} attempts: {last_error}")


def download_single(ticker: str, period_days: int | None = None) -> pd.Series:
    """Download adjusted close for a single ticker. Returns Series."""
    df = download_prices([ticker], period_days=period_days)
    return df.iloc[:, 0].dropna()


def get_spot_price(ticker: str) -> float | None:
    """Fetch current spot price for a ticker."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("currentPrice") or info.get("regularMarketPrice")
    except Exception:
        return None


def get_india_vix() -> float | None:
    """Fetch current India VIX value."""
    try:
        vix = yf.Ticker("^INDIAVIX")
        hist = vix.history(period="5d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def calculate_returns(prices: pd.Series) -> pd.Series:
    """Calculate daily log returns from a price series."""
    return np.log(prices / prices.shift(1)).dropna()


def calculate_historical_volatility(
    prices: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> pd.Series:
    """Calculate rolling historical volatility.

    Args:
        prices: Price series.
        window: Rolling window in trading days.
        annualize: Whether to annualize (multiply by sqrt(252)).

    Returns:
        Series of rolling volatility values.
    """
    returns = calculate_returns(prices)
    vol = returns.rolling(window=window).std()
    if annualize:
        vol = vol * np.sqrt(252)
    return vol.dropna()


def get_ohlcv(ticker: str, period_days: int = 30) -> pd.DataFrame:
    """Fetch OHLCV data for a ticker.

    Returns DataFrame with columns: Open, High, Low, Close, Volume.
    """
    try:
        raw = yf.download(
            ticker,
            period=f"{period_days}d",
            auto_adjust=True,
            progress=False,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        df = _flatten_columns(raw)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        return pd.DataFrame()
