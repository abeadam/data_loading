"""Resolve SPY conId and download news headlines from IBKR for a date range."""
from datetime import date, datetime, timedelta, timezone

from ibapi.contract import Contract

from src.ibkr_client import IBKRClient, fetch_historical_news, resolve_con_id
from src.types import InstrumentConfig, NewsItem

# IBKR reqHistoricalNews requires dashes and a .0 suffix: "YYYY-MM-DD HH:MM:SS.0"
# (not the same as reqHistoricalData which uses "YYYYMMDD HH:MM:SS")
IBKR_NEWS_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
IBKR_NEWS_TIME_FORMAT = "%Y%m%d%H:%M:%S"


def resolve_spy_con_id(client: IBKRClient, spy_instrument: InstrumentConfig) -> int:
    """
    Resolve the IBKR conId for the SPY instrument via reqContractDetails.

    The conId is required for reqHistoricalNews — do not hardcode it.
    """
    contract = Contract()
    contract.symbol = spy_instrument.symbol
    contract.secType = spy_instrument.sec_type
    contract.exchange = spy_instrument.exchange
    contract.currency = spy_instrument.currency

    return resolve_con_id(client, contract)


def download_news_for_date(
    client: IBKRClient,
    symbol: str,
    con_id: int,
    provider_codes: str,
    target_date: date,
) -> list[NewsItem]:
    """
    Download all news headlines for a symbol from midnight to midnight UTC on target_date.

    Returns an empty list if no news is available.
    Raises PermissionError if error code 10276 is returned (no news subscription).
    """
    start_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    next_day = target_date + timedelta(days=1)
    end_dt = datetime(next_day.year, next_day.month, next_day.day, tzinfo=timezone.utc)

    # IBKR reqHistoricalNews date format: "YYYY-MM-DD HH:MM:SS.0"
    start_str = start_dt.strftime(IBKR_NEWS_DATETIME_FORMAT)
    end_str = end_dt.strftime(IBKR_NEWS_DATETIME_FORMAT)

    raw_items = fetch_historical_news(
        client=client,
        con_id=con_id,
        provider_codes=provider_codes,
        start_datetime=start_str,
        end_datetime=end_str,
    )

    return [_parse_news_item(item, symbol) for item in raw_items]


def _parse_news_item(raw: dict, symbol: str) -> NewsItem:
    """Parse a raw news dict from IBKR into a NewsItem."""
    # IBKR time format: "20240102 10:32:00" or "20240102 10:32:00.0"
    time_str = raw["time"].split(".")[0].strip()
    try:
        timestamp = datetime.strptime(time_str, "%Y%m%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        # Fallback: try alternate format
        timestamp = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    return NewsItem(
        article_id=raw["article_id"],
        provider_code=raw["provider_code"],
        timestamp=timestamp,
        headline=raw["headline"],
        body=None,
        symbol=symbol,
    )
