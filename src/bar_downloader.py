"""Download 5-second OHLCV bars for a single instrument and date from IBKR."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.contract_resolver import resolve_contract
from src.ibkr_client import IBKRClient, fetch_historical_bars
from src.types import Bar, DailyBars, InstrumentConfig

REGULAR_SESSION_BAR_COUNT = 4680
ET_TIMEZONE = ZoneInfo("America/New_York")

# SPX requires a wider time window to reliably capture the full RTH session.
SPX_DURATION_STR = "24000 S"
DEFAULT_DURATION_STR = "1 D"

# Symbols whose bars must be filtered to the regular trading hours window.
SYMBOLS_REQUIRING_RTH_FILTER = {"VIX", "SPX"}


def compute_end_datetime(target_date: date) -> str:
    """
    Convert 4:00 PM ET on target_date to UTC, formatted as IBKR's endDateTime string.

    Example: 2024-01-02 → "20240102-21:00:00" (EST) or "20240102-20:00:00" (EDT)
    """
    et_4pm = datetime(target_date.year, target_date.month, target_date.day, 16, 0, 0, tzinfo=ET_TIMEZONE)
    utc_time = et_4pm.astimezone(timezone.utc)
    return utc_time.strftime("%Y%m%d-%H:%M:%S")


def download_day(
    client: IBKRClient,
    instrument: InstrumentConfig,
    target_date: date,
    spy_bars: DailyBars | None = None,
) -> DailyBars | None:
    """
    Download 5-second bars for one instrument on one trading day.

    Returns DailyBars on success, or None if no bars were returned by IBKR.

    VIX and SPX bars are filtered to the RTH timestamp range using spy_bars if available,
    or by center-trimming to REGULAR_SESSION_BAR_COUNT otherwise.
    """
    contract = resolve_contract(instrument, target_date)
    end_datetime = compute_end_datetime(target_date)
    duration_str = SPX_DURATION_STR if instrument.symbol == "SPX" else DEFAULT_DURATION_STR

    raw_bars = fetch_historical_bars(
        client=client,
        contract=contract,
        end_datetime=end_datetime,
        duration_str=duration_str,
    )

    if not raw_bars:
        return None

    bars = [
        Bar(
            timestamp=int(b["timestamp"]),
            open=float(b["open"]),
            high=float(b["high"]),
            low=float(b["low"]),
            close=float(b["close"]),
            volume=float(b["volume"]),
        )
        for b in raw_bars
    ]

    if instrument.symbol in SYMBOLS_REQUIRING_RTH_FILTER:
        bars = _filter_to_rth(bars, spy_bars)

    return DailyBars(symbol=instrument.symbol, date=target_date, bars=bars)


def _filter_to_rth(bars: list[Bar], spy_bars: DailyBars | None) -> list[Bar]:
    """
    Filter bars to the regular trading hours window.

    If spy_bars is available, use its first/last timestamp as the range.
    Otherwise, center-trim to REGULAR_SESSION_BAR_COUNT bars.
    """
    sorted_bars = sorted(bars, key=lambda b: b.timestamp)

    if spy_bars and spy_bars.bars:
        spy_timestamps = [b.timestamp for b in spy_bars.bars]
        spy_start = min(spy_timestamps)
        spy_end = max(spy_timestamps)
        return [b for b in sorted_bars if spy_start <= b.timestamp <= spy_end]

    # Fallback: center-trim to expected session length
    if len(sorted_bars) > REGULAR_SESSION_BAR_COUNT:
        start_idx = (len(sorted_bars) - REGULAR_SESSION_BAR_COUNT) // 2
        return sorted_bars[start_idx: start_idx + REGULAR_SESSION_BAR_COUNT]

    return sorted_bars
