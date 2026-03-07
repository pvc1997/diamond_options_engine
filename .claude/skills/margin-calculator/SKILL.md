---
description: Estimates margin requirements for options strategies
auto_trigger: true
triggers:
  - user asks about margin for a strategy
  - trade setup involves selling options
  - user asks "how much capital do I need?"
---

Margin estimation for Indian F&O:

1. Long options: No margin, full premium upfront
   - Cost = premium × lot_size × lots

2. Spreads (defined risk): Margin = spread width × lot_size
   - Bull put spread 22300/22200: margin = 100 × 25 = ₹2,500/lot
   - Iron condor: margin = wider spread width × lot_size

3. Naked shorts (undefined risk): SPAN + exposure margin
   - Approx: 12-15% of notional value
   - NIFTY short straddle: ~₹1.5-2L per lot
   - Increases with VIX

4. Index vs stock margin:
   - Index options: lower margin (less volatile)
   - Stock options: higher margin (more volatile)

5. Rules of thumb:
   - Always keep 30% extra margin for MTM swings
   - Margin increases during high volatility
   - Peak margin reporting (Dec 2020 onwards): need margin at time of order

Show estimated margin alongside every trade recommendation.
