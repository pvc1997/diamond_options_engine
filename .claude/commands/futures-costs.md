Calculate futures trading costs for $ARGUMENTS.

Parse: price, lots, lot_size, direction (buy/sell). Default to NIFTY 1 lot if not specified.

1. Use `futures_round_trip_cost_tool` for total round-trip costs
2. Use `futures_pnl_calculator` to show P&L at various exit prices
3. Use `futures_margin_estimate` for margin requirement
4. Show:
   - Entry cost breakdown (brokerage, STT, exchange fees, GST, stamp duty)
   - Exit cost breakdown
   - Total round-trip cost (₹ and as % of contract value)
   - Breakeven price for long and short
   - Margin required
   - Minimum move needed to cover costs

Compare with options costs if the user is deciding between futures and options.
