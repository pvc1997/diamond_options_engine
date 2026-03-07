"""Tests for options strategy backtester."""

import pytest
import numpy as np

from diamond_options.risk.backtester import (
    BacktestResult,
    BacktestTrade,
    backtest_strategy,
)


@pytest.fixture
def trending_prices():
    """Gradually trending up prices (252 trading days)."""
    rng = np.random.default_rng(42)
    base = 22500.0
    # Small upward drift with noise
    returns = rng.normal(0.0003, 0.008, 252)
    prices = [base]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices


@pytest.fixture
def trending_dates(trending_prices):
    """Date strings matching prices."""
    from datetime import date, timedelta
    start = date(2025, 1, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(len(trending_prices))]


@pytest.fixture
def flat_prices():
    """Rangebound prices (good for short premium)."""
    rng = np.random.default_rng(123)
    base = 22500.0
    returns = rng.normal(0.0, 0.005, 100)
    prices = [base]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices


@pytest.fixture
def flat_dates(flat_prices):
    from datetime import date, timedelta
    start = date(2025, 1, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(len(flat_prices))]


class TestBacktestStrategy:
    def test_iron_condor(self, trending_prices, trending_dates):
        """Should complete backtest for iron condor."""
        result = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert isinstance(result, BacktestResult)
        assert result.total_trades > 0
        assert result.win_rate >= 0

    def test_bull_put_spread(self, trending_prices, trending_dates):
        result = backtest_strategy(
            "bull_put_spread", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert result.total_trades > 0

    def test_long_call(self, trending_prices, trending_dates):
        result = backtest_strategy(
            "long_call", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert result.total_trades > 0

    def test_short_strangle_flat(self, flat_prices, flat_dates):
        """Short strangle should do well in flat market."""
        result = backtest_strategy(
            "short_strangle", flat_prices, flat_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert result.total_trades > 0
        # In rangebound market, short premium should have decent win rate
        assert result.win_rate > 30

    def test_trade_count(self, trending_prices, trending_dates):
        """Trade count should match interval."""
        result = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        expected = (len(trending_prices) - 7) // 7
        assert abs(result.total_trades - expected) <= 1

    def test_statistics(self, trending_prices, trending_dates):
        result = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert result.winners + result.losers == result.total_trades
        assert 0 <= result.win_rate <= 100
        assert result.max_win >= result.avg_pnl
        assert result.max_loss <= result.avg_pnl

    def test_profit_factor(self, trending_prices, trending_dates):
        result = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert result.profit_factor >= 0

    def test_max_drawdown_negative(self, trending_prices, trending_dates):
        """Max drawdown should be <= 0."""
        result = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        assert result.max_drawdown <= 0

    def test_trade_log(self, trending_prices, trending_dates):
        """Each trade should have required fields."""
        result = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        for trade in result.trades:
            assert isinstance(trade, BacktestTrade)
            assert trade.entry_spot > 0
            assert trade.expiry_spot > 0
            assert trade.strategy == "iron_condor"
            assert len(trade.legs) > 0

    def test_insufficient_data(self):
        """Too short data should return empty result."""
        result = backtest_strategy(
            "iron_condor", [22500, 22510], ["2025-01-01", "2025-01-02"],
            sigma=0.13,
        )
        assert result.total_trades == 0

    def test_different_holding_periods(self, trending_prices, trending_dates):
        """Longer holding period should produce fewer trades."""
        short = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=7, holding_period=7,
        )
        long = backtest_strategy(
            "iron_condor", trending_prices, trending_dates,
            sigma=0.13, entry_interval=14, holding_period=14,
        )
        assert long.total_trades < short.total_trades

    def test_multiple_strategies(self, trending_prices, trending_dates):
        """Should support multiple strategy types."""
        for strategy in ["iron_condor", "bull_put_spread", "bear_call_spread",
                         "long_call", "long_put", "short_straddle"]:
            result = backtest_strategy(
                strategy, trending_prices, trending_dates,
                sigma=0.13, entry_interval=14, holding_period=7,
            )
            assert result.total_trades > 0, f"{strategy} produced no trades"
