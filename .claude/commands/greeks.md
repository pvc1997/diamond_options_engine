Calculate Greeks for $ARGUMENTS.

Parse: symbol, strike, option type (CE/PE), expiry.

1. Resolve the symbol using ticker-resolver skill
2. Use `calculate_greeks` MCP tool
3. Display in a clean table:
   - Delta, Gamma, Theta (per day), Vega (per 1% vol)
   - Per-share AND per-lot values
   - Probability ITM
4. Add interpretation:
   - Delta > 0.7 = deep ITM, < 0.3 = OTM
   - High gamma near ATM = position sensitive to moves
   - Negative theta = time working against you

If no strike given, show Greeks for ATM, 1 OTM, 2 OTM.
