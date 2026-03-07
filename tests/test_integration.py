"""Tests for cross-engine integration (stock_bridge, overlay, hedge)."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from diamond_options.integration.stock_bridge import (
    StockHolding,
    StockPortfolio,
    get_stock_holdings,
    _ticker_to_fno_symbol,
)
from diamond_options.integration.overlay import (
    CoveredCallSetup,
    ProtectivePutSetup,
    CollarSetup,
    suggest_covered_calls,
    suggest_protective_puts,
    suggest_collar,
)
from diamond_options.integration.hedge import (
    PortfolioHedgeAnalysis,
    HedgeOption,
    analyze_portfolio_hedge,
    covered_call_income_report,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_stock_db():
    """Create a temporary SQLite DB mimicking diamond_stock_engine ledger."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE holdings (
            ticker TEXT PRIMARY KEY,
            shares INTEGER NOT NULL DEFAULT 0,
            avg_price REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO state (key, value) VALUES ('cash', '200000');
        INSERT INTO state (key, value) VALUES ('initial_capital', '1000000');

        INSERT INTO holdings (ticker, shares, avg_price) VALUES ('RELIANCE.NS', 500, 2400.0);
        INSERT INTO holdings (ticker, shares, avg_price) VALUES ('TCS.NS', 300, 3500.0);
        INSERT INTO holdings (ticker, shares, avg_price) VALUES ('INFY.NS', 600, 1500.0);
        INSERT INTO holdings (ticker, shares, avg_price) VALUES ('HDFCBANK.NS', 550, 1600.0);
    """)
    conn.close()

    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def reliance_holding():
    """A Reliance holding with 500 shares."""
    return StockHolding(
        ticker="RELIANCE.NS",
        fno_symbol="RELIANCE",
        shares=500,
        avg_price=2400.0,
        current_price=2600.0,
        market_value=1300000.0,
        unrealized_pnl=100000.0,
        unrealized_pnl_pct=4.17,
        weight_pct=25.0,
    )


@pytest.fixture
def tcs_holding():
    """A TCS holding with 300 shares."""
    return StockHolding(
        ticker="TCS.NS",
        fno_symbol="TCS",
        shares=300,
        avg_price=3500.0,
        current_price=3800.0,
        market_value=1140000.0,
        unrealized_pnl=90000.0,
        unrealized_pnl_pct=8.57,
        weight_pct=22.0,
    )


@pytest.fixture
def sample_portfolio(reliance_holding, tcs_holding):
    """Portfolio with F&O-eligible stocks."""
    return StockPortfolio(
        strategy="test",
        holdings=[reliance_holding, tcs_holding],
        total_value=2440000.0,
        cash=200000.0,
        nav=2640000.0,
        num_stocks=2,
        fno_eligible=[reliance_holding, tcs_holding],
        fno_eligible_value=2440000.0,
        fno_eligible_pct=92.42,
    )


# ═══════════════════════════════════════════════════════════════
# Stock Bridge Tests
# ═══════════════════════════════════════════════════════════════


class TestTickerConversion:
    def test_ns_suffix(self):
        assert _ticker_to_fno_symbol("RELIANCE.NS") == "RELIANCE"

    def test_bo_suffix(self):
        assert _ticker_to_fno_symbol("TCS.BO") == "TCS"

    def test_no_suffix(self):
        assert _ticker_to_fno_symbol("INFY") == "INFY"


class TestGetStockHoldings:
    def test_reads_holdings(self, mock_stock_db):
        portfolio = get_stock_holdings("test", db_path=mock_stock_db)
        assert portfolio.num_stocks == 4
        assert portfolio.cash == 200000.0

    def test_fno_eligible(self, mock_stock_db):
        portfolio = get_stock_holdings("test", db_path=mock_stock_db)
        fno_symbols = [h.fno_symbol for h in portfolio.fno_eligible]
        assert "RELIANCE" in fno_symbols
        assert "TCS" in fno_symbols
        assert "INFY" in fno_symbols

    def test_with_current_prices(self, mock_stock_db):
        prices = {
            "RELIANCE.NS": 2600.0,
            "TCS.NS": 3800.0,
            "INFY.NS": 1600.0,
            "HDFCBANK.NS": 1700.0,
        }
        portfolio = get_stock_holdings("test", current_prices=prices, db_path=mock_stock_db)
        rel = next(h for h in portfolio.holdings if h.fno_symbol == "RELIANCE")
        assert rel.current_price == 2600.0
        assert rel.unrealized_pnl > 0  # Bought at 2400, now 2600

    def test_weight_calculation(self, mock_stock_db):
        portfolio = get_stock_holdings("test", db_path=mock_stock_db)
        total_weight = sum(h.weight_pct for h in portfolio.holdings)
        # Weights should sum to ~100% of equity portion (not counting cash)
        assert total_weight > 0
        assert total_weight < 100  # Cash takes some weight

    def test_missing_db(self):
        portfolio = get_stock_holdings("nonexistent_strategy")
        assert portfolio.num_stocks == 0
        assert portfolio.nav == 0

    def test_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE holdings (ticker TEXT PRIMARY KEY, shares INTEGER, avg_price REAL);
            CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO state (key, value) VALUES ('cash', '500000');
        """)
        conn.close()

        portfolio = get_stock_holdings("test", db_path=db_path)
        assert portfolio.num_stocks == 0
        assert portfolio.cash == 500000.0
        db_path.unlink(missing_ok=True)

    def test_fno_eligible_value(self, mock_stock_db):
        portfolio = get_stock_holdings("test", db_path=mock_stock_db)
        assert portfolio.fno_eligible_value > 0
        assert portfolio.fno_eligible_pct > 0


