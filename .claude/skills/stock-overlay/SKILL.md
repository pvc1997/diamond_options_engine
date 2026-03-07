---
description: Suggests options overlay strategies for equity holdings
auto_trigger: true
triggers:
  - user mentions their stock portfolio
  - user asks about hedging stocks with options
  - user asks about covered calls on their holdings
  - user mentions selling calls against stocks they own
  - user asks "how do I generate income from my stocks?"
---

Options overlay for equity holdings:

1. First check if stock engine holdings are available:
   - Use `stock_holdings_for_options` to read the portfolio
   - Identify F&O-eligible stocks

2. Covered call overlay:
   - For stocks with >= 1 lot: suggest selling OTM calls
   - Use `covered_call_suggestions` per stock
   - Show monthly income potential with `covered_call_income_report`
   - Best when: stock is rangebound or mildly bullish

3. Protective put overlay:
   - For stocks with large unrealized gains: suggest buying OTM puts
   - Use `protective_put_suggestions`
   - Best when: want to lock in profits without selling

4. Collar (combination):
   - Use `collar_suggestion` for zero-cost protection
   - Best when: want protection but don't want to pay for puts

5. Portfolio-level hedge:
   - Use `portfolio_hedge_analysis` with NIFTY options
   - Best when: want to hedge systematic risk across entire portfolio

Always check: does the user have enough shares for at least 1 lot?
