---
description: Interprets Greeks in plain language for the user
auto_trigger: true
triggers:
  - user asks what delta/gamma/theta/vega means for their position
  - Greeks are calculated and displayed
  - user asks "is my delta too high?"
  - user asks about position sensitivity
---

After calculating Greeks, interpret them:

**Delta:**
- |Delta| > 0.7 → Deep ITM, behaves like stock
- |Delta| 0.4-0.6 → ATM, high optionality
- |Delta| < 0.3 → OTM, leveraged bet
- Portfolio delta > 200 → very directional, consider hedging

**Gamma:**
- High gamma near ATM → position P&L accelerates on moves
- Short gamma near expiry → dangerous, small moves cause big P&L swings
- Weekly options have highest gamma — handle with care

**Theta:**
- Show as daily INR amount (theta × lot_size × lots)
- Positive theta = time working for you (short premium)
- Theta accelerates in last 7 days — avoid buying weeklies with < 3 DTE

**Vega:**
- Show as INR per 1% IV move
- Long vega = benefit from vol increase
- Short vega = benefit from IV crush (post-event)

Always relate to the user's specific position size and P&L impact.
