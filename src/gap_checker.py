"""Validate bar sequence for a single trading day — pure function, no I/O."""
from src.types import DailyBars, GapInterval, GapReport

EXPECTED_BAR_INTERVAL_SECONDS = 5
EXPECTED_REGULAR_SESSION_BARS = 4680


def check_gaps(bars: DailyBars) -> GapReport:
    """
    Detect gaps in a sorted 5-second bar sequence.

    A gap is any consecutive pair where the time difference exceeds 5 seconds.
    The report also flags days with fewer bars than the expected 4,680.
    """
    sorted_bars = sorted(bars.bars, key=lambda b: b.timestamp)
    total_bars = len(sorted_bars)
    gaps: list[GapInterval] = []

    for i in range(len(sorted_bars) - 1):
        diff = sorted_bars[i + 1].timestamp - sorted_bars[i].timestamp
        if diff > EXPECTED_BAR_INTERVAL_SECONDS:
            missing_seconds = diff - EXPECTED_BAR_INTERVAL_SECONDS
            gaps.append(GapInterval(
                start_timestamp=sorted_bars[i].timestamp,
                end_timestamp=sorted_bars[i + 1].timestamp,
                missing_seconds=missing_seconds,
                missing_bars=missing_seconds // EXPECTED_BAR_INTERVAL_SECONDS,
            ))

    has_gaps = bool(gaps) or total_bars < EXPECTED_REGULAR_SESSION_BARS

    return GapReport(
        symbol=bars.symbol,
        date=bars.date,
        has_gaps=has_gaps,
        gaps=gaps,
        total_bars=total_bars,
        expected_bars=EXPECTED_REGULAR_SESSION_BARS,
        bar_count_delta=total_bars - EXPECTED_REGULAR_SESSION_BARS,
    )
