Get futures adjustment advice for $ARGUMENTS.

Parse: symbol, direction (long/short), entry price, current price.

1. Use `get_spot_price` for current spot (or use user-provided price)
2. Estimate basis and DTE from context
3. Use `futures_adjustment_advisor` with the position details
4. Show:
   - Position status (healthy / challenged / at_risk / in_trouble)
   - What triggered the analysis
   - Ranked adjustments with:
     - Type (roll, scale down, hedge, close, convert to spread)
     - Urgency (immediate / soon / optional)
     - Step-by-step actions
     - Estimated cost
     - Risk reduction vs trade-off
   - Risk of doing nothing

If near expiry, also run `futures_expiry_checklist_tool`.
Bold any "immediate" urgency adjustments.
