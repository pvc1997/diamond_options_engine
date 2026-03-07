Run Monte Carlo simulation for $ARGUMENTS.

Parse: strategy or specific legs, optional parameters.

1. Build the position legs (from strategy slug or explicit legs)
2. Use `monte_carlo_simulation` with 10K paths
3. Display:
   - Expected P&L and median P&L
   - Probability of profit
   - VaR 95 and VaR 99 (worst-case thresholds)
   - CVaR (expected shortfall)
   - Best case / worst case
   - Percentile distribution
4. Use `stress_test_position` for extreme scenarios
5. Verdict: Is the risk/reward favorable?
