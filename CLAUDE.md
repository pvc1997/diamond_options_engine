# Diamond Options Engine

Systematic Indian F&O options trading engine with mathematical trade suggestions.
All interactions via natural language through Claude Code.

## Quick Reference

### Project Structure
```
src/diamond_options/
  config.py           — Pydantic settings, singleton via get_config()
  cli.py              — Typer CLI entry point
  data/
    market.py         — yfinance wrapper + cache
    options_chain.py  — OptionsChain, OptionQuote, chain operations
    universe.py       — F&O stocks, lot sizes, sectors
    expiry.py         — Weekly/monthly expiry calendar
    ledger.py         — SQLite options trade ledger (multi-leg)
    costs.py          — Indian options/futures cost model (pure functions)
    kite_bridge.py    — Kite MCP bridge: parse symbols, build chains, OI analysis
    position_sync.py  — Kite position sync, portfolio reconciliation
    events.py         — Market event calendar (RBI, earnings, budget, FOMC)
  pricing/
    black_scholes.py  — BS European pricing (call/put, dividend yield)
    greeks.py         — Delta, Gamma, Theta, Vega, Rho, Vanna, Charm
    implied_volatility.py — Newton-Raphson IV solver + bisection fallback
    live_greeks.py    — Real IV/Greeks from market prices (Kite LTP → IV → Greeks)
    iv_surface.py     — Smile/skew analysis, IV rank/percentile, surface grid
    payoff.py         — Multi-leg payoff, breakevens, Monte Carlo EV
  volatility/
    historical.py     — 5 HV estimators (CC, Parkinson, GK, YZ, RS)
    forecast.py       — EWMA, GARCH(1,1), variance risk premium
    vix.py            — India VIX regime detection + signals
  strategy/
    definitions.py    — 18+ strategy specs, leg builders, catalog
    scanner.py        — Market condition scoring, strategy signal quality (0-100)
    sizing.py         — Fixed-risk & Kelly criterion position sizing
    recommender.py    — Trade recommendation engine (full pipeline)
  risk/
    portfolio_greeks.py — Aggregate Greeks, risk limits, exposure summary
    adjustments.py    — Roll/widen/close/hedge advisor, expiry checklist
    monte_carlo.py    — GBM simulation, VaR, CVaR, stress testing
    backtester.py     — Historical strategy backtesting engine
  integration/
    stock_bridge.py   — Read equity holdings from diamond_stock_engine
    overlay.py        — Covered calls, protective puts, collars for stock holdings
    hedge.py          — Portfolio-level hedging with NIFTY index options
  utils/
    indian_markets.py — NSE hours, holidays, trading day utilities
    formatters.py     — INR, Greek, IV display formatting
mcp_server/
  server.py           — FastMCP with 77 tools (Phase 1-6)
.claude/
  commands/           — 28 slash commands (/suggest, /greeks, /hedge, /covered-call, etc.)
  skills/             — 31 auto-triggering skills (strategy-selector, stock-overlay, etc.)
  hooks/              — 7 market-aware hooks (expiry alerts, VIX checks, etc.)
```

### Key Conventions
- **Package manager:** uv
- **Config singleton:** `get_config()` cached via `@lru_cache`
- **SQLite ledgers:** One `.db` per trading mode (default, paper)
- **Cost model:** Pure functions in `costs.py`, no side effects
- **Options chain:** `OptionsChain` dataclass with calls/puts, ATM, PCR, max pain
- **F&O universe:** ~75 stocks + 4 indices, lot sizes in `universe.py`
- **Expiry:** Weekly (Tuesday) for indices, monthly for stocks. Holiday-adjusted.
- **Paper trading:** Separate ledger (name="paper")

### Running Tests
```bash
uv run pytest tests/ -x --tb=short -q    # All tests (436)
uv run pytest tests/test_costs.py         # Specific module
```

### CLI Commands
```bash
uv run options status      # Portfolio status
uv run options chain NIFTY # Options chain
uv run options expiry      # Upcoming expiries
uv run options universe    # F&O stocks
uv run options costs 3250  # Cost calculator
```

### MCP Tools (89 tools — Phase 1-8)

**Foundation (13):** `fno_universe`, `index_contracts`, `lot_size`, `search_fno`, `sector_fno_stocks`, `upcoming_expiries`, `is_expiry_today`, `next_monthly_expiry`, `options_chain_summary`, `option_chain_strikes`, `max_pain`, `market_status`, `is_trading_day`

