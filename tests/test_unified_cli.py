"""Tests for unified portfolio CLI command (Phase U1)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner
from diamond_options.cli import app

runner = CliRunner()


class TestPortfolioCommand:
    def test_runs_without_error(self):
        result = runner.invoke(app, ["portfolio"])
        assert result.exit_code == 0

    def test_shows_unified_header(self):
        result = runner.invoke(app, ["portfolio"])
        assert "UNIFIED PORTFOLIO" in result.output

    def test_shows_nav(self):
        result = runner.invoke(app, ["portfolio"])
        assert "NAV" in result.output

    def test_shows_margin(self):
        result = runner.invoke(app, ["portfolio"])
        assert "Margin" in result.output

    def test_shows_risk_level(self):
        result = runner.invoke(app, ["portfolio"])
        assert "Risk Level" in result.output

    def test_shows_hedge_ratio(self):
        result = runner.invoke(app, ["portfolio"])
        assert "Hedge Ratio" in result.output

    def test_shows_product_breakdown(self):
        result = runner.invoke(app, ["portfolio"])
        assert "Equity:" in result.output
        assert "Options:" in result.output
        assert "Futures:" in result.output

    def test_custom_capital(self):
        result = runner.invoke(app, ["portfolio", "--capital", "1000000"])
        assert result.exit_code == 0
        assert "10,00,000" in result.output or "1000000" in result.output or "Capital" in result.output

    def test_help(self):
        result = runner.invoke(app, ["portfolio", "--help"])
        assert result.exit_code == 0
        assert "capital" in result.output.lower()
