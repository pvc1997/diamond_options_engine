Suggest covered calls for $ARGUMENTS.

Parse: stock symbol, or "all" for entire portfolio.

If specific stock:
1. Use `covered_call_suggestions` with the stock
2. Show 3 strikes (conservative, balanced, aggressive)
3. For each: premium, yield, downside protection, upside cap

If "all" or no argument:
1. Use `covered_call_income_report` to scan all holdings
2. Show per-stock income potential
3. Total monthly income and annualized yield
4. Highlight best yield opportunities

Include: lot size, shares needed, shares available.
Warn if holding fewer shares than 1 lot.
