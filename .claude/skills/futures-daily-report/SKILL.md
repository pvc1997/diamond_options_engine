---
description: Generates a fully parameterised Diamond Futures Engine trade opportunity PDF report
auto_trigger: true
triggers:
  - user says "futures report" or "generate futures report" or "create futures report"
  - user says "/futures-report" or invokes the futures-report command
  - user asks to create a PDF report for futures trading
  - user says "futures report for [symbol/date/period/capital]"
  - user wants to document futures trade opportunities as a PDF
  - user mentions "futures weekly report", "futures monthly report"
---

# Futures Trade Opportunity Report — Universal Pipeline

You are generating a **Diamond Futures Engine Trade Report** — a comprehensive, professionally formatted PDF for futures trading opportunities. This skill is fully parameterised: it works for any symbol, any date, any holding period, any capital size, and any risk appetite.

---

## STEP 1 — Resolve Parameters

Parse the user's request (and any `/futures-report` command arguments) to resolve:

| Parameter | How to resolve | Default |
|-----------|---------------|---------|
| `SYMBOL` | User-specified F&O symbol | `NIFTY` |
| `REPORT_DATE` | User-specified date or "today" | today's date |
| `DATE_LABEL` | Human-readable: "10 March 2026" | today |
| `DATE_SHORT` | Compact: "10MAR2026" | today |
| `DAY_NAME` | "Tuesday" etc. | today |
| `CAPITAL` | User amount (parse INR — lakhs, crores, k) | portfolio cash or Rs. 5,00,000 |
| `RISK_APPETITE` | conservative / moderate / aggressive / custom | moderate |
| `MAX_LOSS_PCT` | Max loss as % of capital | 2% (moderate), 1% (conservative), 3% (aggressive) |
| `HOLDING_PERIOD` | intraday / weekly / monthly / positional | derived from DTE |
| `TREND` | bullish / bearish / neutral / volatile | neutral |
| `REPORT_DEPTH` | full / quick / basis / risk | full |
| `FILENAME_PREFIX` | Custom filename prefix | `futures_report` |
| `OUTPUT_PATH` | `reports/{FILENAME_PREFIX}_{DATE_SHORT}_{SYMBOL}.pdf` | derived |

**Holding period → DTE mapping:**
- intraday: DTE = 0 (near-month only, same-day exit)
- weekly: DTE range 5–10
- monthly: DTE range 15–25
- positional: DTE range 25–60 (may consider next month)
- If not specified: use near-month expiry

**Risk appetite → sizing adjustments:**
- conservative: 0.5x Kelly, max 1 lot, wider stops (3x daily move)
- moderate: 1.0x standard sizing, 2–3 lots max, standard stops (2x daily move)
- aggressive: 1.25x Kelly, more lots, tighter stops (1.5x daily move)
- custom: use explicit max_loss_pct to back-calculate lot size

**Lot size by symbol:**
- NIFTY: 65 | BANKNIFTY: 15 | FINNIFTY: 65
- Individual stocks: look up via `lot_size` tool

---

## STEP 2 — Fetch Market Data (run in parallel)

Run these MCP tools **simultaneously**:

1. `market_status` — open/closed, expiry day
2. `is_expiry_today` — expiry flag
3. `upcoming_expiries` (count=4, weekly=false) — monthly expiry calendar
4. `get_india_vix` — VIX level and regime
5. `get_spot_price` for SYMBOL — live or synthetic spot
6. `lot_size` for SYMBOL — confirm lot size
7. `futures_events` (days_ahead=60) — upcoming futures-specific events
8. `upcoming_market_events` (days_ahead=45) — full event horizon

If SYMBOL is not NIFTY, also fetch:
9. `get_spot_price` for NIFTY — for market-wide context

---

## STEP 3 — Derive Inputs & Estimate Futures Prices

From Step 2 data, compute:

```
SPOT        = from get_spot_price
VIX         = from get_india_vix (fallback: 15.0)
RV          = VIX / 100 * 0.82  (typical realized vol assumption)
LOT_SIZE    = from lot_size tool
RISK_FREE   = 0.065 (6.5% — Indian T-bill rate)
DIV_YIELD   = 0.012 for indices, 0.005-0.02 for stocks
```

