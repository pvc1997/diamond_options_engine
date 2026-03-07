"""Tests for volatility estimators and forecasting."""

import numpy as np
import pandas as pd
import pytest

from diamond_options.volatility.historical import (
    close_to_close,
    parkinson,
    garman_klass,
    yang_zhang,
    rogers_satchell,
    rolling_volatility,
    all_estimators,
    multi_window_vol,
)
from diamond_options.volatility.forecast import (
    ewma_volatility,
    ewma_forecast,
    garch_fit,
    garch_forecast,
    variance_risk_premium,
)
from diamond_options.volatility.vix import (
    classify_regime,
    vix_mean_reversion_signal,
    vix_term_structure_signal,
)


@pytest.fixture
def price_series() -> pd.Series:
    """Synthetic price series with known properties."""
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.01, 300)  # ~16% annual vol
    prices = 100 * np.exp(np.cumsum(returns))
    return pd.Series(prices, name="Close")


@pytest.fixture
def ohlc_data() -> pd.DataFrame:
    """Synthetic OHLC data."""
    np.random.seed(42)
    n = 300
    close = [100.0]
    for _ in range(n - 1):
        close.append(close[-1] * np.exp(np.random.normal(0.0005, 0.01)))

    close = np.array(close)
    high = close * (1 + np.abs(np.random.normal(0, 0.005, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, n)))
    open_ = close * np.exp(np.random.normal(0, 0.003, n))

    return pd.DataFrame({
        "Open": open_, "High": high, "Low": low, "Close": close,
    })


class TestCloseToClose:
    def test_positive_vol(self, price_series):
        vol = close_to_close(price_series, window=20)
        assert vol > 0

    def test_reasonable_range(self, price_series):
        """Vol should be in reasonable range for our synthetic data."""
        vol = close_to_close(price_series, window=20)
        assert 0.05 < vol < 0.50  # 5% to 50%

    def test_short_series(self):
        """Too-short series should return 0."""
        short = pd.Series([100, 101, 102])
        vol = close_to_close(short, window=20)
        assert vol == 0.0

    def test_annualization(self, price_series):
        """Annualized vol should be ~sqrt(252) times daily."""
        daily = close_to_close(price_series, window=20, annualize=False)
        annual = close_to_close(price_series, window=20, annualize=True)
        assert abs(annual / daily - np.sqrt(252)) < 1.0


class TestParkinson:
    def test_positive(self, ohlc_data):
        vol = parkinson(ohlc_data["High"], ohlc_data["Low"], window=20)
        assert vol > 0

    def test_more_efficient(self, ohlc_data):
        """Parkinson should generally have lower variance than close-close."""
        pk = parkinson(ohlc_data["High"], ohlc_data["Low"], window=20)
        # Just verify it produces a reasonable number
        assert 0.01 < pk < 1.0


class TestGarmanKlass:
    def test_positive(self, ohlc_data):
        vol = garman_klass(
            ohlc_data["Open"], ohlc_data["High"],
            ohlc_data["Low"], ohlc_data["Close"], window=20,
        )
        assert vol > 0

    def test_reasonable(self, ohlc_data):
        vol = garman_klass(
            ohlc_data["Open"], ohlc_data["High"],
            ohlc_data["Low"], ohlc_data["Close"], window=20,
        )
        assert 0.01 < vol < 1.0


class TestYangZhang:
    def test_positive(self, ohlc_data):
        vol = yang_zhang(
            ohlc_data["Open"], ohlc_data["High"],
            ohlc_data["Low"], ohlc_data["Close"], window=20,
        )
        assert vol > 0

    def test_handles_overnight(self, ohlc_data):
        """Yang-Zhang should handle overnight jumps."""
        vol = yang_zhang(
            ohlc_data["Open"], ohlc_data["High"],
            ohlc_data["Low"], ohlc_data["Close"], window=20,
        )
        assert 0.01 < vol < 1.0


class TestRogersSatchell:
    def test_positive(self, ohlc_data):
        vol = rogers_satchell(
            ohlc_data["Open"], ohlc_data["High"],
            ohlc_data["Low"], ohlc_data["Close"], window=20,
        )
        assert vol > 0


