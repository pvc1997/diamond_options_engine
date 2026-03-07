---
description: Validates trades before execution
auto_trigger: true
triggers:
  - user confirms a trade
  - user says "execute", "place order", "let's do it"
  - trade recommendation is accepted
---

Before executing any trade:

1. Pre-trade checklist:
   - [ ] Position sizing within risk limits?
   - [ ] Portfolio Greeks after trade within limits?
   - [ ] Not doubling down on existing exposure?
   - [ ] Sufficient capital/margin available?
   - [ ] Not opening new weekly positions on Tuesday?
   - [ ] Cost impact < 20% of max profit?

2. Show final trade summary:
   - All legs with exact strikes and premiums
   - Total cost (premium + transaction costs)
   - Max profit / max loss
   - Breakevens
   - Position size (lots)
   - Required margin

3. Confirm with user before proceeding.
4. If any check fails, explain why and suggest alternatives.
