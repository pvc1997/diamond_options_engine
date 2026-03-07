Price an option: $ARGUMENTS.

Parse: symbol, strike, type (CE/PE), expiry or DTE.

1. Use `price_option` for Black-Scholes theoretical price
2. Use `calculate_greeks` for all Greeks
3. Show:
   - Theoretical price
   - Intrinsic value and time value
   - Key Greeks (delta, theta, vega)
   - Probability ITM
4. If market price is available, compare with theoretical
5. If market price given, use `solve_iv` to extract IV
