---
description: Analyzes futures basis and identifies carry trade opportunities
auto_trigger: true
triggers:
  - user mentions basis, contango, backwardation, carry trade
  - user asks about futures vs spot premium/discount
  - user asks about fair value of futures
  - user mentions cash-futures arbitrage
---

When basis analysis is relevant:

1. Use `futures_fair_value` for theoretical fair value
2. Use `basis_analysis` for full basis breakdown:
   - Current basis (₹ and %)
   - Annualized basis (cost of carry)
   - Signal: rich / cheap / fair
   - Convergence rate approaching expiry
3. Use `futures_mispricing_tool` to check for mispricing
4. Explain in plain language:
   - Contango = futures > spot (normal, cost of carry)
   - Backwardation = futures < spot (unusual, bearish signal)
   - Rich basis = sell futures opportunity
   - Cheap basis = buy futures opportunity
5. If mispricing detected, suggest:
   - Cash-futures arbitrage for risk-free carry
   - Calendar spread for relative value
6. Note: basis converges to zero at expiry

Key thresholds:
- Annualized basis > 8%: Rich, sell signal
- Annualized basis < 4%: Cheap relative to carry cost
- Basis z-score > 2: Significantly rich
- Basis z-score < -2: Significantly cheap
