Suggest a collar for $ARGUMENTS.

Parse: stock symbol and optional width.

1. Use `collar_suggestion` for the stock
2. Show:
   - Call strike (sold) and put strike (bought)
   - Net premium (credit or debit)
   - Maximum gain and loss with percentages
   - Whether it's zero-cost, credit, or debit
3. Compare narrow collar (3%/3%) vs wide (5%/5%) vs asymmetric (3%/7%)
4. Include cost context from `trade_cost_impact`

Best for: protecting profits on a winning position without paying for puts.
