Stress test futures position: $ARGUMENTS.

Parse: entry price, direction (long/short), lots, lot_size.

1. Use `futures_stress_test_tool` to test 9 scenarios (-10% to +10%)
2. Show P&L table:
   | Scenario | Spot Move | New Price | P&L | P&L/Lot |
3. Highlight the worst-case scenario
4. Use `futures_monte_carlo` for probabilistic risk assessment
5. Show VaR at 95% and 99% confidence
6. Calculate margin needed to withstand worst-case scenario

Default to NIFTY long 1 lot at ~22500 if not specified.
Clearly flag any scenario where loss exceeds margin.
