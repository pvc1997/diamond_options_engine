"""Tests for MCP unified portfolio tools (Phase U1).

Tests the same logic the MCP tools expose, using the underlying library
functions directly (MCP server has its own venv with fastmcp).
"""

from __future__ import annotations

import pytest

from diamond_options.risk.unified_portfolio import (
    build_unified_portfolio,
    unified_daily_summary,
    unified_exposure_by_symbol,
)


def _sample_stocks():
    return [{
        "symbol": "RELIANCE", "shares": 500, "current_price": 2800,
        "avg_price": 2600, "market_value": 1400000,
        "unrealized_pnl": 100000, "fno_eligible": True,
    }]


def _sample_options():
    return [{
        "symbol": "NIFTY", "strike": 23000, "option_type": "CE",
        "lots": -2, "lot_size": 65, "avg_price": 150, "current_price": 120,
        "direction": "short", "delta": -80, "theta": 200, "vega": -500,
        "margin": 150000,
    }]


def _sample_futures():
    return [{
        "symbol": "RELIANCE", "lots": -2, "lot_size": 250,
        "avg_price": 2850, "current_price": 2800,
        "direction": "short", "margin": 200000,
    }]


class TestUnifiedPortfolioStatusTool:
    """Mirrors unified_portfolio_status MCP tool."""

    def test_full_portfolio_summary(self):
        p = build_unified_portfolio(
            stock_holdings=_sample_stocks(),
            options_positions=_sample_options(),
            futures_positions=_sample_futures(),
            options_cash=300000, options_margin=150000,
            futures_cash=200000, futures_margin=200000,
            capital=2000000,
        )
        summary = unified_daily_summary(p, 2000000)
        assert "date" in summary
        assert summary["equity"]["count"] == 1
        assert summary["options"]["count"] == 1
        assert summary["futures"]["count"] == 1
        assert summary["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")

    def test_empty_portfolio_summary(self):
        p = build_unified_portfolio(capital=500000)
        summary = unified_daily_summary(p, 500000)
        assert summary["nav"] == 0
        assert summary["total_unrealized_pnl"] == 0


class TestUnifiedExposureAnalysisTool:
    """Mirrors unified_exposure_analysis MCP tool."""

    def test_per_symbol_exposure(self):
        p = build_unified_portfolio(
            stock_holdings=_sample_stocks(),
            futures_positions=_sample_futures(),
        )
        exposure = unified_exposure_by_symbol(p)
        output = {"symbol_count": len(exposure), "exposures": exposure}
        assert output["symbol_count"] >= 1
        rel = next(e for e in exposure if e["symbol"] == "RELIANCE")
        assert rel["hedge_status"] in ("hedged", "partially_hedged", "over_hedged", "lightly_hedged", "unhedged")


class TestUnifiedRiskDashboardTool:
    """Mirrors unified_risk_dashboard MCP tool."""

    def test_risk_dashboard_output(self):
        p = build_unified_portfolio(
            stock_holdings=_sample_stocks(),
            options_positions=_sample_options(),
            futures_positions=_sample_futures(),
            options_cash=300000, options_margin=150000,
            futures_cash=200000, futures_margin=200000,
            capital=2000000,
        )
        # Mimic the MCP tool output structure
        output = {
            "risk_level": p.risk_level,
            "margin": {
                "total_used": p.total_margin_used,
                "utilization_pct": p.margin_utilization_pct,
                "options_margin": p.options.margin_used,
                "futures_margin": p.futures.margin_used,
            },
            "hedge": {
                "hedge_ratio": p.hedge_ratio,
                "equity_value": p.equity.total_value,
            },
            "alerts": [
                {"level": a.level, "category": a.category, "message": a.message}
                for a in p.alerts
            ],
        }
        assert output["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert output["margin"]["total_used"] == 350000
        assert output["hedge"]["equity_value"] == 1400000

    def test_high_margin_triggers_alerts(self):
        p = build_unified_portfolio(
            futures_positions=[{
                "symbol": "NIFTY", "lots": 5, "lot_size": 65,
                "avg_price": 22500, "current_price": 22500,
                "direction": "long", "margin": 800000,
            }],
            futures_margin=800000,
            capital=1000000,
        )
        assert p.risk_level in ("HIGH", "CRITICAL")
        margin_alerts = [a for a in p.alerts if a.category == "margin"]
        assert len(margin_alerts) > 0