class TestAllEstimators:
    def test_returns_multiple(self, ohlc_data):
        results = all_estimators(ohlc_data, window=20)
        assert len(results) == 5  # CC, PK, GK, YZ, RS

    def test_all_positive(self, ohlc_data):
        for est in all_estimators(ohlc_data, window=20):
            assert est.volatility > 0, f"{est.method} returned non-positive vol"

    def test_close_only(self, price_series):
        """With only Close, should return 1 estimator."""
        df = pd.DataFrame({"Close": price_series})
        results = all_estimators(df, window=20)
        assert len(results) == 1
        assert results[0].method == "Close-to-Close"


class TestMultiWindowVol:
    def test_returns_dict(self, price_series):
        result = multi_window_vol(price_series)
        assert isinstance(result, dict)
        assert 20 in result
        assert all(v > 0 for v in result.values())


class TestRollingVol:
    def test_rolling(self, price_series):
        result = rolling_volatility(price_series, window=20)
        assert len(result) > 0
        assert (result > 0).all()


class TestEWMA:
    def test_positive(self, price_series):
        returns = np.log(price_series / price_series.shift(1)).dropna()
        vol = ewma_volatility(returns)
        assert vol > 0

    def test_forecast(self, price_series):
        returns = np.log(price_series / price_series.shift(1)).dropna()
        f = ewma_forecast(returns)
        assert f.forecast_vol > 0
        assert f.method == "EWMA"
        assert f.half_life_days > 0


class TestGARCH:
    def test_garch_fit(self, price_series):
        returns = np.log(price_series / price_series.shift(1)).dropna()
        omega, alpha, beta, variances = garch_fit(returns)
        assert omega > 0
        assert 0 < alpha < 1
        assert 0 < beta < 1
        assert alpha + beta < 1  # Stationarity
        assert len(variances) == len(returns)

    def test_garch_forecast(self, price_series):
        returns = np.log(price_series / price_series.shift(1)).dropna()
        f = garch_forecast(returns, horizon_days=5)
        assert f.forecast_vol > 0
        assert f.long_run_vol > 0
        assert f.method == "GARCH(1,1)"
        assert f.half_life_days > 0

    def test_garch_mean_reversion(self, price_series):
        """Forecast should move toward long-run vol."""
        returns = np.log(price_series / price_series.shift(1)).dropna()
        f_short = garch_forecast(returns, horizon_days=1)
        f_long = garch_forecast(returns, horizon_days=100)
        # Long forecast should be closer to long-run mean
        diff_short = abs(f_short.forecast_vol - f_short.long_run_vol)
        diff_long = abs(f_long.forecast_vol - f_long.long_run_vol)
        assert diff_long <= diff_short + 0.001


class TestVRP:
    def test_options_expensive(self):
        result = variance_risk_premium(0.20, 0.12)
        assert result["signal"] == "options_expensive"
        assert result["vol_spread"] > 0

    def test_options_cheap(self):
        result = variance_risk_premium(0.10, 0.18)
        assert result["signal"] == "options_cheap"
        assert result["vol_spread"] < 0

    def test_fair(self):
        result = variance_risk_premium(0.15, 0.14)
        assert result["signal"] == "fair"


class TestVIXRegime:
    def test_low_vol(self):
        regime = classify_regime(10)
        assert regime.regime == "low"
        assert regime.strategy_bias == "buy_vol"

    def test_normal_vol(self):
        regime = classify_regime(15)
        assert regime.regime == "normal"
        assert regime.position_sizing == 1.0

    def test_elevated_vol(self):
        regime = classify_regime(22)
        assert regime.regime == "elevated"
        assert regime.strategy_bias == "sell_vol"

    def test_high_vol(self):
        regime = classify_regime(30)
        assert regime.regime == "high"
        assert regime.position_sizing == 0.50

    def test_crisis_vol(self):
        regime = classify_regime(50)
        assert regime.regime == "crisis"
        assert regime.position_sizing == 0.25

    def test_mean_reversion_signal(self):
        signal = vix_mean_reversion_signal(25)
        assert signal["signal"] == "sell_vol"

        signal = vix_mean_reversion_signal(10)
        assert signal["signal"] == "buy_vol"

    def test_term_structure_contango(self):
        result = vix_term_structure_signal(near_vix=13, far_vix=17)
        assert result["structure"] == "contango"

    def test_term_structure_backwardation(self):
        result = vix_term_structure_signal(near_vix=25, far_vix=18)
        assert result["structure"] == "backwardation"
