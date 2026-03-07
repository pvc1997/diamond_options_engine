---
description: Monitors and alerts on portfolio risk levels
auto_trigger: true
triggers:
  - user opens a new position
  - user asks about portfolio risk
  - portfolio Greeks are calculated
  - risk limits are mentioned
---

After any position change or risk query:

1. Calculate portfolio Greeks with `portfolio_greeks_analysis`
2. Check against risk limits:
   - Max delta: ±500 (warning at ±400)
   - Max gamma: ±100 (warning at ±80)
   - Max vega: ±₹5000 (warning at ±₹4000)
   - Max daily theta: -₹10000 (warning at -₹8000)
   - Per-position delta: ±200
3. If any limits breached, alert immediately
4. Suggest adjustments to reduce risk:
   - High delta → add opposite-direction spread or hedge
   - High gamma → close short near-expiry positions
   - High vega → reduce undefined-risk positions
   - Excessive theta → you're selling too much premium

Risk levels:
- GREEN: All within 50% of limits
- YELLOW: Any metric at 50-80% of limit
- RED: Any metric at 80%+ of limit
- CRITICAL: Any metric breached
