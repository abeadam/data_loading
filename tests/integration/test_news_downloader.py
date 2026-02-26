"""Integration tests for news download — require live TWS with Benzinga subscription."""
from datetime import date, timedelta

import pytest

from src.types import InstrumentConfig

SPY_INSTRUMENT = InstrumentConfig(symbol="SPY", sec_type="STK", exchange="SMART", currency="USD")


@pytest.mark.integration
def test_resolve_spy_con_id():
    """Verify SPY conId resolves to a non-zero integer."""
    from src.ibkr_client import connect_to_ibkr, disconnect
    from src.news_downloader import resolve_spy_con_id

    client = connect_to_ibkr("127.0.0.1", 7497)
    try:
        con_id = resolve_spy_con_id(client, SPY_INSTRUMENT)
    finally:
        disconnect(client)

    assert isinstance(con_id, int)
    assert con_id > 0
    print(f"SPY conId: {con_id}")


@pytest.mark.integration
def test_download_news_for_recent_date():
    """Download news for a recent trading date and verify structure."""
    from src.ibkr_client import connect_to_ibkr, disconnect
    from src.news_downloader import download_news_for_date, resolve_spy_con_id

    # Use a date 7 days ago (well within lookback, likely a trading day)
    target_date = date.today() - timedelta(days=7)
    if target_date.weekday() >= 5:
        target_date -= timedelta(days=target_date.weekday() - 4)

    client = connect_to_ibkr("127.0.0.1", 7497)
    try:
        con_id = resolve_spy_con_id(client, SPY_INSTRUMENT)
        news_items = download_news_for_date(
            client=client,
            symbol="SPY",
            con_id=con_id,
            provider_codes="BZ",
            target_date=target_date,
        )
    finally:
        disconnect(client)

    print(f"News for SPY on {target_date}: {len(news_items)} items")
    for item in news_items[:3]:
        print(f"  [{item.provider_code}] {item.timestamp} — {item.headline[:60]}")

    # Verify structure of each item
    for item in news_items:
        assert item.article_id
        assert item.headline
        assert item.symbol == "SPY"
        assert item.timestamp is not None
