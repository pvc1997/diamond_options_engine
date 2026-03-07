---
description: Analyzes volatility deeply when relevant
auto_trigger: true
triggers:
  - user asks about volatility for a stock
  - user asks if options are expensive
  - before trade recommendations involving premium selling
  - user mentions HV, IV, GARCH, or VRP
---

Volatility analysis workflow:

1. Historical volatility:
   - Use `all_hv_estimators` for 5-method comparison
   - Use `multi_window_volatility` for term structure
   - Yang-Zhang is most reliable overall
   - If short-term HV > long-term HV → vol is expanding

2. Forecasting:
   - `ewma_forecast` for next 5 days
   - `garch_forecast` for mean-reverting prediction
   - If GARCH persistence > 0.95, vol shocks last longer

3. IV vs RV:
   - `variance_risk_premium` for the edge
   - Positive VRP = structural edge for sellers
   - Historical average VRP in India: ~2-4%

4. Present as actionable insight:
   - "Vol is elevated and contracting → sell premium"
   - "Vol is low but expanding → buy options/protection"
   - "IV is fair relative to RV → no vol edge, use directional view"
