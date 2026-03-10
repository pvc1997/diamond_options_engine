"""Tests for unified portfolio view (Phase U1)."""

from __future__ import annotations

import pytest

from diamond_options.risk.unified_portfolio import (
    UnifiedPosition,
    UnifiedRiskAlert,
    EquitySummary,
    OptionsSummary,
    FuturesSummary,
    UnifiedPortfolioRisk,
    build_unified_portfolio,
    generate_unified_alerts,
    unified_exposure_by_symbol,
    unified_daily_summary,
)


# ── Fixtures ───────────────────────────────────────────────────


def sample_stocks():
    return [
        {
            "symbol": "RELIANCE",
            "shares": 500,
            "current_price": 2800,
            "avg_price": 2600,
            "market_value": 1400000,
            "unrealized_pnl": 100000,
            "fno_eligible": True,
        },
        {
            "symbol": "TCS",
            "shares": 150,
            "current_price": 3500,
            "avg_price": 3400,
            "market_value": 525000,
            "unrealized_pnl": 15000,
            "fno_eligible": True,
        },
    ]


def sample_options():
    return [
        {
            "symbol": "NIFTY",
            "strike": 23000,
            "option_type": "CE",
            "lots": -2,
            "lot_size": 65,
            "avg_price": 150,
            "current_price": 120,
            "direction": "short",
            "delta": -80,
            "theta": 200,
            "vega": -500,
            "margin": 150000,
        },
        {
            "symbol": "NIFTY",
            "strike": 22500,
            "option_type": "PE",
            "lots": -2,
            "lot_size": 65,
            "avg_price": 100,
            "current_price": 80,
            "direction": "short",
            "delta": 40,
            "theta": 150,
            "vega": -300,
            "margin": 120000,
        },
    ]


def sample_futures():
    return [
        {
            "symbol": "RELIANCE",
            "lots": -2,
            "lot_size": 250,
            "avg_price": 2850,
            "current_price": 2800,
            "direction": "short",
            "margin": 200000,
        },
        {
            "symbol": "NIFTY",
            "lots": 1,
            "lot_size": 65,
            "avg_price": 22500,
            "current_price": 22600,
            "direction": "long",
            "margin": 170000,
        },
    ]


# ── Dataclass Tests ────────────────────────────────────────────


class TestUnifiedPosition:
    def test_creation(self):
        p = UnifiedPosition(
            asset_type="equity", symbol="RELIANCE", direction="long",
            quantity=500, notional_value=1400000, unrealized_pnl=100000,
            margin_used=0, source="stock_engine", detail="500 shares",
        )
        assert p.asset_type == "equity"
        assert p.symbol == "RELIANCE"
        assert p.notional_value == 1400000

    def test_frozen(self):
        p = UnifiedPosition(
            "equity", "RELIANCE", "long", 500, 1400000, 0, 0, "stock_engine", "",
        )
        with pytest.raises(AttributeError):
            p.symbol = "TCS"


class TestUnifiedRiskAlert:
    def test_creation(self):
        a = UnifiedRiskAlert("warning", "margin", "Margin high")
        assert a.level == "warning"
        assert a.category == "margin"


# ── build_unified_portfolio Tests ──────────────────────────────


