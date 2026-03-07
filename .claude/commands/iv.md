Analyze implied volatility for $ARGUMENTS.

Parse: symbol, or specific option (symbol + strike + type).

If specific option given:
1. Use `solve_iv` to calculate IV from market price
2. Show IV vs historical average

For general IV analysis:
1. Use `iv_rank_analysis` with available data
2. Show IV rank, percentile, regime
3. Use `variance_risk_premium` to compare IV vs RV
4. Recommend: sell premium (high IV) or buy options (low IV)

Include VIX context from `vix_analysis`.
