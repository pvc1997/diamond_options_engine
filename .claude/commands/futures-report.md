Generate a Diamond Futures Engine trade opportunity report as a PDF.

Parse $ARGUMENTS for any combination of these parameters (all optional):

**Symbol / Underlying**
- Any F&O symbol: NIFTY, BANKNIFTY, FINNIFTY, RELIANCE, TCS, etc.
- Default: NIFTY
- Examples: "BANKNIFTY futures report", "futures report for RELIANCE"

**Date / Period**
- Specific date: "for 15 March", "as of today", "for yesterday"
- Default: today

**Capital**
- Any amount: "50 lakh capital", "10L", "2 crore", "Rs 5,00,000"
- Default: from portfolio_status.cash, else Rs. 5,00,000

**Risk Appetite**
- "conservative" — max 1 lot, wider stops, 0.5x Kelly
- "moderate" — standard sizing, 2-3 lots max (default)
- "aggressive" — full Kelly sizing, more lots, tighter stops
- "custom: max loss 1%" — explicit max-loss % of capital

**Holding Period / Style**
- "intraday" — same-day futures trade, near-month only
- "weekly" — 5-10 DTE strategies
- "monthly" — 15-25 DTE strategies
- "positional" — 25-60 DTE, may consider next month
- Default: derived from near-month DTE

**Trend / Market View**
- "bullish", "bearish", "neutral", "volatile"
- Default: neutral (scanner determines)

**Report Sections**
- "full report" — all 8 sections (default)
- "quick report" — cover + basis + trades + execution plan
- "basis only" — focus on basis & term structure analysis
- "risk only" — Monte Carlo + stress test + risk rules

**Output filename**
- "save as weekly_futures" — custom filename prefix
- Default: futures_report_{DDMMMYYYY}_{SYMBOL}.pdf

Then invoke the `futures-daily-report` skill to run the full pipeline with these resolved parameters.