class TestBuildUnifiedPortfolio:
    def test_empty_portfolio(self):
        p = build_unified_portfolio()
        assert p.total_nav == 0
        assert p.equity.count == 0
        assert p.options.count == 0
        assert p.futures.count == 0
        assert len(p.all_positions) == 0
        assert p.risk_level == "LOW"

    def test_equity_only(self):
        p = build_unified_portfolio(stock_holdings=sample_stocks())
        assert p.equity.count == 2
        assert p.equity.total_value == 1925000
        assert p.equity.unrealized_pnl == 115000
        assert p.options.count == 0
        assert p.futures.count == 0
        assert len(p.all_positions) == 2

    def test_options_only(self):
        p = build_unified_portfolio(
            options_positions=sample_options(),
            options_cash=300000,
            options_margin=270000,
        )
        assert p.options.count == 2
        assert p.options.short_count == 2
        assert p.options.long_count == 0
        assert p.options.net_delta == -40  # -80 + 40
        assert p.options.net_theta == 350  # 200 + 150
        assert p.options.margin_used == 270000

    def test_futures_only(self):
        p = build_unified_portfolio(
            futures_positions=sample_futures(),
            futures_cash=200000,
            futures_margin=370000,
        )
        assert p.futures.count == 2
        assert p.futures.long_count == 1
        assert p.futures.short_count == 1
        assert p.futures.margin_used == 370000

    def test_full_portfolio(self):
        p = build_unified_portfolio(
            stock_holdings=sample_stocks(),
            options_positions=sample_options(),
            futures_positions=sample_futures(),
            options_cash=300000,
            options_margin=270000,
            futures_cash=200000,
            futures_margin=370000,
            capital=2000000,
        )
        assert p.equity.count == 2
        assert p.options.count == 2
        assert p.futures.count == 2
        assert len(p.all_positions) == 6
        assert p.total_margin_used == 640000  # 270k + 370k
        assert p.margin_utilization_pct == 32.0  # 640k / 2M * 100

    def test_by_symbol_grouping(self):
        p = build_unified_portfolio(
            stock_holdings=sample_stocks(),
            futures_positions=sample_futures(),
        )
        assert "RELIANCE" in p.by_symbol
        reliance_positions = p.by_symbol["RELIANCE"]
        types = {pos.asset_type for pos in reliance_positions}
        assert "equity" in types
        assert "future" in types

    def test_nav_calculation(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "RELIANCE", "shares": 100, "current_price": 2800,
                "avg_price": 2800, "market_value": 280000,
                "unrealized_pnl": 0, "fno_eligible": True,
            }],
            options_cash=100000,
            futures_cash=50000,
        )
        # NAV = equity_value + options_cash + futures_cash + opt_pnl + fut_pnl
        assert p.total_nav == 430000  # 280k + 100k + 50k

    def test_hedge_ratio(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "RELIANCE", "shares": 500, "current_price": 2800,
                "avg_price": 2600, "market_value": 1400000,
                "unrealized_pnl": 100000, "fno_eligible": True,
            }],
            futures_positions=[{
                "symbol": "RELIANCE", "lots": -2, "lot_size": 250,
                "avg_price": 2850, "current_price": 2800,
                "direction": "short", "margin": 200000,
            }],
        )
        # Short futures notional = 2800 * 500 = 1,400,000
        # Equity value = 1,400,000
        # Hedge ratio = 1.0
        assert abs(p.hedge_ratio - 1.0) < 0.1

    def test_risk_level_low(self):
        p = build_unified_portfolio(capital=1000000)
        assert p.risk_level == "LOW"

    def test_risk_level_with_high_margin(self):
        p = build_unified_portfolio(
            futures_positions=[{
                "symbol": "NIFTY", "lots": 5, "lot_size": 65,
                "avg_price": 22500, "current_price": 22500,
                "direction": "long", "margin": 500000,
            }],
            futures_margin=500000,
            capital=600000,  # 83% margin util -> critical
        )
        assert p.risk_level in ("HIGH", "CRITICAL")

    def test_futures_pnl_long(self):
        p = build_unified_portfolio(
            futures_positions=[{
                "symbol": "NIFTY", "lots": 1, "lot_size": 65,
                "avg_price": 22500, "current_price": 22600,
                "direction": "long", "margin": 170000,
            }],
        )
        # Long P&L = (22600 - 22500) * 65 = 6500
        assert p.futures.unrealized_pnl == 6500

    def test_futures_pnl_short(self):
        p = build_unified_portfolio(
            futures_positions=[{
                "symbol": "RELIANCE", "lots": -2, "lot_size": 250,
                "avg_price": 2850, "current_price": 2800,
                "direction": "short", "margin": 200000,
            }],
        )
        # Short P&L = (2850 - 2800) * 500 = 25000
        assert p.futures.unrealized_pnl == 25000

    def test_symbol_uppercased(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "reliance", "shares": 100, "current_price": 2800,
                "avg_price": 2800, "market_value": 280000,
                "unrealized_pnl": 0, "fno_eligible": True,
            }],
        )
        assert "RELIANCE" in p.by_symbol


# ── Alert Generation Tests ─────────────────────────────────────


