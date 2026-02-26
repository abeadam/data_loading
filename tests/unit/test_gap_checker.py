"""Tests for src/gap_checker.py — pure function, no IBKR, no file I/O."""
from datetime import date



def make_bars(count: int, start_timestamp: int = 1704196200, interval: int = 5):
    """Create a consecutive sequence of bars with given interval (seconds)."""
    from src.types import Bar

    return [
        Bar(
            timestamp=start_timestamp + i * interval,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0,
        )
        for i in range(count)
    ]


class TestPerfectSequence:
    def test_4680_bars_no_gaps(self):
        from src.gap_checker import check_gaps
        from src.types import DailyBars

        bars = make_bars(4680)
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        report = check_gaps(daily)

        assert report.has_gaps is False
        assert report.gaps == []
        assert report.total_bars == 4680
        assert report.expected_bars == 4680
        assert report.bar_count_delta == 0

    def test_symbol_and_date_preserved(self):
        from src.gap_checker import check_gaps
        from src.types import DailyBars

        bars = make_bars(4680)
        daily = DailyBars(symbol="VIX", date=date(2024, 8, 1), bars=bars)
        report = check_gaps(daily)

        assert report.symbol == "VIX"
        assert report.date == date(2024, 8, 1)


class TestSingleGap:
    def test_one_10_second_gap_at_bar_100(self):
        from src.gap_checker import check_gaps
        from src.types import Bar, DailyBars

        bars = make_bars(4680)
        # Replace bar at index 100 — create a 10-second gap between bars 99 and 100
        bars_list = list(bars)
        base_ts = bars_list[99].timestamp
        bars_list[100] = Bar(
            timestamp=base_ts + 10,  # gap: 10 seconds instead of 5
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1000.0,
        )
        # Adjust remaining bars to keep consistent spacing after the gap
        for i in range(101, len(bars_list)):
            bars_list[i] = Bar(
                timestamp=bars_list[i].timestamp + 5,  # shift forward by 5 seconds
                open=100.0, high=101.0, low=99.0, close=100.5, volume=1000.0,
            )
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars_list)
        report = check_gaps(daily)

        assert report.has_gaps is True
        assert len(report.gaps) == 1
        gap = report.gaps[0]
        assert gap.start_timestamp == base_ts
        assert gap.end_timestamp == base_ts + 10
        assert gap.missing_seconds == 5   # end - start - 5 = 10 - 5 = 5
        assert gap.missing_bars == 1      # 5 // 5

    def test_gap_at_beginning(self):
        from src.gap_checker import check_gaps
        from src.types import Bar, DailyBars

        start = 1704196200
        bars = [
            Bar(timestamp=start, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
            Bar(timestamp=start + 15, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
            Bar(timestamp=start + 20, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
        ]
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        report = check_gaps(daily)

        assert report.has_gaps is True
        assert len(report.gaps) == 1
        assert report.gaps[0].missing_bars == 2  # (15 - 5) // 5 = 2


class TestMultipleGaps:
    def test_two_gaps(self):
        from src.gap_checker import check_gaps
        from src.types import DailyBars

        start = 1704196200
        # Segments: 100 bars, gap, 100 bars, gap, 4480 bars
        segment_a = make_bars(100, start_timestamp=start)
        gap1_start = segment_a[-1].timestamp
        segment_b_start = gap1_start + 15  # 10-second gap
        segment_b = make_bars(100, start_timestamp=segment_b_start)
        gap2_start = segment_b[-1].timestamp
        segment_c_start = gap2_start + 25  # 20-second gap
        segment_c = make_bars(4480, start_timestamp=segment_c_start)

        all_bars = segment_a + segment_b + segment_c
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=all_bars)
        report = check_gaps(daily)

        assert report.has_gaps is True
        assert len(report.gaps) == 2
        assert report.gaps[0].missing_bars == 2  # (15 - 5) // 5 = 2
        assert report.gaps[1].missing_bars == 4  # (25 - 5) // 5 = 4


class TestShortBarCount:
    def test_only_4000_bars_has_gaps(self):
        from src.gap_checker import check_gaps
        from src.types import DailyBars

        bars = make_bars(4000)
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        report = check_gaps(daily)

        assert report.has_gaps is True
        assert report.total_bars == 4000
        assert report.bar_count_delta == -680

    def test_bar_count_delta_negative_for_short_days(self):
        from src.gap_checker import check_gaps
        from src.types import DailyBars

        bars = make_bars(100)
        daily = DailyBars(symbol="VIX", date=date(2024, 1, 2), bars=bars)
        report = check_gaps(daily)

        assert report.bar_count_delta == 100 - 4680


class TestEmptyBars:
    def test_empty_bar_list_has_gaps_true(self):
        from src.gap_checker import check_gaps
        from src.types import DailyBars

        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=[])
        report = check_gaps(daily)

        assert report.has_gaps is True
        assert report.total_bars == 0
        assert report.gaps == []


class TestSortingBehavior:
    def test_out_of_order_bars_sorted_before_checking(self):
        from src.gap_checker import check_gaps
        from src.types import Bar, DailyBars

        start = 1704196200
        bars = [
            Bar(timestamp=start + 10, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
            Bar(timestamp=start, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
            Bar(timestamp=start + 5, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
        ]
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        report = check_gaps(daily)

        # 3 consecutive bars in sorted order → has_gaps only due to bar count
        assert report.gaps == []  # no timestamp gaps
        assert report.has_gaps is True  # bar count short
