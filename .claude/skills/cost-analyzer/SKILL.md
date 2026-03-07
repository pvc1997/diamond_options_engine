---
description: Automatically calculates and shows trading costs
auto_trigger: true
triggers:
  - user asks about costs, charges, or fees
  - before confirming any trade execution
  - user compares strategies and needs cost impact
---

When showing trading costs:

1. Use `options_costs` for single-leg trades
2. Use `spread_costs` for multi-leg strategies
3. Always show:
   - Per-leg cost breakdown
   - Total round-trip cost (open + close)
   - Cost as % of max profit
   - STT note: "Remember, options STT is only on sell side"
4. For strategies, calculate break-even including costs
5. Compare with equity delivery costs if relevant

Key Indian F&O cost facts:
- STT on options: 0.0625% sell only (buy is free)
- Flat Rs. 20 brokerage per order
- Each spread leg = 1 order = Rs. 20
- 4-leg iron condor = 8 orders total (open + close) = Rs. 160 brokerage alone
