"""Shared test fixtures for Diamond Options Engine."""

from __future__ import annotations

import pytest
from datetime import date
from pathlib import Path
import tempfile

from diamond_options.data.options_chain import OptionQuote, OptionsChain


@pytest.fixture
def sample_chain() -> OptionsChain:
    """A realistic Nifty options chain for testing."""
    expiry = date(2026, 3, 17)  # A Tuesday
    spot = 22500.0
    strikes = [22200, 22300, 22400, 22500, 22600, 22700, 22800]

    calls = [
        OptionQuote(strike=22200, option_type="CE", expiry=expiry, ltp=350.0,
                    bid=348, ask=352, open_interest=50000, volume=5000, iv=0.15),
        OptionQuote(strike=22300, option_type="CE", expiry=expiry, ltp=270.0,
                    bid=268, ask=272, open_interest=80000, volume=8000, iv=0.14),
        OptionQuote(strike=22400, option_type="CE", expiry=expiry, ltp=195.0,
                    bid=193, ask=197, open_interest=120000, volume=15000, iv=0.13),
        OptionQuote(strike=22500, option_type="CE", expiry=expiry, ltp=130.0,
                    bid=128, ask=132, open_interest=200000, volume=25000, iv=0.12),
        OptionQuote(strike=22600, option_type="CE", expiry=expiry, ltp=80.0,
                    bid=78, ask=82, open_interest=180000, volume=20000, iv=0.13),
        OptionQuote(strike=22700, option_type="CE", expiry=expiry, ltp=45.0,
                    bid=43, ask=47, open_interest=150000, volume=12000, iv=0.14),
        OptionQuote(strike=22800, option_type="CE", expiry=expiry, ltp=22.0,
                    bid=20, ask=24, open_interest=100000, volume=8000, iv=0.15),
    ]

    puts = [
        OptionQuote(strike=22200, option_type="PE", expiry=expiry, ltp=18.0,
                    bid=16, ask=20, open_interest=90000, volume=7000, iv=0.16),
        OptionQuote(strike=22300, option_type="PE", expiry=expiry, ltp=35.0,
                    bid=33, ask=37, open_interest=110000, volume=10000, iv=0.15),
        OptionQuote(strike=22400, option_type="PE", expiry=expiry, ltp=60.0,
                    bid=58, ask=62, open_interest=140000, volume=14000, iv=0.14),
        OptionQuote(strike=22500, option_type="PE", expiry=expiry, ltp=100.0,
                    bid=98, ask=102, open_interest=190000, volume=22000, iv=0.13),
        OptionQuote(strike=22600, option_type="PE", expiry=expiry, ltp=150.0,
                    bid=148, ask=152, open_interest=160000, volume=16000, iv=0.14),
        OptionQuote(strike=22700, option_type="PE", expiry=expiry, ltp=215.0,
                    bid=213, ask=217, open_interest=130000, volume=11000, iv=0.15),
        OptionQuote(strike=22800, option_type="PE", expiry=expiry, ltp=290.0,
                    bid=288, ask=292, open_interest=95000, volume=6000, iv=0.16),
    ]

    return OptionsChain(
        symbol="NIFTY",
        expiry=expiry,
        spot_price=spot,
        timestamp="2026-03-07 14:00:00",
        calls=calls,
        puts=puts,
    )


@pytest.fixture
def tmp_db_path() -> Path:
    """Temporary database path for ledger tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_ledger.db"
