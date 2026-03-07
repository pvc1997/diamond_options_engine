---
description: Suggests portfolio-level hedges
auto_trigger: true
triggers:
  - portfolio delta is high (> 300)
  - user asks about hedging
  - VIX spikes above 25
  - user asks "how do I protect my portfolio?"
---

Portfolio hedging:

1. Assess current exposure:
   - Use `portfolio_greeks_analysis` for net Greeks
   - High positive delta → long market risk
   - High negative delta → short market risk
   - High vega → volatility exposure

2. Hedge instruments:
   - **Protective put:** Buy OTM put (5% below spot). Cost: ~1-2% of notional
   - **Collar:** Sell OTM call + buy OTM put. Net cost: near zero
   - **Delta hedge:** Buy/sell offsetting spread to flatten delta
   - **Vega hedge:** Opposite vega position (short if long vega, vice versa)

3. Sizing the hedge:
   - Target: reduce delta by 50-70% (don't over-hedge)
   - Use `position_size` for hedge lot calculation
   - Cost of hedge should be < 2% of portfolio value per month

4. When to hedge:
   - Portfolio delta > 300 (directionally exposed)
   - VIX > 25 (rising fear)
   - Major event upcoming
   - Portfolio P&L at +20% (protect gains)
