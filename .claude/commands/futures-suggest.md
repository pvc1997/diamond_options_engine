Get futures trade suggestions for $ARGUMENTS.

Parse the user's input to extract: symbol (or assume NIFTY), market view (bullish/bearish/neutral).

1. Use `get_spot_price` to get the current price (or use synthetic ~22500 for NIFTY)
2. Use `get_india_vix` for VIX regime
3. Estimate near-month futures price (spot + ~0.3% basis for 20 DTE)
4. Use `suggest_futures_strategy` with the parsed inputs
5. Show top 3 recommendations with:
   - Strategy name and direction
   - Entry price, target, stop loss
   - Number of lots and margin required
   - Risk-reward ratio
   - Estimated costs (round-trip)
   - Rationale

Keep it actionable. Bold the top pick. Always mention margin requirement.
