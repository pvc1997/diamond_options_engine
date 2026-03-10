"""Tests for futures chain data structures."""

from datetime import date

import pytest

from diamond_options.data.futures_chain import FuturesChain, FuturesQuote


@pytest.fixture
def nifty_near() -> FuturesQuote:
    """Near-month NIFTY futures quote."""
    return FuturesQuote(
        symbol="NIFTY",
        expiry=date(2026, 3, 31),
        last_price=22650.0,
        spot_price=22500.0,
        lot_size=65,
        open_interest=12000000,
        oi_change=500000,
        volume=800000,
        bid=22648.0,
        ask=22652.0,
        open=22600.0,
        high=22700.0,
        low=22550.0,
        prev_close=22580.0,
    )


@pytest.fixture
def nifty_next() -> FuturesQuote:
    """Next-month NIFTY futures quote."""
    return FuturesQuote(
        symbol="NIFTY",
        expiry=date(2026, 4, 28),
        last_price=22750.0,
        spot_price=22500.0,
        lot_size=65,
        open_interest=4000000,
        oi_change=200000,
        volume=200000,
        bid=22745.0,
        ask=22755.0,
    )


@pytest.fixture
def nifty_far() -> FuturesQuote:
    """Far-month NIFTY futures quote."""
    return FuturesQuote(
        symbol="NIFTY",
        expiry=date(2026, 5, 26),
        last_price=22850.0,
        spot_price=22500.0,
        lot_size=65,
        open_interest=500000,
        volume=20000,
    )


class TestFuturesQuote:
    def test_basis_positive_contango(self, nifty_near):
        assert nifty_near.basis == 150.0
        assert nifty_near.is_contango
        assert not nifty_near.is_backwardation

    def test_basis_negative_backwardation(self):
        q = FuturesQuote(
            symbol="RELIANCE",
            expiry=date(2026, 3, 31),
            last_price=2480.0,
            spot_price=2500.0,
            lot_size=250,
        )
        assert q.basis == -20.0
        assert q.is_backwardation
        assert not q.is_contango

    def test_basis_pct(self, nifty_near):
        expected = (150.0 / 22500.0) * 100
        assert abs(nifty_near.basis_pct - expected) < 0.001

    def test_basis_pct_zero_spot(self):
        q = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=100.0, spot_price=0.0,
        )
        assert q.basis_pct == 0.0

    def test_contract_value(self, nifty_near):
        assert nifty_near.contract_value == 22650.0 * 65

    def test_spread(self, nifty_near):
        assert nifty_near.spread == 4.0  # 22652 - 22648

    def test_spread_pct(self, nifty_near):
        mid = (22648.0 + 22652.0) / 2
        expected = (4.0 / mid) * 100
        assert abs(nifty_near.spread_pct - expected) < 0.001

    def test_spread_no_bid_ask(self):
        q = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=100.0, spot_price=100.0,
        )
        assert q.spread == 0.0
        assert q.spread_pct == 0.0

    def test_annualized_basis(self, nifty_near):
        # 150/22500 * 100 = 0.667% over ~20 days → annualized
        ann = nifty_near.annualized_basis(20)
        expected = (nifty_near.basis_pct / 20) * 365
        assert abs(ann - expected) < 0.01

    def test_annualized_basis_zero_days(self, nifty_near):
        assert nifty_near.annualized_basis(0) == 0.0

    def test_annualized_basis_zero_spot(self):
        q = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=100.0, spot_price=0.0,
        )
        assert q.annualized_basis(20) == 0.0

    def test_to_dict(self, nifty_near):
        d = nifty_near.to_dict()
        assert d["symbol"] == "NIFTY"
        assert d["expiry"] == "2026-03-31"
        assert d["basis"] == 150.0
        assert "contract_value" in d


