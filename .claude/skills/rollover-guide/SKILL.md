---
description: Guides option position rollovers
auto_trigger: true
triggers:
  - user wants to roll a position
  - position is near expiry and profitable
  - user asks about rolling to next expiry
  - adjustment advisor suggests ROLL_OUT
---

Rollover guidance:

1. When to roll:
   - Position at 50%+ profit with > 14 DTE remaining in next expiry
   - Position challenged but thesis intact
   - Want to maintain exposure without gap risk over expiry

2. Roll types:
   - **Roll out:** Same strike, next expiry (extend time)
   - **Roll up:** Higher strike, same/next expiry (more bullish)
   - **Roll down:** Lower strike, same/next expiry (more bearish)
   - **Roll out and widen:** Next expiry + wider strikes (defensive)

3. Cost analysis:
   - Compare: close current + open new vs let expire + open new
   - Use `trade_cost_impact` for both scenarios
   - Roll credit: new premium > close cost (ideal)
   - Roll debit: paying to maintain position (less ideal)

4. Rules:
   - Don't roll a losing position just to avoid booking the loss
   - Each roll should stand on its own as a good trade
   - Maximum 2 rolls — if still losing, close and reassess
   - Roll 2-3 days before expiry for best liquidity