class TestGenerateUnifiedAlerts:
    def test_no_alerts_empty(self):
        eq = EquitySummary(0, 0, 0, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
        alerts = generate_unified_alerts(eq, opt, fut, 0, 500000, {}, 0)
        # No positions → no alerts
        assert all(a.level != "critical" for a in alerts)

    def test_critical_margin(self):
        eq = EquitySummary(0, 0, 0, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
        alerts = generate_unified_alerts(eq, opt, fut, 450000, 500000, {}, 0)
        margin_alerts = [a for a in alerts if a.category == "margin"]
        assert any(a.level == "critical" for a in margin_alerts)

    def test_breach_margin(self):
        eq = EquitySummary(0, 0, 0, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
        alerts = generate_unified_alerts(eq, opt, fut, 350000, 500000, {}, 0)
        margin_alerts = [a for a in alerts if a.category == "margin"]
        assert any(a.level == "breach" for a in margin_alerts)

    def test_warning_margin(self):
        eq = EquitySummary(0, 0, 0, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
        alerts = generate_unified_alerts(eq, opt, fut, 250000, 500000, {}, 0)
        margin_alerts = [a for a in alerts if a.category == "margin"]
        assert any(a.level == "warning" for a in margin_alerts)

    def test_concentration_alert(self):
        eq = EquitySummary(1, 1000000, 100, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
        by_sym = {
            "RELIANCE": [UnifiedPosition(
                "equity", "RELIANCE", "long", 500, 1000000, 0, 0, "stock_engine", "",
            )],
        }
        alerts = generate_unified_alerts(eq, opt, fut, 0, 500000, by_sym, 1000000)
        conc = [a for a in alerts if a.category == "concentration"]
        assert len(conc) > 0

    def test_hedge_detected(self):
        eq = EquitySummary(1, 1400000, 100, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(1, 0, 1, -1400000, 1400000, 200000, 0, 0)
        by_sym = {
            "RELIANCE": [
                UnifiedPosition("equity", "RELIANCE", "long", 500, 1400000, 0, 0, "stock_engine", ""),
                UnifiedPosition("future", "RELIANCE", "short", 2, 1400000, 25000, 200000, "futures_ledger", ""),
            ],
        }
        alerts = generate_unified_alerts(eq, opt, fut, 200000, 2000000, by_sym, 1400000)
        hedge_alerts = [a for a in alerts if a.category == "hedge"]
        assert any("hedged" in a.message.lower() for a in hedge_alerts)

    def test_over_hedged_alert(self):
        eq = EquitySummary(1, 500000, 100, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(1, 0, 1, -800000, 800000, 200000, 0, 0)
        by_sym = {
            "RELIANCE": [
                UnifiedPosition("equity", "RELIANCE", "long", 200, 500000, 0, 0, "stock_engine", ""),
                UnifiedPosition("future", "RELIANCE", "short", 3, 800000, 0, 200000, "futures_ledger", ""),
            ],
        }
        alerts = generate_unified_alerts(eq, opt, fut, 200000, 2000000, by_sym, 500000)
        hedge_alerts = [a for a in alerts if a.category == "hedge"]
        assert any("over-hedged" in a.message.lower() for a in hedge_alerts)

    def test_unhedged_large_equity(self):
        eq = EquitySummary(1, 800000, 100, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
        alerts = generate_unified_alerts(eq, opt, fut, 0, 2000000, {}, 800000)
        hedge_alerts = [a for a in alerts if a.category == "hedge"]
        assert any("no hedge" in a.message.lower() for a in hedge_alerts)

    def test_high_leverage_alert(self):
        eq = EquitySummary(0, 0, 0, 0)
        opt = OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
        fut = FuturesSummary(2, 2, 0, 2000000, 2000000, 300000, 0, 0)
        alerts = generate_unified_alerts(eq, opt, fut, 300000, 500000, {}, 0)
        exp_alerts = [a for a in alerts if a.category == "exposure"]
        assert any("leverage" in a.message.lower() for a in exp_alerts)


# ── Exposure Analysis Tests ────────────────────────────────────


class TestUnifiedExposureBySymbol:
    def test_hedged_symbol(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "RELIANCE", "shares": 500, "current_price": 2800,
                "avg_price": 2600, "market_value": 1400000,
                "unrealized_pnl": 100000, "fno_eligible": True,
            }],
            futures_positions=[{
                "symbol": "RELIANCE", "lots": -2, "lot_size": 250,
                "avg_price": 2850, "current_price": 2800,
                "direction": "short", "margin": 200000,
            }],
        )
        exposure = unified_exposure_by_symbol(p)
        rel = next(e for e in exposure if e["symbol"] == "RELIANCE")
        assert rel["hedge_status"] == "hedged"
        assert rel["equity_value"] == 1400000
        assert rel["futures_exposure"] < 0  # Short

    def test_unhedged_symbol(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "TCS", "shares": 150, "current_price": 3500,
                "avg_price": 3400, "market_value": 525000,
                "unrealized_pnl": 15000, "fno_eligible": True,
            }],
        )
        exposure = unified_exposure_by_symbol(p)
        tcs = next(e for e in exposure if e["symbol"] == "TCS")
        assert tcs["hedge_status"] == "unhedged"

    def test_derivatives_only(self):
        p = build_unified_portfolio(
            futures_positions=[{
                "symbol": "NIFTY", "lots": 1, "lot_size": 65,
                "avg_price": 22500, "current_price": 22600,
                "direction": "long", "margin": 170000,
            }],
        )
        exposure = unified_exposure_by_symbol(p)
        nifty = next(e for e in exposure if e["symbol"] == "NIFTY")
        assert nifty["hedge_status"] == "derivatives_only"
        assert nifty["equity_value"] == 0

    def test_multiple_symbols(self):
        p = build_unified_portfolio(
            stock_holdings=sample_stocks(),
            futures_positions=sample_futures(),
        )
        exposure = unified_exposure_by_symbol(p)
        symbols = {e["symbol"] for e in exposure}
        assert "RELIANCE" in symbols
        assert "TCS" in symbols
        assert "NIFTY" in symbols

    def test_pnl_aggregation(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "RELIANCE", "shares": 500, "current_price": 2800,
                "avg_price": 2600, "market_value": 1400000,
                "unrealized_pnl": 100000, "fno_eligible": True,
            }],
            futures_positions=[{
                "symbol": "RELIANCE", "lots": -2, "lot_size": 250,
                "avg_price": 2850, "current_price": 2800,
                "direction": "short", "margin": 200000,
            }],
        )
        exposure = unified_exposure_by_symbol(p)
        rel = next(e for e in exposure if e["symbol"] == "RELIANCE")
        # Equity PnL 100k + Futures PnL 25k = 125k
        assert rel["unrealized_pnl"] == 125000

    def test_asset_types_listed(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "RELIANCE", "shares": 500, "current_price": 2800,
                "avg_price": 2600, "market_value": 1400000,
                "unrealized_pnl": 0, "fno_eligible": True,
            }],
            futures_positions=[{
                "symbol": "RELIANCE", "lots": -2, "lot_size": 250,
                "avg_price": 2850, "current_price": 2800,
                "direction": "short", "margin": 200000,
            }],
        )
        exposure = unified_exposure_by_symbol(p)
        rel = next(e for e in exposure if e["symbol"] == "RELIANCE")
        assert "equity" in rel["asset_types"]
        assert "future" in rel["asset_types"]


