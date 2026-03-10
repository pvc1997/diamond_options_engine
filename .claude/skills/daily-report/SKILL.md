---
description: Generates a fully parameterised Diamond Options Engine trade opportunity PDF report
auto_trigger: true
triggers:
  - user says "generate report" or "create report" or "make a report"
  - user says "/report" or invokes the report command
  - user asks to create a PDF report for any symbol, date, or duration
  - user says "report for [symbol/date/period/capital]"
  - user wants to document trade opportunities as a PDF
  - user mentions "weekly report", "monthly report", "positional report"
---

# Options Trade Opportunity Report — Universal Pipeline

You are generating a **Diamond Options Engine Trade Report** — a comprehensive, professionally formatted PDF. This skill is fully parameterised: it works for any symbol, any date, any holding period, any capital size, and any risk appetite.

---

## STEP 1 — Resolve Parameters

Parse the user's request (and any `/report` command arguments) to resolve:

| Parameter | How to resolve | Default |
|-----------|---------------|---------|
| `SYMBOL` | User-specified F&O symbol | `NIFTY` |
| `REPORT_DATE` | User-specified date or "today" | today's date |
| `DATE_LABEL` | Human-readable: "9 March 2026" | today |
| `DATE_SHORT` | Compact: "09MAR2026" | today |
| `DAY_NAME` | "Monday" etc. | today |
| `CAPITAL` | User amount (parse INR — lakhs, crores, k) | portfolio cash or Rs. 5,00,000 |
| `RISK_APPETITE` | conservative / moderate / aggressive / custom | moderate |
| `MAX_LOSS_PCT` | Max loss as % of capital | 2% (moderate), 1% (conservative), 3% (aggressive) |
| `HOLDING_PERIOD` | intraday / weekly / monthly / positional | derived from expiry window |
| `TREND` | bullish / bearish / neutral / volatile | neutral |
| `NUM_EXPIRIES` | How many expiry windows to cover | 2 |
| `REPORT_DEPTH` | full / quick / math / risk | full |
| `FILENAME_PREFIX` | Custom filename prefix | `options_report` |
| `DEFINED_RISK_ONLY` | true if conservative/moderate, false if aggressive | true |
| `OUTPUT_PATH` | `reports/{FILENAME_PREFIX}_{DATE_SHORT}_{SYMBOL}.pdf` | derived |

**Holding period → DTE mapping:**
- intraday: DTE = 0 (focus on 0DTE or current week expiry)
- weekly: DTE range 4–8
- monthly: DTE range 12–22
- positional: DTE range 25–90
- If not specified: use next 2 upcoming expiries regardless of DTE

**Risk appetite → sizing adjustments:**
- conservative: VIX multiplier × 0.5, wing width +50% wider, defined_risk_only=true
- moderate: VIX multiplier × 1.0 (standard), defined_risk_only=true
- aggressive: VIX multiplier × 1.25, Kelly sizing, defined_risk_only=false
- custom: use explicit max_loss_pct to back-calculate lot size

**Lot size by symbol:**
- NIFTY: 65 | BANKNIFTY: 15 | FINNIFTY: 65
- Individual stocks: look up via `lot_size` tool
- Strike step: 50 for indices, 10–50 for stocks (use `option_chain_strikes` to detect)

---

## STEP 2 — Fetch Market Data (run in parallel)

Run these MCP tools **simultaneously**. Adapt symbol as needed:

1. `market_status` — open/closed, expiry day
2. `is_expiry_today` — expiry flag
3. `upcoming_expiries` (count=8, weekly=true) — full expiry calendar
4. `get_india_vix` — VIX level and regime
5. `portfolio_status` — capital, open positions, P&L
6. `options_chain_summary` for SYMBOL (num_strikes=10)
7. `upcoming_market_events` (days_ahead = max expiry window + 5) — full event horizon
8. `lot_size` for SYMBOL — confirm lot size
9. `get_spot_price` for SYMBOL — live or synthetic spot

