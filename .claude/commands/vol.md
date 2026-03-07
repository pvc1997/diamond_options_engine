Analyze volatility for $ARGUMENTS.

Parse: symbol (default NIFTY).

1. Use `download_historical_prices` for price data
2. Use `all_hv_estimators` for 5 HV methods
3. Use `multi_window_volatility` for term structure (5/10/20/60 day)
4. Use `ewma_forecast` and `garch_forecast` for predictions
5. Use `variance_risk_premium` to compare IV vs RV
6. Display:
   - Current HV by all 5 methods
   - Short-term vs long-term vol (expanding or contracting?)
   - EWMA and GARCH forecasts
   - VRP: are options expensive or cheap?
7. Trading implication: sell premium or buy options?
