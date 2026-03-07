"""Volatility forecasting models.

1. EWMA (Exponentially Weighted Moving Average) — simple, fast
2. GARCH(1,1) — industry standard, captures vol clustering
3. Realized-Implied spread (Variance Risk Premium)

Used for:
- Comparing forecast vol vs current IV → trade signals
- Position sizing based on expected future vol
- Risk management (VaR estimation)

References:
- Engle, R. (1982). "Autoregressive Conditional Heteroscedasticity"
- Bollerslev, T. (1986). "Generalized Autoregressive Conditional Heteroscedasticity"
- RiskMetrics Technical Document (1996). J.P. Morgan/Reuters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from diamond_options.volatility.historical import TRADING_DAYS_PER_YEAR


@dataclass(frozen=True)
class VolForecast:
    """Volatility forecast result."""
    method: str
    forecast_vol: float      # Annualized forecast
    current_vol: float       # Current realized vol
    confidence_low: float    # Lower bound (1 std)
    confidence_high: float   # Upper bound (1 std)
    long_run_vol: float      # Long-run mean vol (GARCH only)
    half_life_days: float    # Days for vol to mean-revert 50%


def ewma_volatility(
    returns: pd.Series | np.ndarray,
    lambda_: float = 0.94,
    annualize: bool = True,
) -> float:
    """EWMA volatility (RiskMetrics method).

    sigma^2_t = lambda * sigma^2_{t-1} + (1 - lambda) * r^2_{t-1}

    Lambda = 0.94 is the RiskMetrics daily parameter.
    Higher lambda = more weight on history, slower response.

    Args:
        returns: Log returns series.
        lambda_: Decay factor (0.94 for daily, 0.97 for monthly).
        annualize: Whether to annualize.

    Returns:
        Current EWMA volatility.
    """
    if isinstance(returns, pd.Series):
        returns = returns.values

    returns = returns[~np.isnan(returns)]
    if len(returns) < 2:
        return 0.0

    # Initialize with sample variance
    var = float(np.var(returns[:20])) if len(returns) >= 20 else float(np.var(returns))

    for r in returns:
        var = lambda_ * var + (1 - lambda_) * r**2

    vol = np.sqrt(var)
    if annualize:
        vol *= np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(vol)


def ewma_forecast(
    returns: pd.Series | np.ndarray,
    horizon_days: int = 5,
    lambda_: float = 0.94,
) -> VolForecast:
    """Forecast volatility using EWMA.

    EWMA forecast is constant (no mean reversion):
    sigma^2_{t+h} = sigma^2_t for all h.

    Args:
        returns: Log returns series.
        horizon_days: Forecast horizon in trading days.
        lambda_: EWMA decay parameter.

    Returns:
        VolForecast with current and forecast values.
    """
    current = ewma_volatility(returns, lambda_, annualize=True)

    # EWMA has no mean reversion — forecast equals current
    forecast = current

    # Confidence interval (rough — based on vol-of-vol)
    if isinstance(returns, pd.Series):
        returns = returns.values
    returns = returns[~np.isnan(returns)]

    # Vol of vol estimate
    if len(returns) > 60:
        rolling_vols = []
        for i in range(20, len(returns)):
            v = ewma_volatility(returns[:i], lambda_, annualize=True)
            rolling_vols.append(v)
        vol_of_vol = float(np.std(rolling_vols))
    else:
        vol_of_vol = current * 0.15  # Rough estimate

    half_life = np.log(2) / (1 - lambda_)

    return VolForecast(
        method="EWMA",
        forecast_vol=round(forecast, 4),
        current_vol=round(current, 4),
        confidence_low=round(max(forecast - vol_of_vol, 0.01), 4),
        confidence_high=round(forecast + vol_of_vol, 4),
        long_run_vol=round(current, 4),  # EWMA has no long-run mean
        half_life_days=round(half_life, 1),
    )


def garch_fit(
    returns: pd.Series | np.ndarray,
    omega: float | None = None,
    alpha: float | None = None,
    beta: float | None = None,
) -> tuple[float, float, float, list[float]]:
    """Fit GARCH(1,1) model to returns.

    sigma^2_t = omega + alpha * r^2_{t-1} + beta * sigma^2_{t-1}

    where:
    - omega = long-run variance weight
    - alpha = news impact (reaction to recent shock)
    - beta = persistence (memory of past variance)
    - alpha + beta < 1 for stationarity

    If parameters not provided, uses a simple moment-based estimation.

    Args:
        returns: Log returns (daily).
        omega, alpha, beta: GARCH parameters. If None, estimated.

    Returns:
        Tuple of (omega, alpha, beta, conditional_variances).
    """
    if isinstance(returns, pd.Series):
        r = returns.values.copy()
    else:
        r = np.array(returns, dtype=float)

    r = r[~np.isnan(r)]
    if len(r) < 30:
        var = float(np.var(r))
        return var * 0.01, 0.05, 0.90, [var] * len(r)

    # Simple moment-based parameter estimation (Variance Targeting)
    # Long-run variance = sample variance
    long_run_var = float(np.var(r))

    if alpha is None:
        alpha = 0.05  # Typical starting point
    if beta is None:
        beta = 0.90   # Typical persistence
    if omega is None:
        # omega = long_run_var * (1 - alpha - beta)
        persistence = alpha + beta
        if persistence >= 1.0:
            beta = 0.94 - alpha  # Force stationarity
        omega = long_run_var * (1 - alpha - beta)

    # Generate conditional variance series
    variances = [long_run_var]
    for i in range(1, len(r)):
        v = omega + alpha * r[i - 1] ** 2 + beta * variances[-1]
        variances.append(v)

    return omega, alpha, beta, variances


def garch_forecast(
    returns: pd.Series | np.ndarray,
    horizon_days: int = 5,
    omega: float | None = None,
    alpha: float | None = None,
    beta: float | None = None,
) -> VolForecast:
    """Forecast volatility using GARCH(1,1).

    GARCH forecasts mean-revert to long-run volatility:
    sigma^2_{t+h} = V_L + (alpha + beta)^h * (sigma^2_t - V_L)

    where V_L = omega / (1 - alpha - beta) is long-run variance.

    Args:
        returns: Daily log returns.
        horizon_days: Forecast horizon.
        omega, alpha, beta: GARCH parameters.

    Returns:
        VolForecast with mean-reverting forecast.
    """
    omega_fit, alpha_fit, beta_fit, variances = garch_fit(
        returns, omega, alpha, beta,
    )

    persistence = alpha_fit + beta_fit
    current_var = variances[-1]

    # Long-run variance
    if persistence < 1.0:
        long_run_var = omega_fit / (1 - persistence)
    else:
        long_run_var = current_var

    # Multi-step forecast: variance mean-reverts to long-run level
    forecast_var = long_run_var + (persistence**horizon_days) * (current_var - long_run_var)

    # Annualize
    current_vol = float(np.sqrt(current_var * TRADING_DAYS_PER_YEAR))
    forecast_vol = float(np.sqrt(forecast_var * TRADING_DAYS_PER_YEAR))
    long_run_vol = float(np.sqrt(long_run_var * TRADING_DAYS_PER_YEAR))

    # Half-life of vol shock (days for deviation to halve)
    if persistence > 0 and persistence < 1:
        half_life = float(np.log(2) / (-np.log(persistence)))
    else:
        half_life = float("inf")

    # Confidence interval
    vol_of_vol = current_vol * 0.12  # Rough estimate

    return VolForecast(
        method="GARCH(1,1)",
        forecast_vol=round(forecast_vol, 4),
        current_vol=round(current_vol, 4),
        confidence_low=round(max(forecast_vol - vol_of_vol, 0.01), 4),
        confidence_high=round(forecast_vol + vol_of_vol, 4),
        long_run_vol=round(long_run_vol, 4),
        half_life_days=round(half_life, 1),
    )


def variance_risk_premium(
    implied_vol: float,
    realized_vol: float,
) -> dict:
    """Calculate Variance Risk Premium (VRP).

    VRP = IV^2 - RV^2 (in variance terms)
    Vol spread = IV - RV (in vol terms)

    Positive VRP means options are "expensive" relative to realized vol.
    This is the risk premium that option sellers collect.

    Historically, VRP is positive ~80% of the time → structural edge for sellers.

    Args:
        implied_vol: Current implied volatility (annualized decimal).
        realized_vol: Current realized volatility (annualized decimal).

    Returns:
        Dict with VRP metrics and interpretation.
    """
    vol_spread = implied_vol - realized_vol
    var_spread = implied_vol**2 - realized_vol**2
    ratio = implied_vol / realized_vol if realized_vol > 0 else 0

    # Interpretation
    if vol_spread > 0.05:
        signal = "options_expensive"
        action = "Consider selling premium (short straddle, iron condor)"
    elif vol_spread < -0.03:
        signal = "options_cheap"
        action = "Consider buying premium (long straddle, long strangle)"
    else:
        signal = "fair"
        action = "No strong vol edge — use directional or neutral strategies"

    return {
        "implied_vol": round(implied_vol, 4),
        "realized_vol": round(realized_vol, 4),
        "vol_spread": round(vol_spread, 4),
        "variance_spread": round(var_spread, 4),
        "iv_rv_ratio": round(ratio, 2),
        "signal": signal,
        "action": action,
    }
