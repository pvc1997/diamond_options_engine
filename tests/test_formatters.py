"""Tests for display formatting utilities."""

from diamond_options.utils.formatters import (
    fmt_inr,
    fmt_lakhs,
    fmt_pct,
    fmt_greek,
    fmt_strike,
    fmt_iv,
    fmt_oi,
    option_symbol,
)


def test_fmt_inr_basic():
    assert fmt_inr(1234.56) == "Rs. 1,234.56"


def test_fmt_inr_lakhs():
    assert fmt_inr(150000) == "Rs. 1,50,000.00"


def test_fmt_inr_crores():
    assert fmt_inr(15000000) == "Rs. 1,50,00,000.00"


def test_fmt_inr_small():
    assert fmt_inr(42) == "Rs. 42.00"


def test_fmt_inr_negative():
    result = fmt_inr(-5000)
    assert result.startswith("-")
    assert "5,000" in result


def test_fmt_inr_with_sign():
    assert fmt_inr(5000, show_sign=True).startswith("+")
    assert fmt_inr(-5000, show_sign=True).startswith("-")


def test_fmt_lakhs_large():
    assert "Cr" in fmt_lakhs(15000000)


def test_fmt_lakhs_medium():
    assert "L" in fmt_lakhs(500000)


def test_fmt_lakhs_small():
    assert "Rs." in fmt_lakhs(500)


def test_fmt_pct():
    assert fmt_pct(0.15) == "15.00%"
    assert fmt_pct(0.0065, 1) == "0.7%"


def test_fmt_greek_delta():
    assert fmt_greek("delta", 0.5123) == "0.5123"


def test_fmt_greek_theta():
    assert fmt_greek("theta", -45.67) == "-45.67"


def test_fmt_strike_round():
    assert fmt_strike(22500.0) == "22500"


def test_fmt_strike_decimal():
    assert fmt_strike(22500.50) == "22500.50"


def test_fmt_iv():
    assert fmt_iv(0.25) == "25.0%"


def test_fmt_oi():
    assert fmt_oi(150000) == "150,000"


def test_option_symbol():
    assert option_symbol("NIFTY", "27MAR", 22500, "CE") == "NIFTY 27MAR 22500 CE"
