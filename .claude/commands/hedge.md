Hedge my equity portfolio with options.

1. Use `stock_holdings_for_options` to read stock engine holdings
2. If no stock engine found, ask for portfolio value and use `portfolio_hedge_analysis`
3. Show:
   - Portfolio value and beta
   - NIFTY lots needed for full/partial hedge
   - Hedge options ranked by cost:
     a. OTM protective puts (cheap insurance)
     b. Bear put spread (cheaper, capped protection)
     c. Zero-cost collar (free but caps upside)
4. Recommend the best hedge based on VIX regime:
   - Low VIX → puts are cheap, buy outright
   - High VIX → use spreads or collars to manage cost
5. Show annualized cost as % of portfolio
