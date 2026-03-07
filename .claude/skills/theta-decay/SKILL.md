---
description: Explains theta decay and optimal timing
auto_trigger: true
triggers:
  - user asks about time decay
  - user asks when to enter/exit a trade
  - user holds short-dated options
  - theta value is particularly high or low
---

Theta decay guidance:

1. Theta acceleration curve:
   - 30+ DTE: Slow, steady decay (~0.3% per day)
   - 14-30 DTE: Moderate decay (~0.7% per day)
   - 7-14 DTE: Fast decay (~1.5% per day)
   - < 7 DTE: Exponential decay (~3%+ per day)

2. Entry timing:
   - Premium sellers: Enter 30-45 DTE for steady theta
   - Premium buyers: Enter 14-21 DTE for best gamma/theta ratio
   - Weekly plays: Only for defined-risk, entry on Monday/Tuesday

3. Exit timing:
   - Premium sellers: Close at 50% profit or 21 DTE remaining
   - Premium buyers: Close before last 7 days (theta acceleration)
   - Never hold undefined-risk into last 3 days

4. Use `what_if_time_decay` to show exact P&L erosion.
