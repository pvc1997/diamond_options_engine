---
description: Guides weekly portfolio review process
auto_trigger: true
triggers:
  - user asks for weekly review
  - it's Friday afternoon
  - user says "review my week"
---

Weekly review checklist:

1. Performance:
   - Use `portfolio_status` for current positions and P&L
   - Use `trade_history` for this week's trades
   - Calculate: wins, losses, net P&L, fees paid

2. Risk check:
   - Use `portfolio_greeks_analysis` for current exposure
   - Are positions sized appropriately?
   - Any concentration risk (too much in one underlying)?

3. Upcoming week:
   - Any positions expiring next Tuesday?
   - Need to roll anything?
   - VIX regime — has it changed?
   - Any major events next week?

4. Lessons:
   - What worked this week?
   - What didn't?
   - Any pattern in winning vs losing trades?

5. Planning:
   - Capital available for next week
   - Strategy ideas based on current conditions
   - Target number of trades (don't over-trade)