Estimate futures prices if live quotes not available:
```
NEAR_FUTURES = futures_fair_value(SPOT, RISK_FREE, NEAR_DTE/365, DIV_YIELD)
NEXT_FUTURES = futures_fair_value(SPOT, RISK_FREE, NEXT_DTE/365, DIV_YIELD)
```

Select expiry based on HOLDING_PERIOD:
```
NEAR_EXPIRY = next monthly expiry from upcoming_expiries
NEXT_EXPIRY = second monthly expiry
NEAR_DTE    = days to near expiry
NEXT_DTE    = days to next expiry
```

---

## STEP 4 — Run Basis & Strategy Analysis (run in parallel)

**Basis analysis:**
- `futures_fair_value` for SYMBOL with NEAR_DTE and NEXT_DTE
- `basis_analysis` for SYMBOL — historical basis stats, z-score, percentile
- `live_basis_check` — basis, annualized carry, mispricing, signal
- `live_rollover_check` — calendar spread, roll cost, recommendation

**Strategy scanning:**
- `scan_futures_signals` — score all 14 strategies for current conditions
  - Pass: spot, near_futures, vix, realized_vol, days_to_expiry, trend, oi_buildup
- `suggest_futures_strategy` — top recommendations with sizing, costs, targets
  - Pass: spot, near_futures, vix, realized_vol, days_to_expiry, trend, symbol, capital

**Risk & volatility:**
- `vix_analysis` — VIX regime, position sizing multiplier
- `historical_volatility` for SYMBOL — recent realized volatility
- `futures_margin_estimate` for SYMBOL — margin requirement

---

## STEP 5 — Deep Analysis on Top Strategies (run in parallel)

For each top-2 recommended strategy:

1. `futures_monte_carlo` — 10K paths, VaR, CVaR, stop/target probability
2. `futures_stress_test_tool` — 9 scenarios from -10% to +10%
3. `futures_round_trip_cost_tool` — full cost breakdown
4. `futures_margin_estimate` — margin requirement per position
5. `futures_pnl_calculator` — entry/exit P&L with costs

---

## STEP 6 — Generate the PDF

Write `reports/generate_futures_report_{DATE_SHORT}_{SYMBOL}.py` and run it with `uv run python`.

### Adaptive Report Structure

The sections included depend on `REPORT_DEPTH`:

| Section | full | quick | basis | risk |
|---------|------|-------|-------|------|
| Cover page | Y | Y | Y | Y |
| 1. Market Context | Y | Y | Y | Y |
| 2. Basis & Term Structure | Y | Y | Y | — |
| 3. Strategy Scanner | Y | Y | — | — |
| 4. Trade Recommendations | Y | Y | — | — |
| 5. Monte Carlo & Risk | Y | — | — | Y |
| 6. Cost & Execution Plan | Y | Y | — | — |
| 7. Risk Rules | Y | — | — | Y |
| 8. Summary & Rankings | Y | Y | — | Y |

---

### Cover Page

- Dark navy banner with "DIAMOND FUTURES ENGINE" title
- Subtitle: `"{SYMBOL} FUTURES TRADE OPPORTUNITY REPORT"`
- Meta line: `"{DAY_NAME}, {DATE_LABEL} | {HOLDING_PERIOD} | Capital: Rs. {CAPITAL}"`
- 4 metric cards:
  - India VIX (with regime label)
  - SYMBOL Spot (with data source label)
  - Near-month Basis (annualized %, rich/cheap/fair signal)
  - Capital / Risk Appetite

---

### Section 1 — Market Context

- VIX: level, regime, percentile, signal
- Market status: open/closed, expiry day, trading day
- Spot: SYMBOL spot price, data source
- If SYMBOL is not NIFTY: also show NIFTY spot as market index context
- Realized volatility: current vs historical average
- Futures event calendar table (within DTE window):
  - Columns: Date | Day | Event | Impact | Notes
  - Color rows: HIGH=red, MEDIUM=amber, holiday=orange
  - Flag rollover windows, delivery margin dates, expiry dates