# ── Daily Summary Tests ────────────────────────────────────────


class TestUnifiedDailySummary:
    def test_empty_summary(self):
        p = build_unified_portfolio()
        summary = unified_daily_summary(p, capital=500000)
        assert summary["nav"] == 0
        assert summary["total_unrealized_pnl"] == 0
        assert summary["risk_level"] == "LOW"

    def test_full_summary(self):
        p = build_unified_portfolio(
            stock_holdings=sample_stocks(),
            options_positions=sample_options(),
            futures_positions=sample_futures(),
            options_cash=300000,
            options_margin=270000,
            futures_cash=200000,
            futures_margin=370000,
            capital=2000000,
        )
        summary = unified_daily_summary(p, capital=2000000)
        assert "date" in summary
        assert summary["equity"]["count"] == 2
        assert summary["options"]["count"] == 2
        assert summary["futures"]["count"] == 2
        assert summary["margin_used"] == 640000
        assert summary["margin_utilization_pct"] == 32.0
        assert len(summary["positions_by_symbol"]) > 0

    def test_total_pnl(self):
        p = build_unified_portfolio(
            stock_holdings=[{
                "symbol": "RELIANCE", "shares": 500, "current_price": 2800,
                "avg_price": 2600, "market_value": 1400000,
                "unrealized_pnl": 100000, "fno_eligible": True,
            }],
            futures_positions=[{
                "symbol": "NIFTY", "lots": 1, "lot_size": 65,
                "avg_price": 22500, "current_price": 22600,
                "direction": "long", "margin": 170000,
            }],
        )
        summary = unified_daily_summary(p, capital=2000000)
        # Equity: 100k, Futures: 6500
        assert summary["total_unrealized_pnl"] == 106500

    def test_available_margin(self):
        p = build_unified_portfolio(
            futures_margin=200000,
            capital=500000,
        )
        summary = unified_daily_summary(p, capital=500000)
        assert summary["available_margin"] == 300000

    def test_positions_by_symbol_in_summary(self):
        p = build_unified_portfolio(
            stock_holdings=sample_stocks(),
            futures_positions=sample_futures(),
        )
        summary = unified_daily_summary(p)
        pos_syms = {ps["symbol"] for ps in summary["positions_by_symbol"]}
        assert "RELIANCE" in pos_syms
        assert "TCS" in pos_syms

    def test_theta_in_options_summary(self):
        p = build_unified_portfolio(
            options_positions=sample_options(),
            options_cash=300000,
            options_margin=270000,
        )
        summary = unified_daily_summary(p)
        assert summary["options"]["daily_theta"] == 350
