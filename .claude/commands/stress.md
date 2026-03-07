Stress test position: $ARGUMENTS.

Parse: current position or strategy to test.

1. Build position legs
2. Use `stress_test_position` for 9 scenarios (-10% to +10%)
3. Show P&L under each scenario in a table
4. Highlight:
   - Which scenarios cause max loss
   - At what point the position breaks
   - Whether the position survives a 2-sigma move
5. Compare with Monte Carlo VaR from `monte_carlo_simulation`
