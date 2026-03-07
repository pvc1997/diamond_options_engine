Get trade suggestions for $ARGUMENTS.

Parse the user's input to extract: symbol (or assume NIFTY), market view (bullish/bearish/neutral).

1. Use `get_spot_price` to get the current price (or use synthetic ~22500 for NIFTY)
2. Use `get_india_vix` for VIX regime
3. Use `suggest_strategy` with the parsed inputs
4. Show top 3 recommendations with:
   - Strategy name and legs
   - Max profit / max loss / breakevens
   - Probability of profit
   - Position sizing recommendation
   - Rationale

Keep it actionable. Bold the top pick.
