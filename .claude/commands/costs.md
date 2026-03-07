Calculate options trading costs for $ARGUMENTS.

Parse the user's input to determine:
- Action (buy/sell)
- Premium amount (or derive from price * lots * lot_size)
- Whether it's an index option

Use the `options_costs` MCP tool and display itemized breakdown:
brokerage, GST, STT, exchange fees, SEBI, stamp duty, slippage, total.

For spreads, use `spread_costs` to show total round-trip costs.