# ═══════════════════════════════════════════════════════════════
# Covered Call Tests
# ═══════════════════════════════════════════════════════════════


class TestCoveredCalls:
    def test_returns_suggestions(self, reliance_holding):
        calls = suggest_covered_calls(reliance_holding, days_to_expiry=30)
        assert len(calls) == 3
        assert all(isinstance(c, CoveredCallSetup) for c in calls)

    def test_strike_above_spot(self, reliance_holding):
        calls = suggest_covered_calls(reliance_holding, spot=2600, days_to_expiry=30)
        for call in calls:
            assert call.strike >= 2600  # All OTM

    def test_lots_from_shares(self, reliance_holding):
        """500 shares, RELIANCE lot = 250 → 2 lots coverable."""
        calls = suggest_covered_calls(reliance_holding, days_to_expiry=30)
        assert calls[0].lots_coverable == 2  # 500 // 250

    def test_premium_positive(self, reliance_holding):
        calls = suggest_covered_calls(reliance_holding, days_to_expiry=30)
        for call in calls:
            assert call.premium > 0
            assert call.total_premium > 0

    def test_annualized_yield(self, reliance_holding):
        calls = suggest_covered_calls(reliance_holding, days_to_expiry=30)
        for call in calls:
            assert call.annualized_yield_pct > 0

    def test_breakeven_below_spot(self, reliance_holding):
        calls = suggest_covered_calls(reliance_holding, spot=2600, days_to_expiry=30)
        for call in calls:
            assert call.breakeven < 2600  # Premium provides downside buffer

    def test_not_enough_shares(self):
        """Holding with fewer shares than 1 lot should return empty."""
        small = StockHolding(
            ticker="RELIANCE.NS", fno_symbol="RELIANCE",
            shares=100, avg_price=2400, current_price=2600,
            market_value=260000, unrealized_pnl=20000,
            unrealized_pnl_pct=8.33, weight_pct=10,
        )
        calls = suggest_covered_calls(small)
        assert len(calls) == 0  # 100 < 250 lot size

    def test_non_fno_stock(self):
        """Non-F&O stock should return empty."""
        non_fno = StockHolding(
            ticker="SOMESMALL.NS", fno_symbol="SOMESMALL",
            shares=1000, avg_price=100, current_price=110,
            market_value=110000, unrealized_pnl=10000,
            unrealized_pnl_pct=10, weight_pct=5,
        )
        calls = suggest_covered_calls(non_fno)
        assert len(calls) == 0

    def test_moneyness_label(self, reliance_holding):
        calls = suggest_covered_calls(reliance_holding, spot=2600, days_to_expiry=30)
        for call in calls:
            assert call.moneyness in ("ITM", "ATM", "OTM")


