---
description: Monitors unified portfolio risk across equity, options, and futures
auto_trigger: true
triggers:
  - user asks about "portfolio risk" or "total risk" or "overall risk"
  - user asks "how is my portfolio?" or "portfolio status" combining stocks and derivatives
  - user mentions wanting a "unified view" or "combined view" or "cross-product"
  - user asks about hedge effectiveness or hedge ratio
  - user asks about total margin or margin utilization across products
  - user wants to see net exposure per symbol across all products
---

# Unified Risk Monitor

You are monitoring risk across all three products: equity, options, and futures.

## When to trigger

This skill activates when the user's query involves:
- Overall portfolio health across multiple products
- Cross-product risk (e.g., "am I hedged?", "total margin?")
- Net exposure per symbol (equity + derivatives)
- Combined P&L across products

## Steps

1. **Gather positions from all sources** (run in parallel):
   - `portfolio_status` — options positions and cash/margin
   - `stock_holdings_for_options` — equity from stock engine (may fail if no stock engine)
   - Check for futures positions via context or user input

2. **Build unified view**:
   - Use `unified_portfolio_status` to get combined NAV, margin, P&L
   - Use `unified_exposure_analysis` for per-symbol breakdown
   - Use `unified_risk_dashboard` for alerts and risk level

3. **Present in priority order**:
   - **Critical alerts first** (margin breach, concentration, unhedged exposure)
   - **Risk level** with explanation
   - **Per-symbol exposure** showing hedge status
   - **Margin breakdown** (options + futures)
   - **Actionable recommendations**

## Interpretation guidelines

- **Hedge ratio > 0.8**: Well-hedged, equity protected
- **Hedge ratio 0.3–0.8**: Partially hedged, moderate protection
- **Hedge ratio < 0.3**: Minimally hedged, full directional exposure
- **Margin > 60%**: Avoid new positions
- **Margin > 80%**: Reduce exposure immediately
- **Concentration > 40%**: Diversify or hedge specific symbol

## Cross-product insights

When you see both equity and derivatives on the same symbol:
- Long stock + Short futures = Delta-neutral hedge (earn basis as income)
- Long stock + Short calls = Covered call (income strategy)
- Long stock + Long puts = Protective put (insurance)
- Long stock + Short futures + Short puts = Complex — check net exposure carefully

Always convert to net directional exposure per symbol before making recommendations.
