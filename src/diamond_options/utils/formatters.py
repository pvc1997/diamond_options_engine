"""Display formatting utilities for INR amounts, Greeks, and options data."""

from __future__ import annotations


def fmt_inr(amount: float, show_sign: bool = False) -> str:
    """Format amount in INR with Indian number system (lakhs/crores).

    Examples:
        fmt_inr(1234.56)    -> "Rs. 1,234.56"
        fmt_inr(150000)     -> "Rs. 1,50,000.00"
        fmt_inr(-5000, True) -> "-Rs. 5,000.00"
    """
    sign = ""
    if amount < 0:
        sign = "-"
        amount = abs(amount)
    elif show_sign and amount > 0:
        sign = "+"

    # Indian number system: last 3 digits, then groups of 2
    integer_part = int(amount)
    decimal_part = f"{amount - integer_part:.2f}"[1:]  # ".XX"

    s = str(integer_part)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        formatted = ",".join(groups) + "," + last3

    return f"{sign}Rs. {formatted}{decimal_part}"


def fmt_lakhs(amount: float) -> str:
    """Format large amounts in lakhs for readability."""
    lakhs = amount / 100000
    if lakhs >= 100:
        return f"Rs. {lakhs / 100:.2f} Cr"
    if lakhs >= 1:
        return f"Rs. {lakhs:.2f} L"
    return fmt_inr(amount)


def fmt_pct(value: float, decimals: int = 2) -> str:
    """Format a decimal as percentage. 0.15 -> '15.00%'"""
    return f"{value * 100:.{decimals}f}%"


def fmt_greek(name: str, value: float) -> str:
    """Format a Greek value with appropriate precision.

    Delta/Gamma: 4 decimals
    Theta: 2 decimals (INR per day)
    Vega: 2 decimals (INR per 1% vol)
    """
    if name.lower() in ("delta", "gamma", "rho"):
        return f"{value:.4f}"
    return f"{value:.2f}"


def fmt_strike(strike: float) -> str:
    """Format strike price — no decimals if round, else 2."""
    if strike == int(strike):
        return str(int(strike))
    return f"{strike:.2f}"


def fmt_iv(iv: float) -> str:
    """Format implied volatility as percentage."""
    return f"{iv * 100:.1f}%"


def fmt_oi(oi: int) -> str:
    """Format open interest with comma separators."""
    return f"{oi:,}"


def option_symbol(underlying: str, expiry_str: str, strike: float, opt_type: str) -> str:
    """Build a human-readable option symbol.

    Example: option_symbol("NIFTY", "27MAR", 22500, "CE") -> "NIFTY 27MAR 22500 CE"
    """
    return f"{underlying} {expiry_str} {fmt_strike(strike)} {opt_type}"