# ═══════════════════════════════════════════════════════════════
# Protective Put Tests
# ═══════════════════════════════════════════════════════════════


class TestProtectivePuts:
    def test_returns_suggestions(self, reliance_holding):
        puts = suggest_protective_puts(reliance_holding, days_to_expiry=30)
        assert len(puts) == 3
        assert all(isinstance(p, ProtectivePutSetup) for p in puts)

    def test_strike_below_spot(self, reliance_holding):
        puts = suggest_protective_puts(reliance_holding, spot=2600, days_to_expiry=30)
        for put in puts:
            assert put.strike <= 2600  # All OTM puts

    def test_premium_positive(self, reliance_holding):
        puts = suggest_protective_puts(reliance_holding, days_to_expiry=30)
        for put in puts:
            assert put.premium > 0
            assert put.total_cost > 0

    def test_cost_as_pct(self, reliance_holding):
        puts = suggest_protective_puts(reliance_holding, days_to_expiry=30)
        for put in puts:
            assert put.cost_as_pct_of_holding > 0
            assert put.annualized_cost_pct > 0

    def test_deeper_otm_cheaper(self, reliance_holding):
        puts = suggest_protective_puts(reliance_holding, spot=2600, days_to_expiry=30)
        # Deeper OTM puts should be cheaper
        assert puts[0].premium >= puts[-1].premium

    def test_protection_level(self, reliance_holding):
        puts = suggest_protective_puts(reliance_holding, days_to_expiry=30)
        for put in puts:
            assert put.protection_level_pct > 0

    def test_non_fno_returns_empty(self):
        non_fno = StockHolding(
            ticker="SMALL.NS", fno_symbol="SMALL",
            shares=1000, avg_price=100, current_price=110,
            market_value=110000, unrealized_pnl=10000,
            unrealized_pnl_pct=10, weight_pct=5,
        )
        puts = suggest_protective_puts(non_fno)
        assert len(puts) == 0


# ═══════════════════════════════════════════════════════════════
# Collar Tests
# ═══════════════════════════════════════════════════════════════


class TestCollar:
    def test_returns_collar(self, reliance_holding):
        collar = suggest_collar(reliance_holding, days_to_expiry=30)
        assert isinstance(collar, CollarSetup)

    def test_call_above_put(self, reliance_holding):
        collar = suggest_collar(reliance_holding, spot=2600, days_to_expiry=30)
        assert collar.call_strike > collar.put_strike

    def test_premiums(self, reliance_holding):
        collar = suggest_collar(reliance_holding, days_to_expiry=30)
        assert collar.call_premium > 0
        assert collar.put_premium > 0

    def test_upside_cap_positive(self, reliance_holding):
        collar = suggest_collar(reliance_holding, spot=2600, days_to_expiry=30)
        assert collar.upside_cap_pct > 0  # Some upside allowed

    def test_downside_floor(self, reliance_holding):
        collar = suggest_collar(reliance_holding, spot=2600, days_to_expiry=30)
        assert collar.downside_floor_pct > 0  # Some downside possible

    def test_non_fno_returns_none(self):
        non_fno = StockHolding(
            ticker="SMALL.NS", fno_symbol="SMALL",
            shares=1000, avg_price=100, current_price=110,
            market_value=110000, unrealized_pnl=10000,
            unrealized_pnl_pct=10, weight_pct=5,
        )
        assert suggest_collar(non_fno) is None

    def test_not_enough_shares_returns_none(self):
        small = StockHolding(
            ticker="RELIANCE.NS", fno_symbol="RELIANCE",
            shares=100, avg_price=2400, current_price=2600,
            market_value=260000, unrealized_pnl=20000,
            unrealized_pnl_pct=8.33, weight_pct=10,
        )
        assert suggest_collar(small) is None

    def test_wider_collar(self, reliance_holding):
        collar = suggest_collar(
            reliance_holding, spot=2600,
            call_otm_pct=0.10, put_otm_pct=0.10,
            days_to_expiry=30,
        )
        assert collar.call_strike > 2600 * 1.05  # Wider than default
        assert collar.put_strike < 2600 * 0.95