**Costs (3):** `options_costs`, `spread_costs`, `futures_costs`

**Portfolio (2):** `portfolio_status`, `trade_history`

**Pricing (5):** `price_option`, `price_spread`, `payoff_curve`, `analyze_payoff`, `put_call_parity`

**Greeks (4):** `calculate_greeks`, `greeks_comparison`, `probability_itm`, `probability_of_profit`

**IV & Volatility (10):** `solve_iv`, `iv_rank_analysis`, `iv_smile_analysis`, `iv_term_structure`, `iv_surface`, `vix_analysis`, `vix_mean_reversion`, `vix_term_structure`, `variance_risk_premium`, `strategies_for_vix_regime`

**Historical Vol (4):** `historical_volatility`, `all_hv_estimators`, `multi_window_volatility`, `rolling_volatility_series`

**Forecasting (2):** `ewma_forecast`, `garch_forecast`

**Strategy (7):** `list_strategies`, `strategy_details`, `suggest_strategy`, `scan_market_signals`, `strategy_strikes`, `compare_strategies`, `quick_iron_condor`, `quick_straddle`

**Sizing (3):** `position_size`, `kelly_position_size`, `max_lots_affordable`

**Risk (6):** `portfolio_greeks_analysis`, `adjustment_advisor`, `monte_carlo_simulation`, `stress_test_position`, `backtest_strategy_tool`, `expiry_checklist`

**What-If (3):** `what_if_spot_move`, `what_if_iv_change`, `what_if_time_decay`

**Market Data (3):** `get_spot_price`, `get_india_vix`, `download_historical_prices`, `get_ohlcv`

**Helpers (3):** `build_option_symbol`, `trade_cost_impact`, `trading_days_to_expiry`, `format_inr`

**Cross-Engine (6):** `stock_holdings_for_options`, `covered_call_suggestions`, `protective_put_suggestions`, `collar_suggestion`, `portfolio_hedge_analysis`, `covered_call_income_report`

**Live OI (Kite Bridge) (4):** `build_live_chain`, `live_oi_analysis`, `oi_walls`, `parse_kite_symbol_tool`

**Position Sync (2):** `sync_kite_positions`, `compare_kite_vs_ledger`

**Live IV & Greeks (2):** `live_greeks`, `compute_option_greeks`

**Event Calendar (4):** `upcoming_market_events`, `event_context`, `events_for_symbol`, `earnings_calendar`

### Slash Commands (28)
`/status` `/chain` `/expiry` `/costs` `/universe` `/morning` `/suggest` `/greeks` `/iv` `/risk` `/adjust` `/backtest` `/simulate` `/compare` `/payoff` `/vix` `/vol` `/whatif` `/size` `/price` `/scan` `/stress` `/condor` `/straddle` `/history` `/hedge` `/covered-call` `/collar`

### Auto-Triggering Skills (31)
`ticker-resolver` `amount-parser` `market-context` `cost-analyzer` `expiry-manager` `strategy-selector` `greeks-interpreter` `risk-monitor` `iv-regime` `position-sizer` `adjustment-trigger` `expiry-day-ops` `trade-validator` `vol-analyzer` `spread-builder` `theta-decay` `backtest-interpreter` `vix-regime-adapter` `cost-optimizer` `profit-taker` `loss-manager` `event-aware` `margin-calculator` `weekly-review` `moneyness-guide` `rollover-guide` `pnl-calculator` `portfolio-hedger` `multi-expiry` `trade-journal` `stock-overlay`

### Hooks (7)
`pre-market-scan` `post-market-log` `expiry-alert` `vix-spike` `friday-review` `position-check` `monthly-expiry`

### Indian Options Cost Rules
- **STT:** 0.0625% on SELL side only (options buy = 0 STT)
- **Brokerage:** Rs. 20 flat per order (discount brokers)
- **GST:** 18% on (brokerage + exchange fees + SEBI)
- **Exchange fees:** 0.0495%
- **SEBI:** 0.001%
- **Stamp duty:** 0.003% on BUY side only

### F&O Lot Sizes (Key)
- NIFTY: 65 | BANKNIFTY: 15 | FINNIFTY: 65
- RELIANCE: 250 | TCS: 150 | HDFCBANK: 550 | INFY: 300

### Expiry Rules
- Weekly: Every Tuesday (NIFTY, BANKNIFTY, FINNIFTY) — changed from Thursday effective 2024
- Monthly: Last Tuesday of month (all F&O stocks)
- Holiday: Moves to previous trading day

