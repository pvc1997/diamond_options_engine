---
description: Optimizes trade setup to minimize cost impact
auto_trigger: true
triggers:
  - trade costs are calculated
  - cost as % of max profit exceeds 15%
  - user asks about reducing costs
  - multi-leg strategy has high brokerage
---

Cost optimization strategies:

1. Brokerage awareness:
   - Each leg = ₹20 per order
   - 4-leg iron condor = 8 orders (open+close) = ₹160
   - 2-leg spread = 4 orders = ₹80
   - Consider: is the simpler strategy worth it for cost savings?

2. Cost thresholds:
   - < 5% of max profit: Excellent — proceed
   - 5-15%: Acceptable — note the drag
   - 15-30%: Marginal — consider wider spreads or fewer legs
   - > 30%: Not viable — costs eat too much profit

3. Optimization techniques:
   - Use wider spreads (more profit per leg)
   - Trade monthly instead of weekly (more premium per leg)
   - Use 2-leg spreads instead of 4-leg condors when possible
   - Avoid very OTM options (low premium, high cost ratio)

4. Always compare `trade_cost_impact` across alternatives.
