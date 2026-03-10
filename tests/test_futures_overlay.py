"""Tests for futures overlay strategies on equity holdings."""

from diamond_options.integration.stock_bridge import StockHolding, StockPortfolio
from diamond_options.integration.futures_overlay import (
    suggest_stock_futures_hedge,
    suggest_index_futures_hedge,
    compare_hedge_methods,
    futures_income_from_holdings,
)


def _holding(symbol="RELIANCE", shares=500, price=2800.0):
    return StockHolding(
        ticker=f"{symbol}.NS", fno_symbol=symbol, shares=shares,
        avg_price=price, current_price=price,
        market_value=shares * price, unrealized_pnl=0,
        unrealized_pnl_pct=0, weight_pct=100,
    )


def _portfolio(value=1500000.0, fno_eligible=None):
    eligible = fno_eligible or []
    fno_value = sum(h.market_value for h in eligible)
    return StockPortfolio(
        strategy="test", holdings=eligible, total_value=value,
        cash=0, nav=value, num_stocks=len(eligible),
        fno_eligible=eligible, fno_eligible_value=fno_value,
        fno_eligible_pct=(fno_value / value * 100) if value > 0 else 0,
    )


# ── suggest_stock_futures_hedge ─────────────────────────────────


class TestStockFuturesHedge:
    def test_basic_hedge(self):
        h = _holding("RELIANCE", 500, 2800.0)
        result = suggest_stock_futures_hedge(h, futures_price=2810.0, days_to_expiry=20)
        assert result is not None
        assert result.fno_symbol == "RELIANCE"
        assert result.lots_hedged == 2  # 500 // 250 = 2
        assert result.shares_hedged == 500  # 2 * 250
        assert result.hedge_ratio == 1.0
        assert result.effectiveness_pct == 100.0

    def test_partial_hedge_odd_shares(self):
        h = _holding("RELIANCE", 600, 2800.0)
        result = suggest_stock_futures_hedge(h, futures_price=2810.0, days_to_expiry=20)
        assert result is not None
        assert result.lots_hedged == 2  # 600 // 250 = 2
        assert result.shares_hedged == 500
        assert result.hedge_ratio < 1.0

    def test_not_enough_shares(self):
        h = _holding("RELIANCE", 100, 2800.0)  # 100 < 250 lot size
        result = suggest_stock_futures_hedge(h, futures_price=2810.0)
        assert result is None

    def test_non_fno_stock(self):
        h = _holding("UNKNOWN_STOCK", 1000, 500.0)
        result = suggest_stock_futures_hedge(h, futures_price=505.0)
        assert result is None  # lot_size = 0

    def test_auto_futures_price(self):
        h = _holding("RELIANCE", 500, 2800.0)
        result = suggest_stock_futures_hedge(h, days_to_expiry=20)
        assert result is not None
        assert result.entry_price > 2800.0  # Auto-estimated carry

    def test_margin_calculation(self):
        h = _holding("RELIANCE", 500, 2800.0)
        result = suggest_stock_futures_hedge(h, futures_price=2810.0, days_to_expiry=20)
        assert result is not None
        assert result.margin_required > 0

    def test_basis_cost(self):
        h = _holding("RELIANCE", 500, 2800.0)
        result = suggest_stock_futures_hedge(h, futures_price=2810.0, days_to_expiry=20)
        assert result is not None
        assert result.basis_cost == 10.0 * 500  # (2810 - 2800) * 500

    def test_annualized_carry(self):
        h = _holding("RELIANCE", 500, 2800.0)
        result = suggest_stock_futures_hedge(h, futures_price=2814.0, days_to_expiry=20)
        assert result is not None
        assert result.annualized_carry_cost_pct > 0

    def test_high_carry_warning(self):
        h = _holding("RELIANCE", 500, 2800.0)
        # Very rich basis: 2% for 20 days = ~36% annualized
        result = suggest_stock_futures_hedge(h, futures_price=2856.0, days_to_expiry=20)
        assert result is not None
        assert "rich" in result.notes.lower()

    def test_low_carry_favorable(self):
        h = _holding("RELIANCE", 500, 2800.0)
        result = suggest_stock_futures_hedge(h, futures_price=2803.0, days_to_expiry=20)
        assert result is not None
        assert "favorable" in result.notes.lower() or "low" in result.notes.lower()


# ── suggest_index_futures_hedge ─────────────────────────────────


class TestIndexFuturesHedge:
    def test_basic_index_hedge(self):
        p = _portfolio(1500000.0)
        result = suggest_index_futures_hedge(p, nifty_futures=22600.0, nifty_spot=22500.0)
        assert result.portfolio_value == 1500000.0
        assert result.lots_full_hedge >= 1
        assert result.margin_full > 0

    def test_beta_adjusted_lots(self):
        p = _portfolio(3000000.0)
        result_b1 = suggest_index_futures_hedge(p, nifty_futures=22600.0, portfolio_beta=1.0)
        result_b15 = suggest_index_futures_hedge(p, nifty_futures=22600.0, portfolio_beta=1.5)
        assert result_b15.lots_full_hedge >= result_b1.lots_full_hedge

    def test_partial_hedge(self):
        p = _portfolio(3000000.0)
        result = suggest_index_futures_hedge(p, nifty_futures=22600.0, hedge_ratio=0.5)
        full = suggest_index_futures_hedge(p, nifty_futures=22600.0, hedge_ratio=1.0)
        assert result.lots_full_hedge <= full.lots_full_hedge

    def test_basis_cost_calculated(self):
        p = _portfolio(1500000.0)
        result = suggest_index_futures_hedge(p, nifty_futures=22600.0, nifty_spot=22500.0)
        assert result.basis_cost > 0  # Futures above spot

    def test_hedge_effectiveness(self):
        p = _portfolio(1500000.0)
        result = suggest_index_futures_hedge(p, nifty_futures=22600.0, nifty_spot=22500.0)
        assert result.hedge_effectiveness > 0


