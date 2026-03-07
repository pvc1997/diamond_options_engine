Backtest a strategy: $ARGUMENTS.

Parse: strategy name, optional period.

1. Use `download_historical_prices` to get price data
2. Use `backtest_strategy_tool` with the strategy
3. Display results:
   - Total trades, win rate, profit factor
   - Average P&L, max win, max loss
   - Sharpe ratio, max drawdown
   - Expectancy per trade
4. Show a brief trade log (last 10 trades)
5. Verdict: Is this strategy worth trading?

Default to NIFTY, 1 year, iron_condor if not specified.
