"""Tests for configuration module."""

from diamond_options.config import Config, get_config


def test_default_config():
    """Config loads with sensible defaults even without .env."""
    cfg = Config()
    assert cfg.risk.initial_capital == 500000
    assert cfg.risk.max_risk_per_trade_pct == 2.0
    assert cfg.cache.chain_ttl == 300
    assert cfg.market.risk_free_rate == 0.065
    assert cfg.execution.dry_run is True


def test_config_singleton():
    """get_config() returns same instance."""
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2


def test_config_paths():
    """Config provides correct data paths."""
    cfg = Config()
    assert cfg.data_dir.name == "data"
    assert cfg.cache_dir.name == "cache"
    assert cfg.ledger_dir.name == "ledgers"
    assert cfg.reports_dir.name == "reports"


def test_ledger_path():
    """Ledger path includes name."""
    cfg = Config()
    path = cfg.ledger_path("test_strategy")
    assert path.name == "test_strategy.db"
    assert path.parent == cfg.ledger_dir
