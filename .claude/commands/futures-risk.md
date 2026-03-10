Analyze futures portfolio risk.

1. Use `portfolio_status` to get current futures positions (if any in ledger)
2. For each position, use `futures_portfolio_risk` to aggregate:
   - Net notional (long vs short)
   - Margin utilization
   - Unrealized P&L
   - Directional bias
3. Check risk alerts:
   - Notional exposure limits
   - Margin utilization > 60%
   - Unrealized loss > 5% of capital
   - Concentration in single symbol > 40%
   - Near-expiry positions (< 2 DTE)
   - Basis deviation
4. If positions near expiry, run `futures_expiry_checklist_tool`
5. Use `futures_adjustment_advisor` for any at-risk positions

Highlight anything requiring immediate attention. Show risk level (LOW/MODERATE/HIGH/CRITICAL).