# ═══════════════════════════════════════════════════════════════
# Portfolio Hedge Tests
# ═══════════════════════════════════════════════════════════════


class TestPortfolioHedge:
    def test_returns_analysis(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        assert isinstance(result, PortfolioHedgeAnalysis)

    def test_hedge_options(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        assert len(result.hedging_options) >= 4  # Puts + spread + collar

    def test_lots_calculation(self, sample_portfolio):
        result = analyze_portfolio_hedge(
            sample_portfolio, nifty_spot=22500, portfolio_beta=1.0,
        )
        # Portfolio ~24.4L, NIFTY lot = 22500*25 = 562500
        # Lots ≈ 24.4L / 5.625L ≈ 4
        assert result.lots_to_hedge >= 1

    def test_beta_adjustment(self, sample_portfolio):
        low_beta = analyze_portfolio_hedge(
            sample_portfolio, nifty_spot=22500, portfolio_beta=0.5,
        )
        high_beta = analyze_portfolio_hedge(
            sample_portfolio, nifty_spot=22500, portfolio_beta=1.5,
        )
        assert low_beta.lots_to_hedge <= high_beta.lots_to_hedge

    def test_hedge_cost(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        for option in result.hedging_options:
            assert option.total_cost != 0 or option.strategy == "collar"
            assert option.days_to_expiry > 0

    def test_summary(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        assert "Portfolio" in result.summary
        assert "Beta" in result.summary

    def test_hedge_strategies_present(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        strategies = {h.strategy for h in result.hedging_options}
        assert "protective_put" in strategies
        assert "bear_put_spread" in strategies
        assert "collar" in strategies

    def test_partial_hedge(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        assert result.lots_partial_hedge <= result.lots_to_hedge

    def test_annualized_costs(self, sample_portfolio):
        result = analyze_portfolio_hedge(sample_portfolio, nifty_spot=22500)
        for option in result.hedging_options:
            assert option.annualized_cost_pct >= 0


# ═══════════════════════════════════════════════════════════════
# Covered Call Income Report Tests
# ═══════════════════════════════════════════════════════════════


class TestCoveredCallIncome:
    def test_returns_report(self, sample_portfolio):
        report = covered_call_income_report(sample_portfolio, days_to_expiry=30)
        assert "total_monthly_income" in report
        assert "annualized_yield_pct" in report

    def test_income_positive(self, sample_portfolio):
        report = covered_call_income_report(sample_portfolio, days_to_expiry=30)
        assert report["total_monthly_income"] > 0

    def test_stocks_with_calls(self, sample_portfolio):
        report = covered_call_income_report(sample_portfolio, days_to_expiry=30)
        assert report["stocks_with_calls"] >= 1

    def test_detail_fields(self, sample_portfolio):
        report = covered_call_income_report(sample_portfolio, days_to_expiry=30)
        for detail in report["details"]:
            assert "ticker" in detail
            assert "call_strike" in detail
            assert "premium_per_share" in detail
            assert "total_premium" in detail
            assert "annualized_yield_pct" in detail

    def test_fno_eligible_pct(self, sample_portfolio):
        report = covered_call_income_report(sample_portfolio, days_to_expiry=30)
        assert report["fno_eligible_pct"] > 0

    def test_yield_reasonable(self, sample_portfolio):
        report = covered_call_income_report(sample_portfolio, days_to_expiry=30)
        # Annualized yield should be reasonable (2-30% typically)
        assert 0 < report["annualized_yield_pct"] < 100