If SYMBOL is not NIFTY, also fetch:
10. `get_spot_price` for NIFTY — for market-wide context

---

## STEP 3 — Derive Volatility Inputs

From Step 2 data, compute:

```
SPOT        = from options_chain or get_spot_price (fallback: symbol-appropriate default)
VIX         = from get_india_vix (fallback: 15.0)
IV          = VIX / 100 * 1.1     (ATM IV approximation)
RV          = IV * 0.82            (typical VRP assumption — options historically ~18% overpriced)
IV_RANK     = vix_percentile * 0.70  (rough conversion from VIX pctile to IV rank 0–100)
TREND       = user-specified or "neutral"
LOT_SIZE    = from lot_size tool
STRIKE_STEP = 50 for indices, 25–100 for stocks
```

Select expiry windows based on HOLDING_PERIOD and NUM_EXPIRIES:
```
EXPIRIES = filter upcoming_expiries by DTE range matching HOLDING_PERIOD
         → take first NUM_EXPIRIES results
         → derive EXP_DAYS[], EXP_LABELS[] arrays
```

---

## STEP 4 — Run Strategy Analysis (run in parallel)

For each expiry in EXPIRIES, run simultaneously:

**Per expiry:**
- `vix_analysis` (once, shared) — VIX regime, position sizing multiplier
- `variance_risk_premium` (once, shared) — IV vs RV spread
- `scan_market_signals` — score all strategies for this DTE, spot, VIX, IV rank, trend
- `suggest_strategy` — top N legs for this expiry
  - Pass: spot, vix, iv_rank, realized_vol, implied_vol, trend, days_to_expiry
  - Pass: capital=CAPITAL, lot_size=LOT_SIZE, strike_step=STRIKE_STEP
  - Pass: defined_risk_only=DEFINED_RISK_ONLY, max_results=5

For aggressive risk appetite, also run:
- `suggest_strategy` with defined_risk_only=false — to surface undefined-risk strategies

---

## STEP 5 — Deep Analysis on Top Strategies (run in parallel)

For each top strategy across all expiries:

1. `analyze_payoff` — max profit, max loss, breakevens, PoP, EV
2. `monte_carlo_simulation` — 10K paths, GBM, EV, VaR, CVaR
3. `calculate_greeks` for each short leg — Delta, Gamma, Theta, Vega
4. `stress_test_position` — 9 scenarios from -10% to +10%
5. `options_costs` for the primary sell leg — per-leg cost breakdown
6. `position_size` OR `kelly_position_size` depending on risk appetite
   - conservative/moderate: `position_size` with max_loss_pct
   - aggressive: `kelly_position_size` with fractional Kelly

---

## STEP 6 — Generate the PDF

Write `reports/generate_report_{DATE_SHORT}_{SYMBOL}.py` and run it with `uv run python`.

### Adaptive Report Structure

The sections included depend on `REPORT_DEPTH`:

| Section | full | quick | math | risk |
|---------|------|-------|------|------|
| Cover page | ✓ | ✓ | ✓ | ✓ |
| 1. Market Context | ✓ | ✓ | ✓ | ✓ |
| 2. Strategy Scanner | ✓ | ✓ | — | — |
| 3. Trade Recommendations | ✓ | ✓ | — | — |
| 4. BS Pricing Math | ✓ | — | ✓ | — |
| 5. HV & VRP | ✓ | — | ✓ | — |
| 6. Monte Carlo | ✓ | — | ✓ | ✓ |
| 7. Cost Analysis | ✓ | ✓ | — | — |
| 8. Execution Plan | ✓ | ✓ | — | — |
| 9. Risk Rules | ✓ | — | — | ✓ |
| 10. Summary & Rankings | ✓ | ✓ | — | ✓ |

---

### Cover Page

