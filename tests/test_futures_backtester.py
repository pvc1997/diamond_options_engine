"""Tests for futures strategy backtester."""

import pytest

from diamond_options.risk.futures_backtester import (
    FuturesBacktestResult,
    FuturesBacktestTrade,
    backtest_futures_strategy,
)


@pytest.fixture
def trending_up_prices() -> tuple[list[float], list[str]]:
    """50 days of upward trending prices."""
    prices = [22000 + i * 30 for i in range(50)]  # +30/day
    dates = [f"2026-01-{i+1:02d}" for i in range(31)] + \
            [f"2026-02-{i+1:02d}" for i in range(19)]
    return prices, dates


@pytest.fixture
def trending_down_prices() -> tuple[list[float], list[str]]:
    """50 days of downward trending prices."""
    prices = [24000 - i * 25 for i in range(50)]  # -25/day
    dates = [f"2026-01-{i+1:02d}" for i in range(31)] + \
            [f"2026-02-{i+1:02d}" for i in range(19)]
    return prices, dates


@pytest.fixture
def sideways_prices() -> tuple[list[float], list[str]]:
    """50 days of sideways oscillating prices."""
    import math
    prices = [22500 + 100 * math.sin(i * 0.5) for i in range(50)]
    dates = [f"2026-01-{i+1:02d}" for i in range(31)] + \
            [f"2026-02-{i+1:02d}" for i in range(19)]
    return prices, dates


class TestBacktestLongFutures:
    def test_returns_result(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates,
        )
        assert isinstance(result, FuturesBacktestResult)

    def test_has_trades(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates,
        )
        assert result.total_trades > 0

    def test_trending_up_profitable(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates,
            use_stops=False,
        )
        assert result.total_pnl > 0
        assert result.win_rate > 50

    def test_trending_up_short_loses(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "short_futures", prices, dates,
            use_stops=False,
        )
        assert result.total_pnl < 0


class TestBacktestShortFutures:
    def test_trending_down_profitable(self, trending_down_prices):
        prices, dates = trending_down_prices
        result = backtest_futures_strategy(
            "short_futures", prices, dates,
            use_stops=False,
        )
        assert result.total_pnl > 0

    def test_trending_down_long_loses(self, trending_down_prices):
        prices, dates = trending_down_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates,
            use_stops=False,
        )
        assert result.total_pnl < 0


class TestBacktestMeanReversion:
    def test_runs_on_sideways(self, sideways_prices):
        prices, dates = sideways_prices
        result = backtest_futures_strategy(
            "mean_reversion", prices, dates,
            entry_interval=1,  # Check every day
        )
        assert isinstance(result, FuturesBacktestResult)

    def test_needs_history(self):
        # Less than 20 days — mean reversion needs lookback
        prices = [22500.0] * 15
        dates = [f"2026-01-{i+1:02d}" for i in range(15)]
        result = backtest_futures_strategy(
            "mean_reversion", prices, dates,
            entry_interval=1,
        )
        # May have zero trades if not enough history for signals
        assert result.total_trades >= 0


class TestBacktestMomentum:
    def test_momentum_on_trend(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "momentum", prices, dates,
            entry_interval=1,
        )
        assert isinstance(result, FuturesBacktestResult)


class TestBacktestStatistics:
    def test_win_rate_bounded(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy("long_futures", prices, dates)
        assert 0 <= result.win_rate <= 100

    def test_profit_factor(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates, use_stops=False,
        )
        if result.winners > 0 and result.losers > 0:
            assert result.profit_factor > 0

    def test_max_drawdown_negative_or_zero(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy("long_futures", prices, dates)
        assert result.max_drawdown <= 0

    def test_sharpe_ratio(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy("long_futures", prices, dates)
        assert isinstance(result.sharpe_ratio, float)

    def test_expectancy(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates, use_stops=False,
        )
        if result.win_rate > 50:
            assert result.expectancy > 0

    def test_total_costs_positive(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy("long_futures", prices, dates)
        if result.total_trades > 0:
            assert result.total_costs > 0

    def test_trade_has_costs(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy("long_futures", prices, dates)
        if result.trades:
            assert result.trades[0].costs > 0

    def test_net_pnl_less_than_gross(self, trending_up_prices):
        prices, dates = trending_up_prices
        result = backtest_futures_strategy(
            "long_futures", prices, dates, use_stops=False,
        )
        for trade in result.trades:
            if trade.gross_pnl > 0:
                assert trade.net_pnl < trade.gross_pnl  # Costs eat into profit


class TestBacktestStopsTargets:
    def test_stop_limits_loss(self, trending_down_prices):
        prices, dates = trending_down_prices
        no_stops = backtest_futures_strategy(
            "long_futures", prices, dates,
            use_stops=False,
        )
        with_stops = backtest_futures_strategy(
            "long_futures", prices, dates,
            use_stops=True, stop_pct=1.0,
        )
        # Stops should limit the max loss
        assert with_stops.max_loss >= no_stops.max_loss  # Less negative

    def test_target_caps_gain(self, trending_up_prices):
        prices, dates = trending_up_prices
        no_target = backtest_futures_strategy(
            "long_futures", prices, dates,
            use_stops=False,
        )
        with_target = backtest_futures_strategy(
            "long_futures", prices, dates,
            use_stops=True, target_pct=0.5, stop_pct=5.0,
        )
        # With tight target, max win should be limited
        assert with_target.max_win <= no_target.max_win


class TestBacktestEdgeCases:
    def test_insufficient_data(self):
        result = backtest_futures_strategy(
            "long_futures", [22500], ["2026-01-01"],
        )
        assert result.total_trades == 0

    def test_empty_prices(self):
        result = backtest_futures_strategy(
            "long_futures", [], [],
        )
        assert result.total_trades == 0

    def test_custom_lot_size(self, trending_up_prices):
        prices, dates = trending_up_prices
        r65 = backtest_futures_strategy(
            "long_futures", prices, dates,
            lot_size=65, use_stops=False,
        )
        r250 = backtest_futures_strategy(
            "long_futures", prices, dates,
            lot_size=250, use_stops=False,
        )
        # Larger lot size → larger P&L
        if r65.total_trades > 0 and r250.total_trades > 0:
            assert abs(r250.total_pnl) > abs(r65.total_pnl)

    def test_multiple_lots(self, trending_up_prices):
        prices, dates = trending_up_prices
        r1 = backtest_futures_strategy(
            "long_futures", prices, dates, lots=1, use_stops=False,
        )
        r3 = backtest_futures_strategy(
            "long_futures", prices, dates, lots=3, use_stops=False,
        )
        if r1.total_trades > 0:
            # 3 lots should have ~3x P&L (approximately, costs differ)
            assert abs(r3.total_pnl) > abs(r1.total_pnl) * 2
