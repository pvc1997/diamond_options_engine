---
description: Builds option spreads with proper strike selection
auto_trigger: true
triggers:
  - user asks to build a specific spread
  - user mentions bull spread, bear spread, condor, butterfly
  - user wants to construct a multi-leg trade
---

Spread construction:

1. Determine strategy type from user's intent
2. Get spot price and lot size
3. Use `strategy_strikes` for optimal strikes
4. Use `price_spread` for BS theoretical prices
5. Use `analyze_payoff` for P&L profile

Strike selection guidelines:
- Credit spreads: sell closer to ATM, buy further OTM
- Iron condor wings: 1-2 strikes OTM (short), 2-3 strikes OTM (long)
- Butterflies: center at expected settlement
- Straddles: always ATM

Width conventions (NIFTY):
- Standard: 100-point wide spreads
- Aggressive: 50-point wide (more premium, more risk)
- Conservative: 200-point wide (less premium, safer)

Always show the complete setup with all legs before execution.