- Dark navy banner with "DIAMOND OPTIONS ENGINE" title
- Subtitle: `"{SYMBOL} TRADE OPPORTUNITY REPORT"`
- Meta line: `"{DAY_NAME}, {DATE_LABEL} | {HOLDING_PERIOD} | Capital: Rs. {CAPITAL}"`
- 4 metric cards (adapt values dynamically):
  - India VIX (with regime label)
  - SYMBOL Spot (with data source label)
  - IV vs RV (with VRP signal)
  - Capital / Risk Appetite

---

### Section 1 — Market Context

- VIX: level, regime, percentile, deviation from mean, signal (sell/buy/neutral vol)
- Market status: open/closed, expiry day, trading day
- Spot: SYMBOL spot price, data source
- If SYMBOL ≠ NIFTY: also show NIFTY spot as market index context
- Volatility: IV, RV, IV/RV ratio, VRP (absolute and %), IV rank
- Event calendar table (full window + 3 days buffer):
  - Columns: Date | Day | Event | Impact | Relevance to EXPIRIES
  - Color rows: HIGH=red bg, MEDIUM=amber bg, holiday=orange bg
  - Flag events that fall WITHIN any expiry window with "⚠ IN WINDOW" marker
- Warning boxes for any HIGH-impact event inside an expiry window

---

### Section 2 — Strategy Scanner

- 5 scoring dimensions table (IV alignment 25, VIX regime 20, trend 20, VRP 15, DTE 10, base 10)
- For each expiry: table of top strategies with rank, name, score, confidence, risk profile, recommended action
- Highlight: recommended strategy per expiry (green row)
- Note any undefined-risk strategies flagged in red if risk appetite = conservative/moderate

---

### Section 3 — Trade Recommendations

**Adapt the number of trades to NUM_EXPIRIES and what scored well:**

For each recommended trade:

**Trade header bar** (navy/teal/blue depending on rank):
`"TRADE {N} — {SYMBOL} {STRATEGY_NAME} — {EXP_LABEL} | Score: {SCORE}/100 | {CONFIDENCE}"`

**Legs table:** #, Action (BUY green/SELL red), Type, Strike, Premium, Role, BS-derived price

**P&L profile (two-column layout):**
Left: Net premium, Max profit, Max loss, Upper breakeven, Lower breakeven, Profit zone width, R:R ratio
Right: Lots (sizing method), Shares/contracts, Capital at risk (Rs + %), Margin required, Round-trip costs, Net P&L at max profit, PoP

**Greeks table** (for short legs):
Delta, Gamma, Theta (Rs/day per lot), Vega (Rs per 1% IV move), daily theta decay narrative

**Key math block** (monospace/code style):
- Daily theta earned (combined short legs)
- Total theta over DTE (theoretical max)
- Monte Carlo EV (10K paths)
- Probability of profit
- VaR 95% and CVaR 95%

**Event impact note** — which events fall in this trade's window, what to watch

**Stress test table** (for longest-DTE trade or if HIGH-impact event in window):
9 scenarios -10% to +10%, show P&L per lot + note

**Sizing rationale** (adapted to risk appetite):
- conservative: "VIX-adjusted 0.50× sizing, wider wings, defined risk only"
- moderate: "Standard VIX-adjusted sizing"
- aggressive: "Full Kelly criterion sizing, higher premium capture"

After primary trades: condensed cards for Trades 3 and 4 (alternative/supporting)

---

### Section 4 — Black-Scholes Pricing Mathematics

*(included in full and math report depths)*

- Full BS formula: C = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)
- Worked example using **today's actual** short call strike, actual IV, actual DTE from the primary trade
- Step-by-step d1, d2 calculation with actual numbers
- Greeks derivation: Gamma = φ(d1)/(S·σ·√T), Theta = -[S·φ(d1)·σ/(2√T)]/365, Vega = S·φ(d1)·√T/100
- IV Solver: Newton-Raphson with Brenner-Subrahmanyam seed, bisection fallback, tolerance 1e-8

