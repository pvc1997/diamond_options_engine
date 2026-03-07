---
description: Identifies IV regime and adjusts recommendations accordingly
auto_trigger: true
triggers:
  - IV rank or percentile is mentioned
  - user asks if options are expensive or cheap
  - before any trade recommendation
  - user asks about premium levels
---

IV regime assessment:

1. Check IV rank (0-100):
   - > 80: Very high — strong sell premium signal
   - 50-80: High — lean toward credit strategies
   - 20-50: Normal — no strong edge either way
   - < 20: Very low — consider buying options/protection

2. Check VRP (variance risk premium):
   - IV > RV by 3%+ → options are expensive → sell
   - IV ≈ RV → fairly priced → no edge
   - IV < RV → options are cheap → buy protection

3. Adjust strategy recommendations:
   - High IV: Iron condors, short strangles, credit spreads
   - Low IV: Long straddles, debit spreads, calendars
   - Normal IV: Follow directional view

Always mention the IV regime when recommending trades.
