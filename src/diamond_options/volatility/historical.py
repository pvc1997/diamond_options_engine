"""Historical volatility estimators.

Multiple estimators for measuring realized volatility from price data:
1. Close-to-Close (standard) — simplest, most common
2. Parkinson (High-Low) — more efficient, uses intraday range
3. Garman-Klass — uses OHLC, most efficient for daily data
4. Yang-Zhang — handles overnight jumps, best overall estimator
5. Rogers-Satchell — drift-independent, good for trending markets

All return annualized volatility (multiply by sqrt(252) for daily data).

References:
- Parkinson, M. (1980). "The Extreme Value Method for Estimating the Variance of the Rate of Return"
- Garman, M. & Klass, M. (1980). "On the Estimation of Security Price Volatilities from Historical Data"
- Yang, D. & Zhang, Q. (2000). "Drift-Independent Volatility Estimation"
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class VolEstimate:
    """Volatility estimate with metadata."""
    method: str              # Estimator name
    volatility: float        # Annualized volatility (decimal)
    window: int              # Lookback window used
    data_points: int         # Number of observations used


def close_to_close(
    prices: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> float:
    """Standard close-to-close volatility estimator.

    sigma = std(log_returns) * sqrt(252)

    Most commonly used. Simple but ignores intraday information.

    Args:
        prices: Close price series.
        window: Lookback period in trading days.
        annualize: Whether to annualize.

    Returns:
        Annualized volatility as decimal.
    """
    if len(prices) < window + 1:
        return 0.0

    log_returns = np.log(prices / prices.shift(1)).dropna()
    recent = log_returns.iloc[-window:]

    vol = float(recent.std())
    if annualize:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return vol


def parkinson(
    high: pd.Series,
    low: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> float:
    """Parkinson (High-Low Range) volatility estimator.

    sigma^2 = (1 / 4*ln(2)) * mean(ln(H/L)^2)

    ~5x more efficient than close-to-close for continuous processes.
    Underestimates vol if there are jumps (gaps).

    Args:
        high: High price series.
        low: Low price series.
        window: Lookback period.
        annualize: Whether to annualize.

    Returns:
        Annualized volatility.
    """
    if len(high) < window or len(low) < window:
        return 0.0

    log_hl = np.log(high / low)
    recent = log_hl.iloc[-window:]

    var = float((recent**2).mean()) / (4 * np.log(2))
    vol = np.sqrt(var)

    if annualize:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(vol)


def garman_klass(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> float:
    """Garman-Klass OHLC volatility estimator.

    sigma^2 = 0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2

    Most efficient estimator using OHLC data (~8x more efficient than close-close).

    Args:
        open_: Open price series.
        high: High price series.
        low: Low price series.
        close: Close price series.
        window: Lookback period.
        annualize: Whether to annualize.

    Returns:
        Annualized volatility.
    """
    n = min(len(open_), len(high), len(low), len(close))
    if n < window:
        return 0.0

    log_hl = np.log(high / low).iloc[-window:]
    log_co = np.log(close / open_).iloc[-window:]

    var = float((0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2).mean())
    vol = np.sqrt(max(var, 0))

    if annualize:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(vol)


def yang_zhang(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> float:
    """Yang-Zhang volatility estimator.

    Combines overnight (close-to-open) and intraday (Rogers-Satchell) components.
    Best overall estimator — handles both jumps and drift.

    sigma^2 = sigma_o^2 + k * sigma_c^2 + (1-k) * sigma_rs^2

    where:
    - sigma_o = overnight variance (close-to-open returns)
    - sigma_c = open-to-close variance
    - sigma_rs = Rogers-Satchell variance
    - k = 0.34 / (1.34 + (n+1)/(n-1))

    Args:
        open_: Open price series.
        high: High price series.
        low: Low price series.
        close: Close price series.
        window: Lookback period.
        annualize: Whether to annualize.

    Returns:
        Annualized volatility.
    """
    n = min(len(open_), len(high), len(low), len(close))
    if n < window + 1:
        return 0.0

    # Align and take recent window
    o = open_.iloc[-window:]
    h = high.iloc[-window:]
    l = low.iloc[-window:]
    c = close.iloc[-window:]
    c_prev = close.iloc[-(window + 1):-1]

    # Reset indices for alignment
    c_prev = c_prev.reset_index(drop=True)
    o = o.reset_index(drop=True)
    h = h.reset_index(drop=True)
    l = l.reset_index(drop=True)
    c = c.reset_index(drop=True)

    # Overnight returns: ln(Open / Previous Close)
    log_oc = np.log(o / c_prev)
    sigma_o_sq = float(log_oc.var())

    # Open-to-close returns
    log_co = np.log(c / o)
    sigma_c_sq = float(log_co.var())

    # Rogers-Satchell variance
    log_ho = np.log(h / o)
    log_hc = np.log(h / c)
    log_lo = np.log(l / o)
    log_lc = np.log(l / c)
    sigma_rs_sq = float((log_ho * log_hc + log_lo * log_lc).mean())

    # Combining factor
    n_val = window
    k = 0.34 / (1.34 + (n_val + 1) / (n_val - 1))

    var = sigma_o_sq + k * sigma_c_sq + (1 - k) * sigma_rs_sq
    vol = np.sqrt(max(var, 0))

    if annualize:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(vol)


def rogers_satchell(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> float:
    """Rogers-Satchell volatility estimator.

    Drift-independent — unbiased even when the asset has a trend.

    sigma^2 = mean(ln(H/C)*ln(H/O) + ln(L/C)*ln(L/O))

    Args:
        open_: Open price series.
        high: High price series.
        low: Low price series.
        close: Close price series.
        window: Lookback period.
        annualize: Whether to annualize.

    Returns:
        Annualized volatility.
    """
    n = min(len(open_), len(high), len(low), len(close))
    if n < window:
        return 0.0

    o = open_.iloc[-window:]
    h = high.iloc[-window:]
    l = low.iloc[-window:]
    c = close.iloc[-window:]

    log_hc = np.log(h / c)
    log_ho = np.log(h / o)
    log_lc = np.log(l / c)
    log_lo = np.log(l / o)

    var = float((log_hc * log_ho + log_lc * log_lo).mean())
    vol = np.sqrt(max(var, 0))

    if annualize:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(vol)


def rolling_volatility(
    prices: pd.Series,
    window: int = 20,
    method: str = "close",
) -> pd.Series:
    """Calculate rolling volatility using specified method.

    Args:
        prices: Close price series.
        window: Rolling window size.
        method: "close" for close-to-close (only method for close-only data).

    Returns:
        Series of rolling annualized volatility values.
    """
    log_returns = np.log(prices / prices.shift(1)).dropna()
    rolling_std = log_returns.rolling(window=window).std()
    return (rolling_std * np.sqrt(TRADING_DAYS_PER_YEAR)).dropna()


def all_estimators(
    ohlc: pd.DataFrame,
    window: int = 20,
) -> list[VolEstimate]:
    """Calculate volatility using all available estimators.

    Args:
        ohlc: DataFrame with Open, High, Low, Close columns.
        window: Lookback period.

    Returns:
        List of VolEstimate for each method.
    """
    results = []

    if "Close" in ohlc.columns:
        cc = close_to_close(ohlc["Close"], window)
        results.append(VolEstimate("Close-to-Close", round(cc, 4), window, len(ohlc)))

    if {"High", "Low"}.issubset(ohlc.columns):
        pk = parkinson(ohlc["High"], ohlc["Low"], window)
        results.append(VolEstimate("Parkinson", round(pk, 4), window, len(ohlc)))

    if {"Open", "High", "Low", "Close"}.issubset(ohlc.columns):
        gk = garman_klass(ohlc["Open"], ohlc["High"], ohlc["Low"], ohlc["Close"], window)
        results.append(VolEstimate("Garman-Klass", round(gk, 4), window, len(ohlc)))

        yz = yang_zhang(ohlc["Open"], ohlc["High"], ohlc["Low"], ohlc["Close"], window)
        results.append(VolEstimate("Yang-Zhang", round(yz, 4), window, len(ohlc)))

        rs = rogers_satchell(ohlc["Open"], ohlc["High"], ohlc["Low"], ohlc["Close"], window)
        results.append(VolEstimate("Rogers-Satchell", round(rs, 4), window, len(ohlc)))

    return results


def multi_window_vol(
    prices: pd.Series,
    windows: list[int] | None = None,
) -> dict[int, float]:
    """Calculate close-to-close vol across multiple windows.

    Default windows: 5, 10, 20, 30, 60, 90, 252 days.

    Returns:
        Dict mapping window -> annualized vol.
    """
    if windows is None:
        windows = [5, 10, 20, 30, 60, 90, 252]

    return {
        w: round(close_to_close(prices, w), 4)
        for w in windows
        if len(prices) > w + 1
    }