---

### Section 5 — Historical Volatility & VRP

*(included in full and math report depths)*

- Table of 5 HV estimators with method description and estimated values
- VRP math: variance terms (IV² - RV²) and vol spread (IV - RV), IV/RV ratio
- Why the VRP is the structural seller's edge — explanation
- GARCH(1,1) mean-reverting forecast for each DTE in EXPIRIES:
  `σ²(t+h) = V_L + (α+β)^h × (σ²(t) - V_L)` with actual numbers
- Forecast conclusion: whether vol is expected to rise or fall

---

### Section 6 — Monte Carlo Simulation

*(included in full, math, and risk report depths)*

- GBM methodology: dS = μ·S·dt + σ·S·dW, 10K paths
- Results comparison table for all expiries covered:
  Metric | EXP1 | EXP2 | ...
  rows: Expected P&L, Median, PoP, VaR 95%, CVaR 95%, Best case, Worst case
- Interpretation: binary payoff distribution explanation, positive EV rationale

---

### Section 7 — Transaction Cost Analysis

*(included in full and quick report depths)*

- Per-leg breakdown: Brokerage, STT (sell only, 0.0625%), Exchange fee (0.0495%), SEBI (0.001%), GST (18%), Stamp duty (buy only, 0.003%), slippage — TOTAL
- Round-trip cost table for the primary trade: entry, exit, total, as % of max profit
- STT EXPIRY WARNING box (amber): ITM exercise → 0.125% on notional, worked example, 3 PM rule

---

### Section 8 — Actionable Execution Plan

*(included in full and quick report depths)*

Build a **day-by-day timeline** from today through the last expiry date. For each meaningful day:

- TODAY: entry action, target premium range, lot count, order type, alert levels
- Holiday days: "Market CLOSED — theta accrues — no action needed"
- Data release days (CPI, IIP, RBI, FOMC): monitoring checklist
- Midpoint of trade: profit-taking check (if at 50% of max premium → close)
- Pre-event days (1 day before HIGH-impact): close or hedge decision tree
- Expiry days: 2:30 PM / 3:00 PM protocol, ITM vs OTM handling

Use colored section bars per day:
- TEAL: active entry/exit action
- ORANGE: monitor / warning
- RED: critical / FOMC / close deadline
- NAVY: informational / holiday

**Decision trees for common scenarios:**
- If SYMBOL moves > ADJUSTMENT_TRIGGER (50 pts for index, 2% for stocks): roll tested wing
- If premium decays to PROFIT_TARGET (50%): close for profit
- If loss hits STOP_LOSS (2× premium): cut position

---

### Section 9 — Risk Management Rules

*(included in full and risk report depths)*

7 rules table adapted to risk appetite:

| # | Rule | Value (conservative) | Value (moderate) | Value (aggressive) |
|---|------|---------------------|-----------------|-------------------|
| 1 | Max loss per trade | 1% of capital | 2% of capital | 3% of capital |
| 2 | Stop loss trigger | 1.5× net premium | 2× net premium | 3× net premium |
| 3 | Adjustment trigger | Short strike ±30 pts | Short strike ±50 pts | Short strike ±75 pts |
| 4 | Adjustment action | Close position | Roll wing OTM | Roll + add size |
| 5 | Profit target | 40% of max premium | 50–60% | 70% or expiry |
| 6 | Event rule | Close 2 days before HIGH | Close day before | Hedge, don't close |
| 7 | Position limit | 2 positions | 3 positions | 5 positions |

Show the column matching the user's actual RISK_APPETITE, highlight it in green.

---

### Section 10 — Summary Rankings & Final Recommendation

*(included in full, quick, and risk report depths)*

