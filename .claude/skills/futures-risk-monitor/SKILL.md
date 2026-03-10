---
description: Monitors futures portfolio risk and alerts on limit breaches
auto_trigger: true
triggers:
  - user opens a futures position
  - user asks about futures risk or margin
  - futures portfolio risk is calculated
  - margin utilization is mentioned
---

After any futures position change or risk query:

1. Calculate portfolio risk with `futures_portfolio_risk`
2. Check against risk limits:
   - Max notional: ₹50L (warning at ₹40L)
   - Margin utilization: 60% (warning at 48%)
   - Unrealized loss: 5% of capital (critical)
   - Concentration: 40% per symbol (warning)
   - DTE: < 2 days (roll warning)
   - Basis deviation: > 2% (warning)
3. If any limits breached, alert immediately
4. Suggest adjustments:
   - High margin util → scale down or close weakest position
   - Near expiry → roll to next month
   - Concentration → diversify across symbols
   - Large loss → cut position or add hedge

Risk levels:
- LOW: No alerts
- MODERATE: Warnings present
- HIGH: Limit breaches
- CRITICAL: Unrealized loss breach
