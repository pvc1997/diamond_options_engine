---
description: Selects optimal strategy based on market context
auto_trigger: true
triggers:
  - user asks "what should I trade?"
  - user asks for trade ideas or suggestions
  - user mentions wanting to sell premium or buy options
  - user describes a market view (bullish, bearish, sideways)
---

When the user wants a trade suggestion:

1. Gather market context:
   - VIX regime from `vix_analysis` or `get_india_vix`
   - IV rank if available
   - User's directional view
   - Days to expiry preference
2. Use `scan_market_signals` to score all strategies
3. Use `suggest_strategy` for top picks with specific legs
4. Present top 3 recommendations with:
   - Clear leg details (strikes, premiums)
   - Max profit/loss and breakevens
   - Probability of profit
   - Position sizing
5. Always include cost impact

Decision matrix:
- High IV + neutral view → sell premium (iron condor, short strangle)
- High IV + directional → credit spreads
- Low IV + directional → debit spreads, long options
- Low IV + neutral → avoid or calendar spreads
- Crisis VIX → protective puts, collars only