- Rankings table: all trades with score, strategy, expiry, max profit, max loss, PoP, Monte Carlo EV
- Highlight top trade row in green
- Final recommendation numbered steps:
  `STEP 1 — TODAY: ...`
  `STEP 2 — AFTER [EVENT]: ...`
  `STEP 3 — PRE-[EXPIRY]: ...`
  Adapted to actual events in the window
- Expected combined P&L (max profit scenario) and Monte Carlo combined EV
- Disclaimer: italic, small font, justified

---

## STEP 7 — PDF Design Standards (non-negotiable)

```python
from reportlab.lib.pagesizes import A4
PAGE_W, PAGE_H = A4       # 595 × 842 pt
MARGIN = 1.8 * cm
BW = PAGE_W - 2 * MARGIN  # ≈ 493 pt — SINGLE source of truth for all widths
```

**Layout rules (learned from production bugs):**
- ALL `colWidths` lists must sum to exactly `BW`. Pattern: `[c1, c2, ..., BW - (c1+c2+...)]`
- NEVER use `PAGE_W - 2*MARGIN` inline — always reference `BW`
- two_col_kv (4-column key-value layout): `colWidths=[BW/4, BW/4, BW/4, BW/4]` — never hardcode cm values here
- Nested inner tables in warning/profit boxes: `colWidths=[BW - 24]` (24pt for border padding)
- Cover metric cards: inner card = `(BW/2) - 4`, outer 2-col = `[BW/2, BW/2]`
- Summary table with 8 columns: ensure widths are tight (1–4cm each), last col fills remainder

**Colors:**
```python
NAVY       = "#0D1B2A"   # headers, trade banners
NAVY_LIGHT = "#1B2E45"   # section bars, secondary header
BLUE       = "#1565C0"   # accent
BLUE_LIGHT = "#E3F0FF"   # alternate rows
TEAL       = "#00796B"   # profit, BUY, positive
RED        = "#C62828"   # loss, SELL, HIGH events
ORANGE     = "#E65100"   # warnings, MEDIUM events
AMBER_BG   = "#FFF3E0"   # warning box background
GREEN_BG   = "#E8F5E9"   # profit/insight box background
GRAY_LIGHT = "#F5F7FA"   # alternate table rows
```

**Page structure:**
- Page 1: tall navy banner (5.2cm high), gold diamond icon, large title in white
  - topMargin = 5.8cm
- Pages 2+: slim navy header bar (1.4cm), report title left + page number right
  - topMargin = 1.8cm
- All pages: navy footer, "Diamond Options Engine | CONFIDENTIAL | For Internal Use Only"

---

## STEP 8 — Confirm & Summarise

After PDF is generated, respond with:
- Full output path
- Page count
- Parameters used (symbol, capital, risk appetite, expiries covered, report depth)
- Top trade highlighted (strategy, expiry, max profit, PoP)
- Any critical alerts active today (expiry, HIGH-impact events in window)

---

## Data Fallbacks

| Data point | Fallback | Label in report |
|-----------|----------|----------------|
| SYMBOL spot | Index-appropriate default (NIFTY=24000, BANKNIFTY=50000) | "Synthetic / Fallback" |
| VIX | 15.0 (normal regime) | "Estimated" |
| IV | VIX/100 × 1.1 | "Derived from VIX" |
| RV | IV × 0.82 | "Estimated" |
| IV rank | VIX percentile × 0.70 | "Approximate" |
| Options chain | Synthetic BS-priced chain | "Synthetic" |

Always note data source in the report. Never silently use synthetic data without labelling it.

---

## Report Naming Convention

```
reports/options_report_{DATE_SHORT}_{SYMBOL}.pdf          # standard
reports/options_report_{DATE_SHORT}_{SYMBOL}_weekly.pdf   # weekly depth
reports/options_report_{DATE_SHORT}_{SYMBOL}_positional.pdf # positional
reports/{CUSTOM_PREFIX}_{DATE_SHORT}_{SYMBOL}.pdf         # user-specified prefix
```

Script saved alongside: same path with `.py` extension.
