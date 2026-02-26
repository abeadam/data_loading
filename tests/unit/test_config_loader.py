"""Tests for src/config_loader.py."""
from pathlib import Path

import pytest
import yaml


def write_yaml(tmp_path: Path, data: dict) -> Path:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(data))
    return config_file


VALID_CONFIG = {
    "data_dir": "/tmp/data",
    "ibkr_host": "127.0.0.1",
    "ibkr_port": 7497,
    "instruments": [
        {"symbol": "SPY", "sec_type": "STK", "exchange": "SMART", "currency": "USD"},
    ],
    "news": {
        "provider_codes": "BZ",
        "spy_symbol": "SPY",
        "sentiment_backend": "finbert",
    },
}


class TestValidConfig:
    def test_returns_app_config(self, tmp_path):
        from src.config_loader import load_config
        from src.types import AppConfig

        config_file = write_yaml(tmp_path, VALID_CONFIG)
        cfg = load_config(config_file)
        assert isinstance(cfg, AppConfig)

    def test_data_dir_is_path(self, tmp_path):
        from src.config_loader import load_config

        config_file = write_yaml(tmp_path, VALID_CONFIG)
        cfg = load_config(config_file)
        assert isinstance(cfg.data_dir, Path)
        assert cfg.data_dir == Path("/tmp/data")

    def test_instruments_loaded(self, tmp_path):
        from src.config_loader import load_config

        config_file = write_yaml(tmp_path, VALID_CONFIG)
        cfg = load_config(config_file)
        assert len(cfg.instruments) == 1
        assert cfg.instruments[0].symbol == "SPY"

    def test_news_section_loaded(self, tmp_path):
        from src.config_loader import load_config

        config_file = write_yaml(tmp_path, VALID_CONFIG)
        cfg = load_config(config_file)
        assert cfg.news_provider_codes == "BZ"
        assert cfg.spy_symbol == "SPY"
        assert cfg.sentiment_backend == "finbert"

    def test_ibkr_port_is_int(self, tmp_path):
        from src.config_loader import load_config

        config_file = write_yaml(tmp_path, VALID_CONFIG)
        cfg = load_config(config_file)
        assert cfg.ibkr_port == 7497

    def test_all_valid_sec_types(self, tmp_path):
        from src.config_loader import load_config

        for sec_type in ("STK", "IND", "CONTFUT", "FUT"):
            subdir = tmp_path / f"cfg_{sec_type}"
            subdir.mkdir()
            data = {**VALID_CONFIG, "instruments": [
                {"symbol": "X", "sec_type": sec_type, "exchange": "SMART", "currency": "USD"}
            ]}
            config_file = write_yaml(subdir, data)
            cfg = load_config(config_file)
            assert cfg.instruments[0].sec_type == sec_type


class TestMissingFields:
    def test_missing_data_dir_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {k: v for k, v in VALID_CONFIG.items() if k != "data_dir"}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="data_dir"):
            load_config(config_file)

    def test_missing_instruments_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {k: v for k, v in VALID_CONFIG.items() if k != "instruments"}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="instruments"):
            load_config(config_file)


class TestValidation:
    def test_non_absolute_data_dir_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {**VALID_CONFIG, "data_dir": "relative/path"}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="data_dir"):
            load_config(config_file)

    def test_invalid_sec_type_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {**VALID_CONFIG, "instruments": [
            {"symbol": "SPY", "sec_type": "INVALID", "exchange": "SMART", "currency": "USD"}
        ]}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="sec_type"):
            load_config(config_file)

    def test_unknown_sentiment_backend_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {**VALID_CONFIG, "news": {**VALID_CONFIG["news"], "sentiment_backend": "gpt"}}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="sentiment_backend"):
            load_config(config_file)

    def test_empty_symbol_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {**VALID_CONFIG, "instruments": [
            {"symbol": "", "sec_type": "STK", "exchange": "SMART", "currency": "USD"}
        ]}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="symbol"):
            load_config(config_file)

    def test_lowercase_symbol_raises_value_error(self, tmp_path):
        from src.config_loader import load_config

        data = {**VALID_CONFIG, "instruments": [
            {"symbol": "spy", "sec_type": "STK", "exchange": "SMART", "currency": "USD"}
        ]}
        config_file = write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="symbol"):
            load_config(config_file)


class TestDuplicateDeduplication:
    def test_duplicate_symbols_are_deduplicated(self, tmp_path):
        from src.config_loader import load_config

        data = {**VALID_CONFIG, "instruments": [
            {"symbol": "SPY", "sec_type": "STK", "exchange": "SMART", "currency": "USD"},
            {"symbol": "SPY", "sec_type": "STK", "exchange": "SMART", "currency": "USD"},
        ]}
        config_file = write_yaml(tmp_path, data)
        cfg = load_config(config_file)
        assert len(cfg.instruments) == 1
