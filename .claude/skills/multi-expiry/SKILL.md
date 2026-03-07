---
description: Guides multi-expiry and calendar spread decisions
auto_trigger: true
triggers:
  - user asks about calendar spreads
  - user wants to trade across expiries
  - user asks "weekly or monthly?"
---

Multi-expiry guidance:

1. Weekly vs Monthly:
   - Weekly: Higher gamma, faster theta, more trades, more costs
   - Monthly: Lower gamma, steadier theta, fewer adjustments
   - Beginners: Start with monthly, move to weekly after experience

2. Calendar spreads:
   - Sell near expiry + buy far expiry (same strike)
   - Profits from time decay differential
   - Best in low IV (cheap far month, fast near decay)
   - Risk: large move makes both legs worthless

3. DTE selection rules:
   - Premium sellers: 30-45 DTE entry (optimal theta curve)
   - Premium buyers: 14-21 DTE (best gamma/theta)
   - Weekly income: Enter Wednesday, close Tuesday (defined risk only)
   - Monthly income: Enter at 30 DTE, close at 50% profit or 14 DTE

4. Use `simulate_multi_expiry` to see P&L evolution over time.
