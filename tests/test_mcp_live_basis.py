"""Tests for MCP live basis tools (Phase F9).

Tests the same logic the MCP tools expose, using the underlying library
functions directly (MCP server has its own venv with fastmcp).
"""

import pytest
from dataclasses import asdict

from diamond_options.pricing.live_basis import (
    live_basis_from_kite,
    live_basis_scan,
    live_rollover_analysis,
)


# ── live_basis_check (MCP tool) ───────────────────────────────


class TestLiveBasisCheckTool:
    def test_basic_output(self):
        result = asdict(live_basis_from_kite("NIFTY", 22500, 22600, 20))
        assert result["symbol"] == "NIFTY"
        assert result["basis"] == 100
        assert result["contango"] is True
        assert result["signal"] in ("rich", "cheap", "fair")
        assert "annualized_basis" in result
        assert "fair_value" in result
        assert "mispricing" in result

    def test_backwardation_output(self):
        result = asdict(live_basis_from_kite("RELIANCE", 2800, 2790, 15))
        assert result["basis"] == -10
        assert result["contango"] is False

    def test_custom_params_output(self):
        result = asdict(live_basis_from_kite(
            "ITC", 450, 455, 30, risk_free_rate=0.07, dividend_yield=0.03,
        ))
        assert result["symbol"] == "ITC"
        assert result["days_to_expiry"] == 30


# ── live_basis_scan_tool (MCP tool) ───────────────────────────


class TestLiveBasisScanTool:
    def test_basic_output(self):
        quotes = [
            {"symbol": "NIFTY", "spot_price": 22500, "futures_price": 22700, "days_to_expiry": 10},
            {"symbol": "BANKNIFTY", "spot_price": 48000, "futures_price": 48050, "days_to_expiry": 30},
        ]
        results = live_basis_scan(quotes)
        output = {"count": len(results), "results": [asdict(r) for r in results]}
        assert output["count"] == 2
        assert len(output["results"]) == 2
        assert all("signal" in r for r in output["results"])

    def test_empty_output(self):
        results = live_basis_scan([])
        assert len(results) == 0

    def test_skips_invalid_output(self):
        quotes = [
            {"symbol": "GOOD", "spot_price": 100, "futures_price": 105, "days_to_expiry": 20},
            {"symbol": "BAD", "spot_price": 0, "futures_price": 105, "days_to_expiry": 20},
        ]
        results = live_basis_scan(quotes)
        assert len(results) == 1


# ── live_rollover_check (MCP tool) ────────────────────────────


class TestLiveRolloverCheckTool:
    def test_basic_output(self):
        result = asdict(live_rollover_analysis("NIFTY", 22600, 3, 22700, 33))
        assert result["symbol"] == "NIFTY"
        assert result["calendar_spread"] == 100
        assert result["recommendation"] in ("roll_now", "wait", "close")
        assert "rationale" in result

    def test_imminent_expiry_output(self):
        result = asdict(live_rollover_analysis("NIFTY", 22600, 1, 22700, 31))
        assert result["recommendation"] == "roll_now"

    def test_no_urgency_output(self):
        result = asdict(live_rollover_analysis("NIFTY", 22600, 15, 22700, 45))
        assert result["recommendation"] == "wait"

    def test_with_spot_output(self):
        result = asdict(live_rollover_analysis(
            "NIFTY", 22600, 5, 22700, 35, spot_price=22500,
        ))
        assert result["near_price"] == 22600
