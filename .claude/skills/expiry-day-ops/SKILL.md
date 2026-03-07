---
description: Manages all expiry day operations
auto_trigger: true
triggers:
  - today is Tuesday (weekly expiry)
  - user has positions expiring today
  - user asks about expiry day procedures
  - it's within 2 hours of 3:00 PM on expiry day
---

Expiry day protocol:

1. Morning (before 10 AM):
   - List all expiring positions with `portfolio_status`
   - Run `expiry_checklist` for each position
   - Flag ITM short options (STT risk: 0.125% on notional!)
   - Flag ATM options (pin risk)

2. Decision framework:
   - Short ITM options: Close before 3:00 PM to avoid exercise STT
   - Long ITM options: Exercise is fine (cash-settled for indices)
   - OTM options: Let expire worthless, no action needed
   - ATM (within 0.5%): Close to avoid pin risk uncertainty

3. Rollover decision:
   - If want to maintain position: roll to next week
   - Compare roll cost with `trade_cost_impact`
   - Roll 1-2 days before expiry for better liquidity

4. STT warning (critical):
   - Options STT on exercise: 0.125% on notional value
   - NIFTY at 24000, lot 65 = ₹24000 × 65 × 0.00125 = ₹1950 per lot
   - Much higher than normal trading STT — always close ITM shorts!

5. Deadline: 3:00 PM IST — no more closing after this.
