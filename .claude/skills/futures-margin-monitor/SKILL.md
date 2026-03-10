---
description: Monitors margin requirements and utilization for futures positions
auto_trigger: true
triggers:
  - user asks about futures margin
  - user wants to know how many lots they can trade
  - user mentions margin call or margin requirement
  - new futures position is being sized
---

When margin monitoring is relevant:

1. Use `futures_margin_estimate` for margin per lot
2. Calculate total margin across positions
3. Show margin utilization:
   - Total margin used / available capital
   - Per-position margin breakdown
   - Available margin for new positions
4. Warn on thresholds:
   - > 40%: Moderate — room for 1-2 more positions
   - > 60%: High — no new positions recommended
   - > 80%: Critical — consider reducing exposure
5. Calculate max affordable lots:
   - max_lots = (capital × max_util%) / margin_per_lot
6. For stock futures, warn about delivery margin:
   - Near expiry, stock futures need 40-50% delivery margin
   - This is much higher than normal SPAN margin

Key margin facts (Indian F&O):
- Index futures: ~10-12% SPAN margin
- Large-cap stocks: ~15-20%
- Mid-cap stocks: ~25-35%
- Volatile stocks: ~35-40%
- Delivery margin (stock futures at expiry): ~40-50%
- ELM (Extreme Loss Margin) adds 2-5% on top of SPAN
