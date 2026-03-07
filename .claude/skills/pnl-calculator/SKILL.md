---
description: Calculates P&L for positions with proper cost inclusion
auto_trigger: true
triggers:
  - user asks about P&L for a trade
  - user asks "how much did I make/lose?"
  - user wants to calculate profit on a closed trade
---

P&L calculation:

1. Gross P&L:
   - Long options: (exit_price - entry_price) × lot_size × lots
   - Short options: (entry_price - exit_price) × lot_size × lots
   - Spread: sum of all legs

2. Net P&L (after costs):
   - Subtract entry costs (brokerage, STT, exchange, etc.)
   - Subtract exit costs
   - Use `options_costs` for exact breakdown
   - Use `spread_costs` for multi-leg

3. Important:
   - STT only on sell side (0.0625%)
   - If option expires worthless, no exit STT (good for sellers!)
   - If exercised, exercise STT is 0.125% on notional (very expensive!)

4. Display:
   - Entry cost, exit cost, gross P&L, net P&L
   - P&L as % of capital risked
   - P&L as % of max profit (how close to optimal?)
