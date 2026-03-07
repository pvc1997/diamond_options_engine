Calculate position size for $ARGUMENTS.

Parse: strategy, capital, risk tolerance.

1. Determine max loss per lot (from strategy analysis)
2. Use `position_size` for fixed-risk sizing
3. Use `kelly_position_size` if win rate data available
4. Show:
   - Recommended lots
   - Capital at risk (absolute and %)
   - Margin required
   - VIX adjustment applied
   - Method used (fixed_risk or kelly)
5. Safety check: warn if risk > 5% of capital
