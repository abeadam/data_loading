"""Load and validate config.yaml → AppConfig."""
from pathlib import Path

import yaml

from src.types import AppConfig, InstrumentConfig

VALID_SEC_TYPES = {"STK", "IND", "CONTFUT", "FUT"}
VALID_SENTIMENT_BACKENDS = {"finbert", "vader"}


def load_config(config_path: Path) -> AppConfig:
    """Load and validate a config.yaml file, returning a fully-populated AppConfig."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    data_dir = _require_absolute_path(raw, "data_dir")
    ibkr_host = raw.get("ibkr_host", "127.0.0.1")
    ibkr_port = int(raw.get("ibkr_port", 7497))

    raw_instruments = raw.get("instruments")
    if not raw_instruments:
        raise ValueError("Config missing required field: 'instruments'")

    instruments = _load_instruments(raw_instruments)

    news = raw.get("news", {})
    sentiment_backend = news.get("sentiment_backend", "finbert")
    if sentiment_backend not in VALID_SENTIMENT_BACKENDS:
        raise ValueError(
            f"Invalid sentiment_backend '{sentiment_backend}'. "
            f"Must be one of: {sorted(VALID_SENTIMENT_BACKENDS)}"
        )

    return AppConfig(
        data_dir=data_dir,
        ibkr_host=ibkr_host,
        ibkr_port=ibkr_port,
        instruments=instruments,
        news_provider_codes=news.get("provider_codes", "BZ"),
        spy_symbol=news.get("spy_symbol", "SPY"),
        sentiment_backend=sentiment_backend,
    )


def _require_absolute_path(raw: dict, key: str) -> Path:
    value = raw.get(key)
    if value is None:
        raise ValueError(f"Config missing required field: '{key}'")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"Config field '{key}' must be an absolute path, got: '{value}'")
    return path


def _load_instruments(raw_instruments: list[dict]) -> list[InstrumentConfig]:
    seen_symbols: set[str] = set()
    instruments: list[InstrumentConfig] = []

    for raw in raw_instruments:
        symbol = raw.get("symbol", "")
        if not symbol or not symbol.isupper():
            raise ValueError(
                f"Instrument 'symbol' must be non-empty and uppercase, got: '{symbol}'"
            )
        sec_type = raw.get("sec_type", "")
        if sec_type not in VALID_SEC_TYPES:
            raise ValueError(
                f"Invalid sec_type '{sec_type}' for symbol '{symbol}'. "
                f"Must be one of: {sorted(VALID_SEC_TYPES)}"
            )
        exchange = raw.get("exchange", "")
        if not exchange:
            raise ValueError(f"Instrument '{symbol}' missing required field: 'exchange'")
        currency = raw.get("currency", "")
        if not currency:
            raise ValueError(f"Instrument '{symbol}' missing required field: 'currency'")

        if symbol in seen_symbols:
            continue  # deduplicate silently
        seen_symbols.add(symbol)

        instruments.append(InstrumentConfig(
            symbol=symbol,
            sec_type=sec_type,
            exchange=exchange,
            currency=currency,
        ))

    return instruments