- Warning boxes for any HIGH-impact event inside the trade window

---

### Section 2 — Basis & Term Structure

- Current basis: absolute (Rs) and percentage, annualized
- Fair value: cost-of-carry model result, mispricing
- Signal: rich (sell signal) / cheap (buy signal) / fair
- Contango/backwardation status
- Calendar spread: near vs next month, cost to roll
- Rollover analysis: recommendation (roll now / wait / close), rationale
- Historical basis context: mean, std dev, z-score, percentile
- Term structure: near, next, far month fair values (if available)
- Basis convergence: expected daily convergence as expiry approaches

---

### Section 3 — Strategy Scanner

- Market condition summary: trend, basis regime, VIX regime, OI buildup
- Scoring dimensions table (Trend 30, Basis 20, VIX 15, OI 15, Rollover 10, DTE 10)
- Top 5 strategies with rank, name, score (0-100), confidence, category, rationale
- Highlight recommended strategy in green
- Note any high-risk strategies flagged in red if risk appetite is conservative

---

### Section 4 — Trade Recommendations

For each recommended trade (top 2-3):

**Trade header bar** (navy/teal/blue depending on rank):
`"TRADE {N} — {SYMBOL} {STRATEGY_NAME} | Score: {SCORE}/100 | {CONFIDENCE}"`

**Trade details table:**
- Action: BUY/SELL
- Entry price (futures LTP or fair value)
- Target price and stop loss
- Lots and lot size
- Margin required
- Contract value (notional)
- Risk-reward ratio

**P&L profile (two-column layout):**
Left: Entry, Target, Stop, Max profit (Rs), Max loss (Rs), R:R ratio, Breakeven
Right: Lots, Capital at risk (Rs + %), Margin required, Round-trip costs, Net P&L at target, Daily move expectation

**Key math block** (monospace):
- Daily expected move: spot x rv / sqrt(252)
- Target: 3x daily move, Stop: 2x daily move
- Monte Carlo EV (10K paths)
- Probability of hitting target vs stop
- VaR 95% and CVaR 95%

**Event impact note** — events in the trade window, rollover dates
**Stress test table** — 9 scenarios -10% to +10%, P&L per lot

**Sizing rationale** (adapted to risk appetite):
- conservative: "Max 1 lot, 0.5x Kelly, wider stops"
- moderate: "Standard sizing, 2-3 lots max"
- aggressive: "Full Kelly, higher lot count, tighter stops"

---

### Section 5 — Monte Carlo & Risk

- GBM methodology: dS = mu*S*dt + sigma*S*dW, 10K paths, linear futures P&L
- Results table:
  Metric | Value
  rows: Expected P&L, Median P&L, Prob of Profit, VaR 95%, VaR 99%, CVaR 95%, Best case, Worst case
- Stop/target hit probabilities
- Margin call probability (if margin provided)
- Multi-horizon analysis: P&L distribution at 25%, 50%, 75%, 100% of DTE
- Stress test comparison table: all 9 scenarios with P&L and % impact

---

### Section 6 — Cost & Execution Plan

**Cost breakdown:**
- Per-leg: Brokerage (Rs 20 flat), STT (0.01% buy+sell), Exchange fee (0.0019%), SEBI (0.001%), GST (18%), Stamp duty (0.002% buy), slippage
- Round-trip cost for primary trade
- Cost as % of expected P&L
- Breakeven move required

**Execution timeline** (day-by-day from today through expiry):
- TODAY: entry action, order type (limit/market), price targets
- Holiday days: "Market CLOSED — no action"
- Event days: monitoring checklist
- Rollover window: decision point for roll vs close
- Pre-delivery margin (T-4): close stock futures to avoid elevated margin
- Expiry day: settlement protocol (cash for index, physical for stocks)

Use colored section bars:
- TEAL: entry/exit action
- ORANGE: monitor/warning
- RED: critical deadline (delivery margin, expiry)
- NAVY: informational

---

### Section 7 — Risk Management Rules

Rules table adapted to risk appetite:

