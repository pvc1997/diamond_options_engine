---
description: Manages losing positions and stop-loss decisions
auto_trigger: true
triggers:
  - position has unrealized loss > 50% of max loss
  - user asks about a losing position
  - adjustment advisor returns "in_trouble" status
  - position breaches a short strike
---

Loss management protocol:

1. Stop-loss levels:
   - Defined risk: let max loss define your risk (it's why you chose defined risk)
   - Undefined risk: close at 2x premium received (e.g., sold for ₹40, close at ₹120)
   - Portfolio level: close all positions if portfolio drawdown > 10%

2. Decision tree for losses:
   - Loss < 25% of max → Monitor, no action
   - Loss 25-50% → Consider rolling (use `adjustment_advisor`)
   - Loss 50-75% → Roll or close (act within 24h)
   - Loss > 75% → Close immediately (damage is done)

3. Adjustment vs close:
   - Roll only if you still believe in the original thesis
   - Don't roll a bad trade into a worse one
   - Rolling costs money — factor in the new position's edge
   - Sometimes the best adjustment is closing

4. After closing a loser:
   - Log the trade and reason for loss
   - Don't immediately enter a "revenge trade"
   - Wait at least 1 day before next trade
