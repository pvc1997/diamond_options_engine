Show my complete portfolio across stocks, options, and futures.

This is the unified portfolio view that combines all three product types into a single risk dashboard.

Parse $ARGUMENTS for optional parameters:
- **Capital**: "with 10L capital", "20 lakh", "1 crore" — total trading capital
- **Focus**: "exposure" (per-symbol breakdown), "risk" (alerts and margin), "summary" (quick overview)
- Default: full unified view with all sections

**Steps to execute:**

1. **Gather data** (run in parallel):
   - `portfolio_status` — options positions and cash
   - `sync_kite_positions` — live positions from Kite (if available)
   - `stock_holdings_for_options` — equity holdings from stock engine

2. **Build unified view** using `unified_portfolio_status`:
   - Pass stock holdings, options positions, futures positions
   - Pass cash and margin from each ledger
   - Pass total capital

3. **Analyze exposure** using `unified_exposure_analysis`:
   - Per-symbol net exposure across all products
   - Identify hedged vs unhedged positions
   - Flag over-hedged or concentrated positions

4. **Check risk** using `unified_risk_dashboard`:
   - Cross-product risk alerts
   - Margin utilization breakdown
   - Hedge effectiveness

5. **Present results**:
   - NAV, total P&L, margin utilization
   - Per-symbol exposure with hedge status
   - Risk alerts sorted by severity
   - Actionable recommendations (hedge, reduce, rebalance)