# ── compare_hedge_methods ───────────────────────────────────────


class TestCompareHedgeMethods:
    def test_returns_four_methods(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, nifty_spot=22500.0, nifty_futures=22600.0)
        assert len(result.methods) == 4
        method_types = {m.method for m in result.methods}
        assert method_types == {"futures", "protective_put", "bear_spread", "collar"}

    def test_has_recommendation(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, nifty_spot=22500.0, nifty_futures=22600.0)
        assert result.recommended != ""
        assert result.rationale != ""

    def test_futures_method_properties(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, nifty_spot=22500.0, nifty_futures=22600.0)
        futures_method = [m for m in result.methods if m.method == "futures"][0]
        assert futures_method.complexity == "simple"
        assert futures_method.max_protection_pct == 100.0
        assert len(futures_method.pros) > 0
        assert len(futures_method.cons) > 0

    def test_high_iv_recommends_futures(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, volatility=0.25)
        assert "futures" in result.recommended.lower()

    def test_low_iv_recommends_puts(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, volatility=0.10)
        assert "put" in result.recommended.lower()

    def test_normal_iv_recommends_collar(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, volatility=0.15)
        assert "collar" in result.recommended.lower()

    def test_small_portfolio_recommends_futures(self):
        p = _portfolio(300000.0)
        result = compare_hedge_methods(p, volatility=0.15)
        assert "futures" in result.recommended.lower()

    def test_all_methods_have_costs(self):
        p = _portfolio(1500000.0)
        result = compare_hedge_methods(p, nifty_spot=22500.0, nifty_futures=22600.0)
        for m in result.methods:
            assert isinstance(m.cost, float)
            assert isinstance(m.margin_required, float)
            assert isinstance(m.rolling_cost_annual, float)


# ── futures_income_from_holdings ────────────────────────────────


class TestFuturesIncome:
    def test_income_report_basic(self):
        holdings = [_holding("RELIANCE", 500, 2800.0)]
        p = _portfolio(1400000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(p, days_to_expiry=20)
        assert result.eligible_count == 1
        assert result.total_income > 0
        assert result.avg_annualized_yield_pct > 0

    def test_income_with_explicit_futures(self):
        holdings = [_holding("RELIANCE", 500, 2800.0)]
        p = _portfolio(1400000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(
            p, days_to_expiry=20,
            futures_premiums={"RELIANCE": 2820.0},
        )
        assert result.eligible_count == 1
        entry = result.entries[0]
        assert entry.futures_price == 2820.0
        assert entry.basis == 20.0

    def test_income_backwardation_no_income(self):
        holdings = [_holding("RELIANCE", 500, 2800.0)]
        p = _portfolio(1400000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(
            p, days_to_expiry=20,
            futures_premiums={"RELIANCE": 2780.0},  # Below spot
        )
        entry = result.entries[0]
        assert entry.basis < 0
        assert entry.risk_level == "high"
        assert "backwardation" in entry.notes.lower()

    def test_income_not_enough_shares(self):
        holdings = [_holding("RELIANCE", 100, 2800.0)]  # < 1 lot
        p = _portfolio(280000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(p, days_to_expiry=20)
        assert result.eligible_count == 0

    def test_income_multiple_holdings(self):
        holdings = [
            _holding("RELIANCE", 500, 2800.0),
            _holding("TCS", 300, 3500.0),
        ]
        p = _portfolio(2450000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(p, days_to_expiry=20)
        assert result.eligible_count == 2
        assert result.total_income > 0

    def test_income_margin_calculated(self):
        holdings = [_holding("RELIANCE", 500, 2800.0)]
        p = _portfolio(1400000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(p, days_to_expiry=20)
        assert result.total_margin_required > 0

    def test_income_summary_populated(self):
        holdings = [_holding("RELIANCE", 500, 2800.0)]
        p = _portfolio(1400000.0, fno_eligible=holdings)
        result = futures_income_from_holdings(p, days_to_expiry=20)
        assert "Eligible" in result.summary
        assert "income" in result.summary.lower()

    def test_income_risk_levels(self):
        holdings = [_holding("RELIANCE", 500, 2800.0)]
        p = _portfolio(1400000.0, fno_eligible=holdings)
        # Low carry = low risk
        result = futures_income_from_holdings(
            p, days_to_expiry=20,
            futures_premiums={"RELIANCE": 2802.0},
        )
        entry = result.entries[0]
        assert entry.risk_level in ("low", "medium", "high")

    def test_empty_portfolio(self):
        p = _portfolio(0, fno_eligible=[])
        result = futures_income_from_holdings(p, days_to_expiry=20)
        assert result.eligible_count == 0
        assert result.total_income == 0
