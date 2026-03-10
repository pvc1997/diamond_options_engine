Generate a Diamond Options Engine trade opportunity report as a PDF.

Parse $ARGUMENTS for any combination of these parameters (all optional):

**Symbol / Underlying**
- Any F&O symbol: NIFTY, BANKNIFTY, FINNIFTY, RELIANCE, TCS, etc.
- Default: NIFTY
- Examples: "BANKNIFTY report", "report for RELIANCE"

**Date / Period**
- Specific date: "for 15 March", "as of today", "for yesterday"
- Historical period: "last week", "for March"
- Default: today

**Expiries to cover**
- Single expiry: "only 17MAR", "just this week"
- Multiple: "17MAR and 24MAR", "next 3 expiries"
- Duration: "30 day window", "weekly only", "monthly only"
- Default: next 2 expiries

**Capital**
- Any amount: "50 lakh capital", "10L", "2 crore", "₹5,00,000"
- Default: from portfolio_status.cash, else Rs. 5,00,000

**Risk Appetite**
- "conservative" — defined risk only, smaller sizing, wider wings
- "moderate" — defined risk, standard sizing (default)
- "aggressive" — allow undefined risk strategies, full Kelly sizing
- "custom: max loss 1%" — explicit max-loss % of capital

**Holding Period / Style**
- "intraday" — 0 DTE focus, same-day exit
- "weekly" — 5–8 DTE strategies
- "monthly" — 15–30 DTE strategies
- "positional" — 30–90 DTE, longer-dated spreads, calendars
- Default: derived from expiry window

**Trend / Market View**
- "bullish", "bearish", "neutral", "volatile"
- Default: neutral (scanner determines)

**Report Sections**
- "full report" — all 10 sections (default)
- "quick report" — cover + top 3 trades + execution plan only
- "math only" — focus on BS pricing + Greeks + vol analysis
- "risk only" — stress test + Greeks + risk rules only

**Output filename**
- "save as weekly_review" — custom filename prefix
- Default: options_report_{DDMMMYYYY}_{SYMBOL}.pdf

Then invoke the `options-report` skill to run the full pipeline with these resolved parameters.
