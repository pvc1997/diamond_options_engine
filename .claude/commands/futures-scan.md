Scan futures market for best strategies now.

1. Use `get_india_vix` for VIX
2. Use `get_spot_price` for NIFTY spot (or use synthetic)
3. Estimate futures price, basis, and trend from available data
4. Use `scan_futures_signals` to score all futures strategies
5. Show top 5 strategies with:
   - Score (0-100) and confidence level
   - Category (directional, spread, arbitrage, hedge)
   - Key reasons for the score
   - Margin type (full or spread)
6. For the top pick, show full setup with `suggest_futures_strategy`

This is the "what futures should I trade today?" command.
