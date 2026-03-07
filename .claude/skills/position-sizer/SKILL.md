---
description: Ensures proper position sizing on every trade
auto_trigger: true
triggers:
  - user is about to place a trade
  - user asks how many lots to trade
  - trade recommendation is generated
  - user mentions capital or risk percentage
---

Before any trade execution:

1. Determine risk budget:
   - Default: 2% of capital per trade
   - Use `position_size` tool with VIX adjustment
   - In high VIX (>25), reduce to 1% or less
   - In crisis VIX (>35), reduce to 0.5%

2. Calculate position size:
   - For defined risk: lots = risk_budget / max_loss_per_lot
   - For undefined risk: use margin-based sizing
   - Apply VIX multiplier (0.25x in crisis, 1.0x in calm)
   - Cap at max_lots (never more than 30% of capital)

3. Safety checks:
   - Never risk > 5% of capital on single trade
   - Total portfolio risk should be < 20% of capital
   - Leave 30% capital as reserve for adjustments

4. Show the sizing calculation transparently.
