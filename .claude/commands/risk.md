Analyze portfolio risk.

1. Use `portfolio_status` to get current positions
2. Use `portfolio_greeks_analysis` to aggregate Greeks
3. Check risk limits — flag any warnings or breaches
4. Show:
   - Net delta (directional exposure)
   - Net gamma (acceleration risk)
   - Net theta (daily time decay P&L)
   - Net vega (volatility exposure)
   - Any risk limit breaches
5. If positions are near expiry, run `expiry_checklist`

Highlight anything requiring immediate attention.
