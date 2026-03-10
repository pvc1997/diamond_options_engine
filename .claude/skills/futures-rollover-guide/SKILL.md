---
description: Guides futures position rollovers near expiry
auto_trigger: true
triggers:
  - user mentions rolling futures or rollover
  - futures position is near expiry (< 3 DTE)
  - user asks about next month futures
  - monthly expiry is approaching
---

When a futures rollover is relevant:

1. Check current position's DTE
2. Use `futures_expiry_checklist_tool` for expiry actions
3. Analyze roll cost:
   - Use `basis_analysis` with next_futures for roll yield
   - Calendar spread = next_month - near_month
   - Annualized roll cost = spread / near × 365 / days
4. Guide the rollover:
   - STEP 1: Check if calendar spread is reasonable (< 1% for indices)
   - STEP 2: Close near-month position at market
   - STEP 3: Open same direction in next month
   - STEP 4: Account for roll cost in P&L tracking
5. Show total costs: roll spread + 2x transaction costs

Rollover rules of thumb:
- Roll 2-3 days before expiry (avoid last-day volatility)
- Stock futures: roll early to avoid physical delivery margin
- Index futures: can roll on expiry day (cash settled)
- Wide calendar spread = expensive roll, consider reducing position
- Negative roll yield (backwardation) = paid to roll (favorable)
