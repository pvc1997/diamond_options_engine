Show payoff analysis for $ARGUMENTS.

Parse: strategy or specific legs with premiums.

1. Use `analyze_payoff` for max P&L, breakevens, risk-reward
2. Use `payoff_curve` for the payoff diagram data
3. Display:
   - Max profit zone
   - Max loss zone
   - Breakeven points
   - Net premium (credit/debit)
   - Risk-reward ratio
4. Show ASCII payoff diagram if possible
5. Include cost impact from `trade_cost_impact`
