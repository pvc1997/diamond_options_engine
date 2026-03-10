"""CLI entry point for Diamond Options Engine.

Provides commands for options analysis, trading, and portfolio management.
Built with Typer for type-safe CLI.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="options",
    help="Diamond Options Engine — Systematic Indian F&O trading",
    no_args_is_help=True,
)

# Sub-app for futures commands
futures_app = typer.Typer(
    name="futures",
    help="Futures trading — positions, basis, costs, contracts",
    no_args_is_help=True,
)
app.add_typer(futures_app, name="futures")


@app.command()
def status():
    """Show options portfolio status — positions, P&L, margin usage."""
    from diamond_options.data.ledger import OptionsLedger
    from diamond_options.utils.formatters import fmt_inr

    ledger = OptionsLedger()
    positions = ledger.get_positions()
    cash = ledger.get_cash()
    margin = ledger.get_margin_used()
    capital = ledger.get_initial_capital()

    typer.echo(f"\n{'='*50}")
    typer.echo("  Diamond Options Engine — Portfolio Status")
    typer.echo(f"{'='*50}")
    typer.echo(f"  Cash:           {fmt_inr(cash)}")
    typer.echo(f"  Margin Used:    {fmt_inr(margin)}")
    typer.echo(f"  Capital:        {fmt_inr(capital)}")
    typer.echo(f"  Open Positions: {len(positions)}")

    if positions:
        typer.echo(f"\n  {'Symbol':<10} {'Strike':>8} {'Type':>4} {'Lots':>5} {'Avg':>8} {'Expiry'}")
        typer.echo(f"  {'-'*55}")
        for p in positions:
            typer.echo(
                f"  {p.symbol:<10} {p.strike:>8.0f} {p.option_type:>4} "
                f"{p.lots:>5} {p.avg_price:>8.2f} {p.expiry}"
            )
    typer.echo()


@app.command()
def chain(
    symbol: str = typer.Argument(help="Underlying symbol (e.g., NIFTY, RELIANCE)"),
    num_strikes: int = typer.Option(10, "--strikes", "-s", help="OTM strikes per side"),
):
    """Display options chain for a symbol."""
    from diamond_options.data.options_chain import generate_strikes, build_synthetic_chain
    from diamond_options.data.expiry import next_weekly_expiry
    from diamond_options.data.universe import get_fno_stock, INDEX_CONTRACTS
    from diamond_options.utils.formatters import fmt_strike

    # Determine strike step
    if symbol.upper() in INDEX_CONTRACTS:
        step = 50 if symbol.upper() == "NIFTY" else 100
        spot = 22500.0  # Placeholder — will use live data when MCP is connected
    else:
        stock = get_fno_stock(symbol)
        if not stock:
            typer.echo(f"  {symbol} is not in the F&O universe.")
            raise typer.Exit(1)
        spot = 1000.0  # Placeholder
        step = 50 if spot > 500 else 10

    expiry = next_weekly_expiry()
    strikes = generate_strikes(spot, step, num_strikes)
    chain_data = build_synthetic_chain(symbol.upper(), spot, expiry, strikes)

    typer.echo(f"\n  {symbol.upper()} Chain | Spot: {spot:.2f} | Expiry: {expiry}")
    typer.echo(f"  ATM Strike: {fmt_strike(chain_data.atm_strike)}")
    typer.echo(f"  Strikes: {len(strikes)}")
    typer.echo()


@app.command()
def expiry():
    """Show upcoming F&O expiry dates."""
    from diamond_options.data.expiry import upcoming_expiries, expiry_label, classify_expiry

    typer.echo("\n  Upcoming F&O Expiries")
    typer.echo(f"  {'Date':<12} {'Label':<8} {'Type':<15} {'Days'}")
    typer.echo(f"  {'-'*45}")

    from datetime import date as d
    today = d.today()

    for exp in upcoming_expiries(count=12):
        label = expiry_label(exp)
        cls = classify_expiry(exp)
        days = (exp - today).days
        typer.echo(f"  {exp.isoformat():<12} {label:<8} {cls:<15} {days}d")
    typer.echo()


@app.command()
def universe(
    sector: str = typer.Option("", "--sector", "-s", help="Filter by sector"),
):
    """Show F&O-permitted stocks with lot sizes."""
    from diamond_options.data.universe import FNO_STOCKS, get_fno_by_sector

    stocks = get_fno_by_sector(sector) if sector else FNO_STOCKS

    typer.echo(f"\n  F&O Universe ({len(stocks)} stocks)")
    typer.echo(f"  {'Symbol':<15} {'Lot':>6} {'Sector':<25}")
    typer.echo(f"  {'-'*50}")
    for s in stocks:
        typer.echo(f"  {s.symbol:<15} {s.lot_size:>6} {s.sector:<25}")
    typer.echo()


@app.command()
def costs(
    premium: float = typer.Argument(help="Premium amount in INR"),
    action: str = typer.Option("BUY", "--action", "-a", help="BUY or SELL"),
):
    """Calculate options transaction costs."""
    from diamond_options.data.costs import calculate_options_costs
    from diamond_options.utils.formatters import fmt_inr

    breakdown = calculate_options_costs(action.upper(), premium)

    typer.echo(f"\n  Options Cost Breakdown ({action.upper()} @ {fmt_inr(premium)})")
    typer.echo(f"  {'='*35}")
    typer.echo(f"  Brokerage:     {fmt_inr(breakdown.brokerage)}")
    typer.echo(f"  GST:           {fmt_inr(breakdown.gst)}")
    typer.echo(f"  STT:           {fmt_inr(breakdown.stt)}")
    typer.echo(f"  Exchange Fees: {fmt_inr(breakdown.exchange_fees)}")
    typer.echo(f"  SEBI Charges:  {fmt_inr(breakdown.sebi_charges)}")
    typer.echo(f"  Stamp Duty:    {fmt_inr(breakdown.stamp_duty)}")
    typer.echo(f"  Slippage:      {fmt_inr(breakdown.slippage)}")
    typer.echo(f"  {'='*35}")
    typer.echo(f"  TOTAL:         {fmt_inr(breakdown.total)}")
    typer.echo()


# ── Futures commands ──────────────────────────────────────────────


@futures_app.command("status")
def futures_status():
    """Show futures portfolio status — positions, margin, notional exposure."""
    from diamond_options.data.futures_ledger import FuturesLedger
    from diamond_options.data.universe import get_futures_margin_pct
    from diamond_options.utils.formatters import fmt_inr

    ledger = FuturesLedger()
    positions = ledger.get_positions()
    cash = ledger.get_cash()
    margin = ledger.get_margin_used()
    capital = ledger.get_initial_capital()

    total_notional = sum(p.notional_value for p in positions)
    margin_util = (margin / capital * 100) if capital > 0 else 0.0

    typer.echo(f"\n{'='*60}")
    typer.echo("  Diamond Options Engine — Futures Portfolio")
    typer.echo(f"{'='*60}")
    typer.echo(f"  Capital:          {fmt_inr(capital)}")
    typer.echo(f"  Cash:             {fmt_inr(cash)}")
    typer.echo(f"  Margin Used:      {fmt_inr(margin)} ({margin_util:.1f}%)")
    typer.echo(f"  Total Notional:   {fmt_inr(total_notional)}")
    typer.echo(f"  Open Positions:   {len(positions)}")

    if positions:
        typer.echo(
            f"\n  {'Symbol':<12} {'Expiry':<12} {'Lots':>5} {'Avg':>10} "
            f"{'Notional':>12} {'Margin%':>8}"
        )
        typer.echo(f"  {'-'*65}")
        for p in positions:
            margin_pct = get_futures_margin_pct(p.symbol) * 100
            direction = "L" if p.is_long else "S"
            typer.echo(
                f"  {p.symbol:<12} {p.expiry:<12} {p.lots:>4}{direction} "
                f"{p.avg_price:>10.2f} {fmt_inr(p.notional_value):>12} "
                f"{margin_pct:>7.1f}%"
            )
    typer.echo()


@futures_app.command("chain")
def futures_chain(
    symbol: str = typer.Argument(help="Underlying symbol (e.g., NIFTY, RELIANCE)"),
):
    """Show futures term structure — near, next, and far month contracts."""
    from diamond_options.data.futures_chain import load_futures_chain_from_cache
    from diamond_options.data.universe import get_lot_size, INDEX_CONTRACTS, get_fno_stock
    from diamond_options.utils.formatters import fmt_inr

    sym = symbol.upper()

    # Validate symbol
    if sym not in INDEX_CONTRACTS and not get_fno_stock(sym):
        typer.echo(f"  {sym} is not in the F&O universe.")
        raise typer.Exit(1)

    chain = load_futures_chain_from_cache(sym)
    if not chain:
        typer.echo(f"  No cached futures chain for {sym}.")
        typer.echo("  Use Kite MCP to fetch live data first.")
        raise typer.Exit(1)

    lot = get_lot_size(sym)
    typer.echo(f"\n  {sym} Futures Term Structure (lot: {lot})")
    typer.echo(f"  {'='*60}")

    from datetime import date as d

    today = d.today()
    contracts = [
        ("Near", chain.near_month),
        ("Next", chain.next_month),
        ("Far", chain.far_month),
    ]
    typer.echo(
        f"  {'Month':<6} {'Expiry':<12} {'Price':>10} {'Basis':>8} "
        f"{'Basis%':>8} {'Ann.Basis':>10}"
    )
    typer.echo(f"  {'-'*58}")
    for label, quote in contracts:
        if quote:
            exp_str = (
                quote.expiry.isoformat()
                if isinstance(quote.expiry, d)
                else str(quote.expiry)
            )
            dte = (quote.expiry - today).days if isinstance(quote.expiry, d) else 20
            ann_basis = quote.annualized_basis(dte)
            typer.echo(
                f"  {label:<6} {exp_str:<12} {quote.last_price:>10.2f} "
                f"{quote.basis:>8.2f} {quote.basis_pct:>7.3f}% "
                f"{ann_basis:>9.2f}%"
            )

    cal_spread = chain.calendar_spread
    if cal_spread is not None:
        typer.echo(f"\n  Calendar Spread:  {cal_spread:.2f}")
    rollover = chain.rollover_pct
    typer.echo(f"  Rollover %:       {rollover:.2f}%")
    typer.echo()


@futures_app.command("basis")
def futures_basis(
    symbol: str = typer.Argument(help="Underlying symbol (e.g., NIFTY, RELIANCE)"),
    futures_price: float = typer.Argument(help="Current futures price"),
    spot_price: float = typer.Argument(help="Current spot price"),
    days_to_expiry: int = typer.Option(20, "--dte", "-d", help="Days to expiry"),
):
    """Analyze futures basis — fair value, annualized carry, signal."""
    from diamond_options.pricing.basis_analysis import analyze_basis
    from diamond_options.pricing.futures_pricing import theoretical_futures_price
    from diamond_options.config import get_config
    from diamond_options.utils.formatters import fmt_inr

    cfg = get_config()
    r = cfg.market.risk_free_rate

    fair = theoretical_futures_price(spot_price, r, days_to_expiry / 365.0)
    result = analyze_basis(
        futures_price=futures_price,
        spot_price=spot_price,
        days_to_expiry=days_to_expiry,
    )

    typer.echo(f"\n  {symbol.upper()} Basis Analysis")
    typer.echo(f"  {'='*45}")
    typer.echo(f"  Spot:              {spot_price:>12.2f}")
    typer.echo(f"  Futures:           {futures_price:>12.2f}")
    typer.echo(f"  Fair Value:        {fair:>12.2f}")
    typer.echo(f"  Basis (₹):        {result.current_basis:>12.2f}")
    typer.echo(f"  Basis (%):         {result.current_basis_pct:>11.3f}%")
    typer.echo(f"  Annualized Basis:  {result.annualized_basis:>11.2f}%")
    typer.echo(f"  Signal:            {result.signal:>12}")
    typer.echo(f"  DTE:               {days_to_expiry:>12}")
    typer.echo()


@futures_app.command("costs")
def futures_costs(
    price: float = typer.Argument(help="Futures price per unit"),
    lots: int = typer.Option(1, "--lots", "-l", help="Number of lots"),
    lot_size: int = typer.Option(65, "--lot-size", "-s", help="Lot size"),
    action: str = typer.Option("BUY", "--action", "-a", help="BUY or SELL"),
):
    """Calculate futures transaction costs and breakeven."""
    from diamond_options.data.costs import (
        calculate_futures_costs,
        futures_round_trip_cost,
        futures_breakeven,
    )
    from diamond_options.utils.formatters import fmt_inr

    turnover = price * lots * lot_size
    breakdown = calculate_futures_costs(action.upper(), turnover)
    rt_cost = futures_round_trip_cost(price, lots, lot_size)
    be = futures_breakeven(price, lots, lot_size, action.upper())

    typer.echo(
        f"\n  Futures Cost Breakdown ({action.upper()} {lots}L × {lot_size} @ {price:.2f})"
    )
    typer.echo(f"  Turnover:      {fmt_inr(turnover)}")
    typer.echo(f"  {'='*35}")
    typer.echo(f"  Brokerage:     {fmt_inr(breakdown.brokerage)}")
    typer.echo(f"  GST:           {fmt_inr(breakdown.gst)}")
    typer.echo(f"  STT:           {fmt_inr(breakdown.stt)}")
    typer.echo(f"  Exchange Fees: {fmt_inr(breakdown.exchange_fees)}")
    typer.echo(f"  SEBI Charges:  {fmt_inr(breakdown.sebi_charges)}")
    typer.echo(f"  Stamp Duty:    {fmt_inr(breakdown.stamp_duty)}")
    typer.echo(f"  Slippage:      {fmt_inr(breakdown.slippage)}")
    typer.echo(f"  {'='*35}")
    typer.echo(f"  One-Way:       {fmt_inr(breakdown.total)}")
    typer.echo(f"  Round-Trip:    {fmt_inr(rt_cost)}")
    typer.echo(f"  Breakeven:     {be:.2f}")
    typer.echo()


@futures_app.command("contracts")
def futures_contracts(
    symbol: str = typer.Argument(
        None, help="Symbol to show (e.g., NIFTY). Omit for all indices."
    ),
):
    """List available futures contracts with lot sizes and margin estimates."""
    from diamond_options.data.universe import (
        INDEX_CONTRACTS,
        get_fno_stock,
        get_lot_size,
        get_futures_margin_pct,
        FNO_STOCKS,
    )
    from diamond_options.utils.formatters import fmt_inr

    if symbol:
        sym = symbol.upper()
        is_index = sym in INDEX_CONTRACTS
        lot = INDEX_CONTRACTS[sym]["lot_size"] if is_index else get_lot_size(sym)
        margin_pct = get_futures_margin_pct(sym) * 100

        typer.echo(f"\n  {sym} Futures Contract")
        typer.echo(f"  {'='*35}")
        typer.echo(f"  Type:          {'Index' if is_index else 'Stock'}")
        typer.echo(f"  Lot Size:      {lot}")
        typer.echo(f"  Margin %:      {margin_pct:.1f}%")
        typer.echo(f"  Settlement:    {'Cash' if is_index else 'Physical delivery'}")
        typer.echo(f"  Expiry:        {'Weekly (Tue)' if is_index else 'Monthly (last Tue)'}")
    else:
        # Show all indices + top stocks
        typer.echo(f"\n  Futures Contracts — Indices")
        typer.echo(f"  {'Symbol':<12} {'Lot':>6} {'Margin%':>8} {'Settlement':<12}")
        typer.echo(f"  {'-'*42}")
        for sym, info in INDEX_CONTRACTS.items():
            margin_pct = get_futures_margin_pct(sym) * 100
            typer.echo(
                f"  {sym:<12} {info['lot_size']:>6} {margin_pct:>7.1f}% {'Cash':<12}"
            )

        typer.echo(f"\n  Futures Contracts — Stocks ({len(FNO_STOCKS)} available)")
        typer.echo(f"  {'Symbol':<12} {'Lot':>6} {'Margin%':>8} {'Sector':<20}")
        typer.echo(f"  {'-'*50}")
        for s in FNO_STOCKS[:20]:
            margin_pct = get_futures_margin_pct(s.symbol) * 100
            typer.echo(
                f"  {s.symbol:<12} {s.lot_size:>6} {margin_pct:>7.1f}% {s.sector:<20}"
            )
        if len(FNO_STOCKS) > 20:
            typer.echo(f"  ... and {len(FNO_STOCKS) - 20} more (use --symbol for details)")
    typer.echo()


@app.command()
def portfolio(
    capital: float = typer.Option(500000, help="Total trading capital"),
):
    """Unified portfolio view — equity + options + futures combined."""
    from diamond_options.risk.unified_portfolio import (
        build_unified_portfolio,
        unified_daily_summary,
    )
    from diamond_options.utils.formatters import fmt_inr

    # Build with empty data — in practice, caller passes real positions
    # This CLI command shows the structure; real data comes from MCP tools
    portfolio_risk = build_unified_portfolio(capital=capital)
    summary = unified_daily_summary(portfolio_risk, capital)

    typer.echo("\n  === UNIFIED PORTFOLIO ===\n")
    typer.echo(f"  NAV:           {fmt_inr(summary['nav'])}")
    typer.echo(f"  Capital:       {fmt_inr(summary['capital'])}")
    typer.echo(f"  Total P&L:     {fmt_inr(summary['total_unrealized_pnl'])}")
    typer.echo(f"  Margin Used:   {fmt_inr(summary['margin_used'])}")
    typer.echo(f"  Margin Util:   {summary['margin_utilization_pct']:.1f}%")
    typer.echo(f"  Available:     {fmt_inr(summary['available_margin'])}")
    typer.echo(f"  Risk Level:    {summary['risk_level']}")
    typer.echo(f"  Hedge Ratio:   {summary['hedge_ratio']:.2f}")

    typer.echo(f"\n  Equity:  {summary['equity']['count']} stocks, value {fmt_inr(summary['equity']['value'])}")
    typer.echo(f"  Options: {summary['options']['count']} positions ({summary['options']['long']}L/{summary['options']['short']}S), theta {fmt_inr(summary['options']['daily_theta'])}/day")
    typer.echo(f"  Futures: {summary['futures']['count']} positions ({summary['futures']['long']}L/{summary['futures']['short']}S)")

    if summary["alerts"]:
        typer.echo(f"\n  Alerts ({len(summary['alerts'])}):")
        for a in summary["alerts"]:
            icon = {"critical": "!!", "breach": "!", "warning": "~", "info": "-"}.get(a["level"], "-")
            typer.echo(f"    [{icon}] {a['message']}")
    typer.echo()


if __name__ == "__main__":
    app()
