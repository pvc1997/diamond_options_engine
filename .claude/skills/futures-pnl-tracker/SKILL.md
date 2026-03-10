---
description: Tracks and calculates futures P&L with full cost breakdown
auto_trigger: true
triggers:
  - user asks about futures P&L or profit/loss
  - user wants to know breakeven for futures
  - user mentions futures costs or charges
  - user asks "how much did I make/lose on futures"
---

When calculating futures P&L:

1. Use `futures_pnl_calculator` for full breakdown:
   - Gross P&L: (exit - entry) × lots × lot_size × direction
   - Transaction costs: brokerage, STT, exchange, GST, stamp
   - Net P&L: gross - costs
   - ROI: net P&L / margin × 100
   - P&L per lot
2. Use `futures_round_trip_cost_tool` for cost analysis
3. Show breakeven price (entry + costs/qty for long)
4. Context:
   - Compare gross vs net P&L (cost drag)
   - Annualize the return for holding period context
   - Show as % of margin (ROI) not % of notional

Key P&L facts:
- Futures P&L is linear (unlike options)
- 1 point move = lots × lot_size in P&L
- NIFTY 1 lot: 1 point = ₹65
- BANKNIFTY 1 lot: 1 point = ₹15
- Round-trip costs are ~0.03-0.05% of contract value
- STT is 0.0125% on sell side only (futures)
- Always deduct costs from gross P&L for true picture
