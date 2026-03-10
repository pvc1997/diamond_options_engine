Run Monte Carlo simulation for futures: $ARGUMENTS.

Parse: entry price, direction (long/short), lots, optional stop/target.

1. Use `futures_monte_carlo` with 10K paths
2. Show:
   - Expected P&L and median P&L
   - Probability of profit
   - VaR at 95% and 99% confidence
   - CVaR (expected shortfall)
   - Best case / worst case
   - Stop loss hit probability (if stop provided)
   - Target hit probability (if target provided)
   - Margin call probability (if margin provided)
3. Use `futures_multi_horizon` to show P&L evolution at 25/50/75/100% of time
4. Use `futures_stress_test_tool` for 9 scenario analysis
5. Summarize: What's the risk-adjusted outlook for this trade?

Default to NIFTY long 1 lot if not specified.
