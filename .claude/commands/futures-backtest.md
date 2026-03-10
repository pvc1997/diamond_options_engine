Backtest a futures strategy: $ARGUMENTS.

Parse: strategy name (long_futures, short_futures, mean_reversion, momentum), optional symbol and period.

1. Use `download_historical_prices` to get price data (default: NIFTY, 1 year)
2. Use `backtest_futures` with the strategy and parsed params
3. Display results:
   - Total trades, win rate, profit factor
   - Average P&L, max win, max loss
   - Total P&L and total costs
   - Sharpe ratio, max drawdown
   - Expectancy per trade
4. Show a brief trade log (last 10 trades with entry/exit/P&L)
5. Verdict: Is this strategy worth trading?

Default to NIFTY, 1 year, long_futures if not specified.
Compare net P&L vs gross P&L to show cost impact.
