"""Tests for futures-specific configuration settings."""

from diamond_options.config import Config, FuturesRiskSettings


def test_futures_risk_defaults():
    """FuturesRiskSettings loads with sensible defaults."""
    cfg = FuturesRiskSettings()
    assert cfg.max_notional_pct == 0.60
    assert cfg.max_margin_utilization == 0.60
    assert cfg.max_concentration_pct == 0.40
    assert cfg.max_open_positions == 5
    assert cfg.stop_loss_pct == 3.0
    assert cfg.rollover_warning_days == 5
    assert cfg.basis_alert_z_score == 2.0
    assert cfg.basis_rich_annualized_pct == 8.0
    assert cfg.basis_cheap_annualized_pct == 4.0
    assert cfg.delivery_margin_buffer_days == 4


def test_futures_risk_in_config():
    """Config includes futures_risk subsection."""
    cfg = Config()
    assert hasattr(cfg, "futures_risk")
    assert isinstance(cfg.futures_risk, FuturesRiskSettings)
    assert cfg.futures_risk.max_margin_utilization == 0.60


def test_futures_risk_margin_range():
    """Margin utilization must be between 10% and 100%."""
    cfg = FuturesRiskSettings(max_margin_utilization=0.80)
    assert cfg.max_margin_utilization == 0.80


def test_futures_risk_stop_loss_range():
    """Stop loss must be between 0.5% and 20%."""
    cfg = FuturesRiskSettings(stop_loss_pct=5.0)
    assert cfg.stop_loss_pct == 5.0


def test_futures_risk_rollover_days():
    """Rollover warning days configurable."""
    cfg = FuturesRiskSettings(rollover_warning_days=7)
    assert cfg.rollover_warning_days == 7


def test_futures_risk_basis_thresholds():
    """Basis alert thresholds configurable."""
    cfg = FuturesRiskSettings(
        basis_alert_z_score=1.5,
        basis_rich_annualized_pct=10.0,
        basis_cheap_annualized_pct=3.0,
    )
    assert cfg.basis_alert_z_score == 1.5
    assert cfg.basis_rich_annualized_pct == 10.0
    assert cfg.basis_cheap_annualized_pct == 3.0


def test_futures_risk_concentration():
    """Max concentration limit configurable."""
    cfg = FuturesRiskSettings(max_concentration_pct=0.25)
    assert cfg.max_concentration_pct == 0.25


def test_futures_risk_delivery_margin():
    """Delivery margin buffer days configurable."""
    cfg = FuturesRiskSettings(delivery_margin_buffer_days=6)
    assert cfg.delivery_margin_buffer_days == 6


def test_config_preserves_existing_settings():
    """Adding futures_risk doesn't break existing config sections."""
    cfg = Config()
    assert cfg.risk.initial_capital == 500000
    assert cfg.cache.chain_ttl == 300
    assert cfg.market.risk_free_rate == 0.065
    assert cfg.execution.dry_run is True
    assert cfg.futures_risk.max_margin_utilization == 0.60