### Risk Management Notes
- **Portfolio Greeks:** Aggregate delta/gamma/theta/vega across all positions. Warns at 80% of limit, breaches at 100%
- **Risk Limits:** Max delta ±500, max gamma ±100, max vega ±₹5000, max daily theta loss -₹10000, per-position delta ±200
- **Adjustments:** Roll out (more time), roll up/down (new strike), widen (more room), close (cut loss), add hedge (cap risk)
- **Expiry Day:** Close short ITM options before 3:00 PM to avoid exercise STT (0.125% on notional). Monitor pin risk (ATM)
- **Monte Carlo:** GBM with 10K paths, VaR (5th/1st percentile), CVaR (expected shortfall), multi-expiry checkpoints
- **Stress Tests:** 9 scenarios from -10% crash to +10% melt-up
- **Backtester:** Walk-forward entry at intervals, BS-priced legs, tracks win rate/Sharpe/max drawdown/profit factor

### Strategy Engine Notes
- **18+ Strategies:** Directional (long call/put, spreads), Neutral (straddles, condors, butterflies), Volatility (strangles, ratios), Income (covered calls, jade lizard), Hedge (protective put, collar)
- **Signal Scanner:** Scores each strategy 0-100 based on IV rank, VIX regime, trend, VRP, DTE alignment
- **Position Sizing:** Fixed-risk (% of capital) with Kelly criterion alternative. VIX-adjusted multiplier reduces size in high vol
- **Trade Recommender:** Full pipeline: scan → score → build legs (BS-priced) → size → payoff analysis → Monte Carlo EV → ranked recommendations
- **VIX Regime Mapping:** Each strategy tagged with suitable VIX regimes. Crisis mode → hedge only

### Pricing & Volatility Notes
- **Black-Scholes:** European pricing with continuous dividend yield (q). Formula: C = S*e^(-qT)*N(d1) - K*e^(-rT)*N(d2)
- **Theta:** Per calendar day (/365), not per year — ATM Nifty weekly ~15-30/day
- **Vega:** Per 1% vol move (/100), not per 100%
- **IV Solver:** Newton-Raphson with Brenner-Subrahmanyam initial estimate, bisection fallback. Tolerance 1e-8, max 100 iters
- **HV Estimators:** Close-to-Close, Parkinson (range), Garman-Klass (OHLC), Yang-Zhang (overnight jumps), Rogers-Satchell (drift-independent). All use 252 trading days/year
- **GARCH(1,1):** Moment-based estimation (not MLE). Mean-reverting forecast: σ²_{t+h} = V_L + (α+β)^h * (σ²_t - V_L)
- **VIX Regimes:** low(<12), normal(12-18), elevated(18-25), high(25-35), crisis(>35) — each with position sizing multiplier
- **VRP:** IV - RV spread. Positive = sell premium, Negative = buy protection
- **Payoff:** Supports unlimited legs. Monte Carlo EV uses GBM with 10K paths

### Cross-Engine Integration Notes
- **Stock Bridge:** Reads holdings directly from diamond_stock_engine's SQLite ledger (no import dependency). Ticker conversion: RELIANCE.NS → RELIANCE
- **Covered Calls:** Requires shares >= 1 lot. Suggests 3 OTM strikes (2%, 5%, 8%) with yield, protection, and breakeven
- **Protective Puts:** Suggests OTM puts at 3%, 5%, 10% below spot. Shows cost as % of holding and annualized
- **Collars:** Sell OTM call + buy OTM put. Often near zero-cost. Caps both upside and downside
- **Portfolio Hedge:** Uses NIFTY options to hedge systematic risk. Calculates lots from portfolio_value × beta / nifty_lot_notional
- **Income Report:** Scans all F&O-eligible holdings for covered call income potential

### Architecture Notes
- Options chain supports both live (Kite MCP) and synthetic data
- Ledger tracks multi-leg spreads via `trade_group` field
- Positions: positive lots = long, negative = short
- All Greeks stored per-quote for portfolio aggregation
- Cache TTLs: chains 5min, prices 4h, IV 30min
- Dual-mode data: `config.market.data_source` = "kite" | "yfinance" | "auto"
- Kite bridge (`kite_bridge.py`): parses Kite symbols, builds OptionsChain from live quotes, OI analysis
- Live OI tools: `build_live_chain`, `live_oi_analysis`, `oi_walls` — require Kite quote data as input
- Synthetic chain tools (`options_chain_summary`, `max_pain`) now fetch live spot via yfinance
