"""Validate bar sequence for a single trading day — pure function, no I/O."""
from src.types import DailyBars, GapInterval, GapReport

EXPECTED_BAR_INTERVAL_SECONDS = 5
EXPECTED_REGULAR_SESSION_BARS = 4680  # Equities/indices: 6.5 RTH hours × 720 bars/hour


def check_gaps(bars: DailyBars, expected_bars: int | None = EXPECTED_REGULAR_SESSION_BARS) -> GapReport:
    """
    Detect gaps in a sorted 5-second bar sequence.

    A gap is any consecutive pair where the time difference exceeds 5 seconds.

    expected_bars: expected bar count for this instrument session.
        - EXPECTED_REGULAR_SESSION_BARS (4680) for equities and indices.
        - None for futures (ES, VXM) — bar-count check is skipped since they
          trade ~24 hours and the count varies by session.
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

    if expected_bars is None:
        # Futures: only flag timestamp gaps, not bar count shortfalls
        has_gaps = bool(gaps)
        effective_expected = total_bars  # delta will always be 0
    else:
        has_gaps = bool(gaps) or total_bars < expected_bars
        effective_expected = expected_bars

    return GapReport(
        symbol=bars.symbol,
        date=bars.date,
        has_gaps=has_gaps,
        gaps=gaps,
        total_bars=total_bars,
        expected_bars=effective_expected,
        bar_count_delta=total_bars - effective_expected,
    )