| # | Rule | Conservative | Moderate | Aggressive |
|---|------|-------------|----------|------------|
| 1 | Max loss per trade | 1% of capital | 2% of capital | 3% of capital |
| 2 | Stop loss | 3x daily move | 2x daily move | 1.5x daily move |
| 3 | Target | 2x daily move | 3x daily move | 4x daily move |
| 4 | Max lots | 1 lot | 2-3 lots | Kelly-sized |
| 5 | Margin utilization | Max 40% | Max 60% | Max 80% |
| 6 | Rollover rule | Roll 7 days early | Roll 5 days early | Roll 3 days early |
| 7 | Position limit | 2 positions | 3 positions | 5 positions |

Highlight the column matching user's RISK_APPETITE in green.

Additional futures-specific rules:
- Delivery margin warning: close stock futures 4+ days before expiry
- Basis monitoring: alert if annualized basis > 8% (rich) or < 4% (cheap)
- Concentration limit: max 40% of capital in single symbol

---

### Section 8 — Summary & Final Recommendation

- Rankings table: all trades with score, strategy, entry, target, stop, lots, margin, max P&L, R:R, Monte Carlo EV
- Highlight top trade row in green
- Final recommendation numbered steps:
  `STEP 1 — TODAY: ...`
  `STEP 2 — MONITORING: ...`
  `STEP 3 — PRE-EXPIRY: ...`
  Adapted to actual events and rollover windows
- Expected P&L scenarios: target hit, stop hit, expiry at entry
- Disclaimer: italic, small font

---

## STEP 7 — PDF Design Standards (non-negotiable)

```python
from reportlab.lib.pagesizes import A4
PAGE_W, PAGE_H = A4       # 595 x 842 pt
MARGIN = 1.8 * cm
BW = PAGE_W - 2 * MARGIN  # ~493 pt — SINGLE source of truth for all widths
```

**Layout rules (learned from production bugs):**
- ALL `colWidths` lists must sum to exactly `BW`. Pattern: `[c1, c2, ..., BW - (c1+c2+...)]`
- NEVER use `PAGE_W - 2*MARGIN` inline — always reference `BW`
- two_col_kv (4-column key-value layout): `colWidths=[BW/4, BW/4, BW/4, BW/4]`
- Nested inner tables in warning/profit boxes: `colWidths=[BW - 24]` (24pt for border padding)
- Cover metric cards: inner card = `(BW/2) - 4`, outer 2-col = `[BW/2, BW/2]`

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
GOLD       = "#FFD700"   # cover page diamond accent
```

**Page structure:**
- Page 1: tall navy banner (5.2cm high), gold diamond icon, large title in white
  - topMargin = 5.8cm
- Pages 2+: slim navy header bar (1.4cm), report title left + page number right
  - topMargin = 1.8cm
- All pages: navy footer, "Diamond Futures Engine | CONFIDENTIAL | For Internal Use Only"

---

## STEP 8 — Confirm & Summarise

After PDF is generated, respond with:
- Full output path
- Page count
- Parameters used (symbol, capital, risk appetite, holding period, report depth)
- Top trade highlighted (strategy, entry, target, stop, lots, margin, R:R)
- Basis signal (rich/cheap/fair with annualized %)
- Any critical alerts (expiry proximity, rollover window, delivery margin)

---

## Data Fallbacks

| Data point | Fallback | Label in report |
|-----------|----------|----------------|
| SYMBOL spot | Index default (NIFTY=24000, BANKNIFTY=50000) | "Synthetic / Fallback" |
| VIX | 15.0 (normal regime) | "Estimated" |
| Futures price | Cost-of-carry fair value | "Theoretical" |
| Realized vol | VIX/100 * 0.82 | "Estimated" |
| Historical basis | Annualized from current basis | "Current only" |

Always note data source in the report. Never silently use synthetic data without labelling it.

---

## Report Naming Convention

```
reports/futures_report_{DATE_SHORT}_{SYMBOL}.pdf          # standard
reports/futures_report_{DATE_SHORT}_{SYMBOL}_weekly.pdf   # weekly depth
reports/{CUSTOM_PREFIX}_{DATE_SHORT}_{SYMBOL}.pdf         # user-specified prefix
```

Script saved alongside: same path with `.py` extension.
