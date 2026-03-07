"""Centralized configuration with Pydantic validation.

All settings loaded from .env with sensible defaults.
Access via `get_config()` singleton.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = str(PROJECT_ROOT / ".env")


class CacheSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_", env_file=_ENV_FILE, extra="ignore")

    chain_ttl: int = Field(default=300, ge=0)        # 5 min
    prices_ttl: int = Field(default=14400, ge=0)      # 4h
    iv_ttl: int = Field(default=1800, ge=0)            # 30 min


class RiskSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=_ENV_FILE, extra="ignore")

    initial_capital: float = Field(default=500000, ge=10000)
    max_risk_per_trade_pct: float = Field(default=2.0, ge=0.1, le=10.0)
    max_margin_utilization: float = Field(default=0.30, ge=0.05, le=1.0)
    max_portfolio_delta: float = Field(default=500, ge=10)
    max_open_positions: int = Field(default=10, ge=1, le=100)
    stop_loss_pct: float = Field(default=50.0, ge=10.0, le=100.0)


class MarketSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=_ENV_FILE, extra="ignore")

    risk_free_rate: float = Field(default=0.065, ge=0.0, le=0.20)
    index_ticker: str = "^NSEI"
    bank_index_ticker: str = "^NSEBANK"
    default_lookback_days: int = Field(default=252, ge=30, le=2520)
    data_source: str = Field(
        default="auto",
        description="Data source: 'kite' (live), 'yfinance' (delayed), 'auto' (kite if available, else yfinance)",
    )


class ExecutionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=_ENV_FILE, extra="ignore")

    dry_run: bool = Field(default=True)
    circuit_breaker_pct: float = Field(default=0.05, ge=0.01, le=0.20)
    max_trades_per_session: int = Field(default=20, ge=1, le=100)


class KiteSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KITE_", env_file=_ENV_FILE, extra="ignore")

    api_key: str = ""
    api_secret: str = ""
    dry_run: bool = Field(default=True)


class Config(BaseSettings):
    """Top-level configuration aggregating all subsections."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cache: CacheSettings = Field(default_factory=CacheSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    market: MarketSettings = Field(default_factory=MarketSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    kite: KiteSettings = Field(default_factory=KiteSettings)

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def ledger_dir(self) -> Path:
        return self.data_dir / "ledgers"

    @property
    def reports_dir(self) -> Path:
        return PROJECT_ROOT / "reports"

    def ledger_path(self, name: str) -> Path:
        return self.ledger_dir / f"{name}.db"

    def ensure_dirs(self) -> None:
        """Create all required runtime directories."""
        for d in [
            self.data_dir,
            self.cache_dir,
            self.cache_dir / "chains",
            self.cache_dir / "prices",
            self.ledger_dir,
            self.reports_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_config() -> Config:
    """Singleton config instance. Cached after first call."""
    cfg = Config()
    cfg.ensure_dirs()
    return cfg