class TestFuturesChain:
    def test_single_month_chain(self, nifty_near):
        chain = FuturesChain(symbol="NIFTY", spot=22500.0, near_month=nifty_near)
        assert chain.total_oi == 12000000
        assert chain.oi_concentration == "near"
        assert chain.calendar_spread is None
        assert chain.calendar_spread_pct is None
        assert chain.term_structure == "single_month"

    def test_two_month_chain(self, nifty_near, nifty_next):
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next,
        )
        assert chain.total_oi == 12000000 + 4000000
        assert chain.calendar_spread == 100.0  # 22750 - 22650
        assert chain.oi_concentration == "near"

    def test_three_month_chain(self, nifty_near, nifty_next, nifty_far):
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next, far_month=nifty_far,
        )
        assert chain.total_oi == 12000000 + 4000000 + 500000

    def test_calendar_spread_pct(self, nifty_near, nifty_next):
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next,
        )
        expected = (100.0 / 22650.0) * 100
        assert abs(chain.calendar_spread_pct - expected) < 0.001

    def test_rollover_pct(self, nifty_near, nifty_next):
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next,
        )
        total = 12000000 + 4000000
        expected = (4000000 / total) * 100
        assert abs(chain.rollover_pct - expected) < 0.01

    def test_rollover_pct_no_next(self, nifty_near):
        chain = FuturesChain(symbol="NIFTY", spot=22500.0, near_month=nifty_near)
        assert chain.rollover_pct == 0.0

    def test_rollover_pct_zero_oi(self):
        near = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=100.0, spot_price=100.0, open_interest=0,
        )
        next_m = FuturesQuote(
            symbol="TEST", expiry=date(2026, 4, 28),
            last_price=101.0, spot_price=100.0, open_interest=0,
        )
        chain = FuturesChain(symbol="TEST", spot=100.0, near_month=near, next_month=next_m)
        assert chain.rollover_pct == 0.0

    def test_term_structure_contango(self, nifty_near, nifty_next, nifty_far):
        # near(22650) < next(22750) < far(22850) → contango
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next, far_month=nifty_far,
        )
        assert chain.term_structure == "contango"

    def test_term_structure_backwardation(self):
        near = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=105.0, spot_price=100.0,
        )
        next_m = FuturesQuote(
            symbol="TEST", expiry=date(2026, 4, 28),
            last_price=103.0, spot_price=100.0,
        )
        far = FuturesQuote(
            symbol="TEST", expiry=date(2026, 5, 26),
            last_price=101.0, spot_price=100.0,
        )
        chain = FuturesChain(
            symbol="TEST", spot=100.0,
            near_month=near, next_month=next_m, far_month=far,
        )
        assert chain.term_structure == "backwardation"

    def test_term_structure_mixed(self):
        near = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=105.0, spot_price=100.0,
        )
        next_m = FuturesQuote(
            symbol="TEST", expiry=date(2026, 4, 28),
            last_price=103.0, spot_price=100.0,
        )
        far = FuturesQuote(
            symbol="TEST", expiry=date(2026, 5, 26),
            last_price=106.0, spot_price=100.0,
        )
        chain = FuturesChain(
            symbol="TEST", spot=100.0,
            near_month=near, next_month=next_m, far_month=far,
        )
        assert chain.term_structure == "mixed"

    def test_oi_concentration_next(self):
        near = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=100.0, spot_price=100.0, open_interest=1000,
        )
        next_m = FuturesQuote(
            symbol="TEST", expiry=date(2026, 4, 28),
            last_price=101.0, spot_price=100.0, open_interest=5000,
        )
        chain = FuturesChain(symbol="TEST", spot=100.0, near_month=near, next_month=next_m)
        assert chain.oi_concentration == "next"

    def test_oi_concentration_far(self):
        near = FuturesQuote(
            symbol="TEST", expiry=date(2026, 3, 31),
            last_price=100.0, spot_price=100.0, open_interest=100,
        )
        next_m = FuturesQuote(
            symbol="TEST", expiry=date(2026, 4, 28),
            last_price=101.0, spot_price=100.0, open_interest=200,
        )
        far = FuturesQuote(
            symbol="TEST", expiry=date(2026, 5, 26),
            last_price=102.0, spot_price=100.0, open_interest=5000,
        )
        chain = FuturesChain(
            symbol="TEST", spot=100.0,
            near_month=near, next_month=next_m, far_month=far,
        )
        assert chain.oi_concentration == "far"

    def test_summary(self, nifty_near, nifty_next):
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next,
        )
        s = chain.summary()
        assert s["symbol"] == "NIFTY"
        assert s["spot"] == 22500.0
        assert "near_month" in s
        assert "next_month" in s
        assert "calendar_spread" in s
        assert s["term_structure"] == "contango"

    def test_summary_single_month(self, nifty_near):
        chain = FuturesChain(symbol="NIFTY", spot=22500.0, near_month=nifty_near)
        s = chain.summary()
        assert "next_month" not in s
        assert "far_month" not in s

    def test_to_dict_roundtrip(self, nifty_near, nifty_next):
        chain = FuturesChain(
            symbol="NIFTY", spot=22500.0,
            near_month=nifty_near, next_month=nifty_next,
            timestamp="2026-03-09 14:00:00",
        )
        d = chain.to_dict()
        assert d["symbol"] == "NIFTY"
        assert d["near_month"]["symbol"] == "NIFTY"
        assert d["next_month"]["expiry"] == "2026-04-28"
