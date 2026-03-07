---
description: Helps maintain a trade journal for learning
auto_trigger: true
triggers:
  - user closes a trade
  - user asks to log or journal a trade
  - user asks "what did I learn?"
---

Trade journal template:

After each closed trade, log:

1. **Trade details:**
   - Strategy, symbol, strikes, premiums
   - Entry date, exit date, DTE at entry
   - Lots, capital risked

2. **Results:**
   - Gross P&L, net P&L (after costs)
   - P&L as % of max profit
   - Win/loss

3. **Market context at entry:**
   - VIX regime, IV rank
   - Trend direction
   - Why this strategy was chosen

4. **What happened:**
   - Did spot move as expected?
   - Did IV behave as expected?
   - Any adjustments made?

5. **Lessons:**
   - What would you do differently?
   - Was the sizing right?
   - Was the timing right?

Use `trade_history` to pull recent trade data automatically.
