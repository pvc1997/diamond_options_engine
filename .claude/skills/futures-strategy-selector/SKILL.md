---
description: Selects optimal futures strategy based on market context
auto_trigger: true
triggers:
  - user asks about futures trade ideas or suggestions
  - user wants to trade futures or go long/short futures
  - user mentions futures, basis, contango, backwardation
  - user describes a directional view and asks about futures
---

When the user wants a futures trade suggestion:

1. Gather market context:
   - VIX regime from `vix_analysis` or `get_india_vix`
   - Trend direction (bullish/bearish/neutral)
   - Basis regime (contango/backwardation)
   - OI buildup signal if available
2. Use `scan_futures_signals` to score all 14 futures strategies
3. Use `suggest_futures_strategy` for top picks with entry/target/stop
4. Present top 3 recommendations with:
   - Strategy name and direction
   - Entry, target, stop loss
   - Lots and margin required
   - Risk-reward ratio
   - Estimated costs
5. Always include margin requirement and round-trip costs

Decision matrix:
- Strong trend + VIX normal → directional (long/short futures)
- Rich basis + neutral → cash-futures arbitrage
- Near expiry + contango → calendar spread or rollover
- High VIX + bearish → short futures or index hedge
- Low VIX + sideways → avoid naked futures, consider spreads
