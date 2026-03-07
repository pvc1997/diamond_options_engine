# Diamond Options Engine

Systematic Indian F&O options trading engine with mathematically-backed trade suggestions.
Designed for natural language interaction through [Claude Code](https://claude.ai/claude-code).

## Features

- **89 MCP tools** for full options analysis and trading workflow
- **Black-Scholes pricing** with Greeks (delta, gamma, theta, vega, rho, vanna, charm)
- **5 HV estimators** (Close-to-Close, Parkinson, Garman-Klass, Yang-Zhang, Rogers-Satchell)
- **EWMA & GARCH(1,1)** volatility forecasting
- **18+ strategies** across directional, neutral, volatility, income, and hedge categories
- **Signal scanner** scoring strategies 0-100 based on IV rank, VIX regime, trend, VRP
- **Position sizing** with fixed-risk and Kelly criterion, VIX-adjusted
- **Portfolio Greeks** aggregation with configurable risk limits
- **Monte Carlo simulation** (10K GBM paths, VaR, CVaR, stress testing)
- **Historical backtesting** with walk-forward entry and performance metrics
- **Live OI analysis** via Kite Connect bridge
- **Cross-engine integration** with [Diamond Stock Engine](https://github.com/your-username/diamond_stock_engine) for covered calls, protective puts, collars
- **Market event calendar** (RBI, earnings, budget, FOMC, holidays)
- **Indian F&O cost model** (STT, brokerage, GST, exchange fees, SEBI, stamp duty)

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Run tests (550 tests, ~2.5s)
uv run pytest tests/ -x -q

# CLI commands
uv run options status       # Portfolio status
uv run options chain NIFTY  # Options chain
uv run options expiry       # Upcoming expiries
uv run options universe     # F&O stocks
uv run options costs 3250   # Cost calculator
```

## Requirements

- Python >= 3.9
- [uv](https://docs.astral.sh/uv/) package manager

## Project Structure

```
src/diamond_options/
  config.py              -- Pydantic settings (singleton via get_config())
  cli.py                 -- Typer CLI entry point
  data/
    market.py            -- yfinance wrapper + file cache
    options_chain.py     -- OptionsChain dataclass, PCR, max pain, OI
    universe.py          -- ~75 F&O stocks + 4 indices, lot sizes
    expiry.py            -- Weekly/monthly expiry calendar (Tue-based)
    ledger.py            -- SQLite trade ledger (multi-leg support)
    costs.py             -- Indian F&O cost model (pure functions)
    kite_bridge.py       -- Kite MCP bridge: symbols, chains, OI analysis
    position_sync.py     -- Kite position sync & portfolio reconciliation
    events.py            -- Market event calendar (100+ events)
  pricing/
    black_scholes.py     -- BS European pricing (call/put, dividend yield)
    greeks.py            -- All Greeks including Vanna, Charm
    implied_volatility.py -- Newton-Raphson IV solver + bisection fallback
    live_greeks.py       -- Real IV/Greeks from market prices via Kite
    iv_surface.py        -- Smile/skew analysis, IV rank/percentile
    payoff.py            -- Multi-leg payoff, breakevens, Monte Carlo EV
  volatility/
    historical.py        -- 5 HV estimators (CC, Parkinson, GK, YZ, RS)
    forecast.py          -- EWMA, GARCH(1,1), variance risk premium
    vix.py               -- India VIX regime detection + signals
  strategy/
    definitions.py       -- 18+ strategy specs, leg builders, catalog
    scanner.py           -- Market condition scoring, signal quality (0-100)
    sizing.py            -- Fixed-risk & Kelly criterion position sizing
    recommender.py       -- Full recommendation pipeline
  risk/
    portfolio_greeks.py  -- Aggregate Greeks, risk limits, exposure
    adjustments.py       -- Roll/widen/close/hedge advisor
    monte_carlo.py       -- GBM simulation, VaR, CVaR, stress testing
    backtester.py        -- Historical strategy backtesting engine
  integration/
    stock_bridge.py      -- Read equity holdings from diamond_stock_engine
    overlay.py           -- Covered calls, protective puts, collars
    hedge.py             -- Portfolio-level hedging with NIFTY options
  utils/
    indian_markets.py    -- NSE hours, holidays, trading day utilities
    formatters.py        -- INR, Greek, IV display formatting
mcp_server/
  server.py              -- FastMCP server with 89 tools
tests/                   -- 550 tests, all mocked, ~2.5s
```

## Claude Code Integration

### MCP Tools (89)

| Category | Count | Examples |
|----------|-------|---------|
| Foundation | 13 | `fno_universe`, `lot_size`, `upcoming_expiries`, `max_pain` |
| Pricing | 5 | `price_option`, `price_spread`, `payoff_curve`, `analyze_payoff` |
| Greeks | 4 | `calculate_greeks`, `greeks_comparison`, `probability_itm` |
| IV & Volatility | 10 | `solve_iv`, `iv_rank_analysis`, `iv_surface`, `vix_analysis` |
| Historical Vol | 4 | `historical_volatility`, `all_hv_estimators`, `rolling_volatility_series` |
| Forecasting | 2 | `ewma_forecast`, `garch_forecast` |
| Strategy | 7 | `suggest_strategy`, `scan_market_signals`, `quick_iron_condor` |
| Sizing | 3 | `position_size`, `kelly_position_size`, `max_lots_affordable` |
| Risk | 6 | `portfolio_greeks_analysis`, `monte_carlo_simulation`, `stress_test_position` |
| What-If | 3 | `what_if_spot_move`, `what_if_iv_change`, `what_if_time_decay` |
| Market Data | 4 | `get_spot_price`, `get_india_vix`, `get_ohlcv` |
| Cross-Engine | 6 | `covered_call_suggestions`, `collar_suggestion`, `portfolio_hedge_analysis` |
| Live OI | 4 | `build_live_chain`, `live_oi_analysis`, `oi_walls` |
| Position Sync | 2 | `sync_kite_positions`, `compare_kite_vs_ledger` |
| Live Greeks | 2 | `live_greeks`, `compute_option_greeks` |
| Events | 4 | `upcoming_market_events`, `event_context`, `earnings_calendar` |
| Costs | 3 | `options_costs`, `spread_costs`, `futures_costs` |
| Portfolio | 2 | `portfolio_status`, `trade_history` |
| Helpers | 4 | `build_option_symbol`, `format_inr`, `trading_days_to_expiry` |

### Slash Commands (28)

`/status` `/chain` `/expiry` `/costs` `/universe` `/morning` `/suggest` `/greeks` `/iv` `/risk` `/adjust` `/backtest` `/simulate` `/compare` `/payoff` `/vix` `/vol` `/whatif` `/size` `/price` `/scan` `/stress` `/condor` `/straddle` `/history` `/hedge` `/covered-call` `/collar`

### Auto-Triggering Skills (31)

Strategy lifecycle skills that activate automatically based on context: `strategy-selector`, `greeks-interpreter`, `risk-monitor`, `iv-regime`, `position-sizer`, `adjustment-trigger`, `expiry-day-ops`, `trade-validator`, `vol-analyzer`, `spread-builder`, `theta-decay`, `vix-regime-adapter`, `cost-optimizer`, `profit-taker`, `loss-manager`, `event-aware`, `margin-calculator`, and more.

## Indian F&O Reference

### Cost Model
| Fee | Rate | Side |
|-----|------|------|
| STT | 0.0625% | Sell only |
| Brokerage | Rs. 20 flat | Per order |
| GST | 18% | On brokerage + exchange + SEBI |
| Exchange fees | 0.0495% | Both |
| SEBI | 0.001% | Both |
| Stamp duty | 0.003% | Buy only |

### Key Lot Sizes
| Symbol | Lot Size |
|--------|----------|
| NIFTY | 65 |
| BANKNIFTY | 15 |
| FINNIFTY | 65 |
| RELIANCE | 250 |
| TCS | 150 |
| HDFCBANK | 550 |
| INFY | 300 |

### Expiry Rules
- **Weekly:** Every Tuesday (NIFTY, BANKNIFTY, FINNIFTY)
- **Monthly:** Last Tuesday of month (all F&O stocks)
- **Holiday:** Moves to previous trading day

### VIX Regimes
| Regime | VIX Range | Bias |
|--------|-----------|------|
| Low | < 12 | Buy vol |
| Normal | 12-18 | Neutral |
| Elevated | 18-25 | Sell vol (wider strikes) |
| High | 25-35 | Sell vol (reduce size) |
| Crisis | > 35 | Hedge only |

## Development

```bash
# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run pyright src/

# All tests
uv run pytest tests/ -x --tb=short -q

# Specific module
uv run pytest tests/test_costs.py

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## MCP Server Setup

The MCP server runs in its own venv:

```bash
cd mcp_server
uv sync
```

Configure in `.mcp.json` (local, not committed):
```json
{
  "mcpServers": {
    "options": {
      "command": "mcp_server/.venv/bin/python",
      "args": ["mcp_server/server.py"],
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings: initial capital, risk limits, cache TTLs, Kite Connect credentials.
See `.env.example` for all options.

## License

MIT License. See [LICENSE](LICENSE).
