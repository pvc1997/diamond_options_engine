"""Indian market options transaction cost model.

Pure functions — no side effects. All costs in INR.

Key difference from equity delivery costs:
- STT on options: 0.0625% on SELL side only (buy side: 0 STT)
- STT on futures: 0.0125% on SELL side only
- Brokerage: Rs. 20 per order (flat, for discount brokers)
- Exchange fees differ for options vs futures
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionsCostBreakdown:
    brokerage: float         # Flat 20 per order for discount brokers
    gst: float               # 18% on (brokerage + exchange fees + SEBI)
    stt: float               # Securities Transaction Tax
    exchange_fees: float     # NSE transaction charges
    sebi_charges: float      # SEBI regulatory fees
    stamp_duty: float        # State stamp duty
    slippage: float          # Estimated bid-ask crossing cost
    total: float

    def __repr__(self) -> str:
        return f"OptionsCostBreakdown(total={self.total:.2f})"


def calculate_options_costs(
    action: str,
    premium_amount: float,
    is_index: bool = False,
) -> OptionsCostBreakdown:
    """Calculate options transaction costs for Indian markets.

    Args:
        action: 'BUY' or 'SELL'
        premium_amount: Total premium value (premium * lot_size * lots)
        is_index: Whether this is an index option (slightly different charges)

    Returns:
        OptionsCostBreakdown with itemized costs.

    Cost structure (as of 2025-26):
        - Brokerage: Rs. 20 flat per order (discount brokers)
        - GST: 18% on (brokerage + exchange fees + SEBI charges)
        - STT: 0.0625% on sell side only (options)
        - Exchange fees: 0.0495% (NSE options)
        - SEBI charges: 0.001%
        - Stamp duty: 0.003% on buy side only
        - Slippage: 0.05% estimated (wider for illiquid strikes)
    """
    if premium_amount <= 0:
        return OptionsCostBreakdown(0, 0, 0, 0, 0, 0, 0, 0)

    # Brokerage: flat Rs. 20 per order
    brokerage = 20.0

    # STT: 0.0625% on sell side only for options
    if action == "SELL":
        stt = premium_amount * 0.000625
    else:
        stt = 0.0

    # Exchange transaction charges: 0.0495% for options
    exchange_rate = 0.000495 if not is_index else 0.000495
    exchange_fees = premium_amount * exchange_rate

    # SEBI charges: 0.001%
    sebi_charges = premium_amount * 0.00001

    # GST: 18% on (brokerage + exchange fees + SEBI charges)
    gst = (brokerage + exchange_fees + sebi_charges) * 0.18

    # Stamp duty: 0.003% on buy side only
    if action == "BUY":
        stamp_duty = premium_amount * 0.00003
    else:
        stamp_duty = 0.0

    # Estimated slippage
    slippage = premium_amount * 0.0005

    total = brokerage + gst + stt + exchange_fees + sebi_charges + stamp_duty + slippage

    return OptionsCostBreakdown(
        brokerage=round(brokerage, 2),
        gst=round(gst, 2),
        stt=round(stt, 2),
        exchange_fees=round(exchange_fees, 2),
        sebi_charges=round(sebi_charges, 2),
        stamp_duty=round(stamp_duty, 2),
        slippage=round(slippage, 2),
        total=round(total, 2),
    )


def calculate_futures_costs(
    action: str,
    turnover: float,
) -> OptionsCostBreakdown:
    """Calculate futures transaction costs.

    Args:
        action: 'BUY' or 'SELL'
        turnover: Total trade value (price * lot_size * lots)

    Returns:
        OptionsCostBreakdown with itemized costs.

    Key differences from options:
        - STT: 0.0125% on sell side only
        - Exchange fees: 0.002%
    """
    if turnover <= 0:
        return OptionsCostBreakdown(0, 0, 0, 0, 0, 0, 0, 0)

    brokerage = 20.0

    if action == "SELL":
        stt = turnover * 0.000125
    else:
        stt = 0.0

    exchange_fees = turnover * 0.00002
    sebi_charges = turnover * 0.00001
    gst = (brokerage + exchange_fees + sebi_charges) * 0.18

    if action == "BUY":
        stamp_duty = turnover * 0.00002
    else:
        stamp_duty = 0.0

    slippage = turnover * 0.0002

    total = brokerage + gst + stt + exchange_fees + sebi_charges + stamp_duty + slippage

    return OptionsCostBreakdown(
        brokerage=round(brokerage, 2),
        gst=round(gst, 2),
        stt=round(stt, 2),
        exchange_fees=round(exchange_fees, 2),
        sebi_charges=round(sebi_charges, 2),
        stamp_duty=round(stamp_duty, 2),
        slippage=round(slippage, 2),
        total=round(total, 2),
    )


def spread_round_trip_cost(
    legs: list[dict],
) -> float:
    """Calculate total cost for a multi-leg spread.

    Args:
        legs: List of dicts with keys: action, premium_amount, is_index

    Returns:
        Total cost for opening + closing all legs.
    """
    total = 0.0
    for leg in legs:
        # Opening cost
        open_cost = calculate_options_costs(
            leg["action"], leg["premium_amount"], leg.get("is_index", False)
        )
        # Closing cost (opposite action)
        close_action = "SELL" if leg["action"] == "BUY" else "BUY"
        close_cost = calculate_options_costs(
            close_action, leg["premium_amount"], leg.get("is_index", False)
        )
        total += open_cost.total + close_cost.total
    return round(total, 2)
