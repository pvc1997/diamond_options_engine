---
description: Suggests when to take profits on winning trades
auto_trigger: true
triggers:
  - position has unrealized profit > 50% of max profit
  - user checks P&L and position is profitable
  - user asks when to exit a winning trade
---

Profit-taking guidelines:

1. Credit strategies (short premium):
   - Close at 50% of max profit (standard)
   - Close at 75% if < 14 DTE (theta slows, gamma risk rises)
   - Always close at 90%+ (last 10% not worth the risk)

2. Debit strategies (long options):
   - Take profits at 100% return (doubled your money)
   - Use trailing stop: close if gives back 50% of peak profit
   - Never hold hoping for "more" past 200% return

3. Time-based rules:
   - Close at 21 DTE regardless if > 50% profit
   - Never hold short premium into last 5 days for extra 10% profit
   - The first 50% of premium decays in 2/3 of the time

4. Use `adjustment_advisor` to check if "CLOSE" is recommended.
5. Show the math: profit taken vs risk of continuing.
