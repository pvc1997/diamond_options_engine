Analyze futures basis for $ARGUMENTS.

Parse: symbol (default NIFTY), optional futures price and spot price.

1. Use `get_spot_price` for spot if not provided
2. Estimate futures price if not provided (spot + typical basis)
3. Use `basis_analysis` to get full analysis:
   - Current basis (₹ and %)
   - Annualized basis (cost of carry)
   - Basis z-score and percentile (if historical data available)
   - Signal: rich / cheap / fair
   - Convergence rate (₹/day)
   - Roll yield (if next-month data available)
4. Use `futures_fair_value` for theoretical fair value comparison
5. Use `futures_mispricing_tool` to check for arbitrage opportunities

Explain whether the futures are trading at a premium or discount and what it means for trading.
