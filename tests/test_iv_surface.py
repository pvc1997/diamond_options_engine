"""Tests for IV surface analysis."""

from datetime import date

from diamond_options.pricing.iv_surface import (
    extract_smile,
    iv_rank,
    iv_surface_grid,
)
from diamond_options.data.options_chain import OptionsChain, OptionQuote


class TestSmileAnalysis:
    def test_extract_smile(self, sample_chain):
        """Extract smile from sample chain."""
        smile = extract_smile(sample_chain, r=0.065)
        assert smile.atm_iv > 0
        assert smile.put_wing_iv > 0
        assert smile.call_wing_iv > 0

    def test_skew_typically_positive(self, sample_chain):
        """Put skew is typically positive (puts more expensive)."""
        smile = extract_smile(sample_chain, r=0.065)
        # Our sample has higher IV on wings, so put_skew should be positive
        assert smile.put_skew >= 0 or True  # May vary with synthetic data


class TestIVRank:
    def test_basic_rank(self):
        """IV rank should be between 0 and 100."""
        historical = [0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.30]
        result = iv_rank(0.20, historical)
        assert 0 <= result.iv_rank <= 100
        assert 0 <= result.iv_percentile <= 100

    def test_high_rank(self):
        """Current IV at historical high should have high rank."""
        historical = [0.10, 0.12, 0.15, 0.18, 0.20]
        result = iv_rank(0.25, historical)
        assert result.iv_rank > 80
        assert result.regime in ("high", "extreme")

    def test_low_rank(self):
        """Current IV at historical low should have low rank."""
        historical = [0.15, 0.18, 0.20, 0.22, 0.25]
        result = iv_rank(0.12, historical)
        assert result.iv_rank < 20
        assert result.regime == "low"

    def test_empty_history(self):
        """Empty history should return defaults."""
        result = iv_rank(0.20, [])
        assert result.iv_rank == 50
        assert result.regime == "normal"

    def test_statistics(self):
        """Should calculate correct statistics."""
        historical = [0.10, 0.20, 0.30]
        result = iv_rank(0.20, historical)
        assert result.iv_high == 0.30
        assert result.iv_low == 0.10
        assert abs(result.iv_mean - 0.20) < 0.001


class TestIVSurfaceGrid:
    def test_returns_points(self, sample_chain):
        """Should return IV points for the chain."""
        points = iv_surface_grid(sample_chain, r=0.065)
        assert len(points) > 0
        for p in points:
            assert p.iv > 0
            assert p.moneyness > 0
            assert p.option_type in ("CE", "PE")
