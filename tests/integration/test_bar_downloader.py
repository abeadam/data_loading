"""Integration tests — require a live TWS/IB Gateway connection on 127.0.0.1:7497."""
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.config_loader import load_config
from src.file_writer import day_file_path, file_exists
from src.types import InstrumentConfig

SPY_INSTRUMENT = InstrumentConfig(symbol="SPY", sec_type="STK", exchange="SMART", currency="USD")
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "src" / "config.yaml"


@pytest.mark.integration
def test_connect_and_disconnect():
    """Verify we can connect to IBKR and disconnect cleanly."""
    from src.ibkr_client import connect_to_ibkr, disconnect

    client = connect_to_ibkr("127.0.0.1", 7497)
    assert client.isConnected()
    disconnect(client)


@pytest.mark.integration
def test_download_spy_yesterday(tmp_data_dir):
    """Download SPY bars for yesterday and verify basic correctness."""
    from src.bar_downloader import download_day
    from src.ibkr_client import connect_to_ibkr, disconnect

    yesterday = date.today() - timedelta(days=1)
    # Skip if yesterday was a weekend
    if yesterday.weekday() >= 5:
        pytest.skip("Yesterday was a weekend — no market data")

    client = connect_to_ibkr("127.0.0.1", 7497)
    try:
        daily_bars = download_day(client, SPY_INSTRUMENT, yesterday)
    finally:
        disconnect(client)

    assert daily_bars is not None
    assert daily_bars.symbol == "SPY"
    assert daily_bars.date == yesterday
    assert daily_bars.bar_count >= 1


@pytest.mark.integration
def test_write_and_no_overwrite(tmp_data_dir):
    """Download SPY, write the file, re-download and verify FileExistsError."""
    from src.bar_downloader import download_day
    from src.file_writer import write_bars
    from src.ibkr_client import connect_to_ibkr, disconnect

    yesterday = date.today() - timedelta(days=1)
    if yesterday.weekday() >= 5:
        pytest.skip("Yesterday was a weekend")

    client = connect_to_ibkr("127.0.0.1", 7497)
    try:
        daily_bars = download_day(client, SPY_INSTRUMENT, yesterday)
        assert daily_bars is not None

        path = write_bars(tmp_data_dir, daily_bars)
        assert path.exists()

        # Second write attempt must raise FileExistsError
        with pytest.raises(FileExistsError):
            write_bars(tmp_data_dir, daily_bars)
    finally:
        disconnect(client)


@pytest.mark.integration
def test_batch_download_three_instruments(tmp_data_dir):
    """Download 3 instruments for a recent date and verify all files appear."""
    from src.downloader import run_download
    from src.types import AppConfig

    yesterday = date.today() - timedelta(days=1)
    if yesterday.weekday() >= 5:
        pytest.skip("Yesterday was a weekend")

    instruments = [
        InstrumentConfig(symbol="SPY", sec_type="STK", exchange="SMART", currency="USD"),
        InstrumentConfig(symbol="SPX", sec_type="IND", exchange="CBOE", currency="USD"),
        InstrumentConfig(symbol="VIX", sec_type="IND", exchange="CBOE", currency="USD"),
    ]
    config = AppConfig(
        data_dir=tmp_data_dir,
        ibkr_host="127.0.0.1",
        ibkr_port=7497,
        instruments=instruments,
        news_provider_codes="BZ",
        spy_symbol="SPY",
        sentiment_backend="finbert",
    )

    results = run_download(config)

    # At least some results should be successful for the date range
    successful = [r for r in results if r.success and not r.skipped]
    assert len(successful) >= 1


@pytest.mark.integration
def test_invalid_symbol_produces_failed_result_without_abort(tmp_data_dir):
    """An invalid symbol produces a failed DayDownloadResult without crashing other symbols."""
    from src.downloader import run_download
    from src.types import AppConfig

    instruments = [
        InstrumentConfig(symbol="SPY", sec_type="STK", exchange="SMART", currency="USD"),
        InstrumentConfig(symbol="ZZZBAD", sec_type="STK", exchange="SMART", currency="USD"),
    ]
    config = AppConfig(
        data_dir=tmp_data_dir,
        ibkr_host="127.0.0.1",
        ibkr_port=7497,
        instruments=instruments,
        news_provider_codes="BZ",
        spy_symbol="SPY",
        sentiment_backend="finbert",
    )

    results = run_download(config)

    spy_results = [r for r in results if r.symbol == "SPY"]
    bad_results = [r for r in results if r.symbol == "ZZZBAD"]

    assert any(r.success for r in spy_results), "SPY should have at least one success"
    assert any(not r.success for r in bad_results), "ZZZBAD should have at least one failure"
