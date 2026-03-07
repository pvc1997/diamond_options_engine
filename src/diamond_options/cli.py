"""CLI entry point for Diamond Options Engine.

Provides commands for options analysis, trading, and portfolio management.
Built with Typer for type-safe CLI.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="options",
    help="Diamond Options Engine — Systematic Indian options trading",
    no_args_is_help=True,
)


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


if __name__ == "__main__":
    app()
