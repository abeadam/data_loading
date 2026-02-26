"""Tests for src/file_writer.py — file I/O using tmp_data_dir fixture."""
import csv
from datetime import date
from pathlib import Path

import pytest


def make_daily_bars(symbol: str = "SPY", count: int = 3, start_ts: int = 1704196200):
    from src.types import Bar, DailyBars

    bars = [
        Bar(
            timestamp=start_ts + i * 5,
            open=476.0 + i * 0.01,
            high=477.0,
            low=475.0,
            close=476.5,
            volume=1000.0 + i,
        )
        for i in range(count)
    ]
    return DailyBars(symbol=symbol, date=date(2024, 1, 2), bars=bars)


class TestDayFilePath:
    def test_correct_path_format(self, tmp_data_dir):
        from src.file_writer import day_file_path

        path = day_file_path(tmp_data_dir, "SPY", date(2024, 1, 2))
        expected = tmp_data_dir / "bars" / "SPY" / "2024-01-02_SPY.csv"
        assert path == expected

    def test_symbol_is_uppercase_in_path(self, tmp_data_dir):
        from src.file_writer import day_file_path

        path = day_file_path(tmp_data_dir, "VIX", date(2024, 8, 1))
        assert "VIX" in str(path)
        assert "2024-08-01" in str(path)


class TestFileExists:
    def test_returns_false_when_not_exists(self, tmp_data_dir):
        from src.file_writer import file_exists

        assert file_exists(tmp_data_dir, "SPY", date(2024, 1, 2)) is False

    def test_returns_true_when_file_present(self, tmp_data_dir):
        from src.file_writer import day_file_path, file_exists

        path = day_file_path(tmp_data_dir, "SPY", date(2024, 1, 2))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

        assert file_exists(tmp_data_dir, "SPY", date(2024, 1, 2)) is True


class TestWriteBars:
    def test_creates_file_with_csv_header(self, tmp_data_dir):
        from src.file_writer import write_bars

        daily = make_daily_bars()
        write_bars(tmp_data_dir, daily)

        path = tmp_data_dir / "bars" / "SPY" / "2024-01-02_SPY.csv"
        assert path.exists()

        with open(path) as f:
            header = f.readline().strip()
        assert header == "timestamp,open,high,low,close,volume"

    def test_written_rows_match_bars(self, tmp_data_dir):
        from src.file_writer import write_bars

        daily = make_daily_bars(count=5)
        write_bars(tmp_data_dir, daily)

        path = tmp_data_dir / "bars" / "SPY" / "2024-01-02_SPY.csv"
        with open(path) as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 5
        assert int(rows[0]["timestamp"]) == 1704196200
        assert int(rows[4]["timestamp"]) == 1704196220

    def test_rows_ordered_ascending_by_timestamp(self, tmp_data_dir):
        from src.types import Bar, DailyBars
        from src.file_writer import write_bars

        # Create bars in reverse order to test sorting
        bars = [
            Bar(timestamp=1704196210, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
            Bar(timestamp=1704196200, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
            Bar(timestamp=1704196205, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0),
        ]
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        write_bars(tmp_data_dir, daily)

        path = tmp_data_dir / "bars" / "SPY" / "2024-01-02_SPY.csv"
        with open(path) as f:
            rows = list(csv.DictReader(f))
        timestamps = [int(r["timestamp"]) for r in rows]
        assert timestamps == sorted(timestamps)

    def test_creates_parent_directories(self, tmp_data_dir):
        from src.file_writer import write_bars

        # bars/ subdirectory inside tmp_data_dir already exists; SPY/ does not
        daily = make_daily_bars(symbol="NEWSY")
        write_bars(tmp_data_dir, daily)

        path = tmp_data_dir / "bars" / "NEWSY" / "2024-01-02_NEWSY.csv"
        assert path.exists()

    def test_raises_file_exists_error_if_file_exists(self, tmp_data_dir):
        from src.file_writer import write_bars

        daily = make_daily_bars()
        write_bars(tmp_data_dir, daily)

        with pytest.raises(FileExistsError):
            write_bars(tmp_data_dir, daily)

    def test_returns_path_to_written_file(self, tmp_data_dir):
        from src.file_writer import write_bars

        daily = make_daily_bars()
        result_path = write_bars(tmp_data_dir, daily)

        expected = tmp_data_dir / "bars" / "SPY" / "2024-01-02_SPY.csv"
        assert result_path == expected


class TestReadBars:
    def test_read_bars_returns_daily_bars(self, tmp_data_dir):
        from src.file_writer import read_bars, write_bars

        daily = make_daily_bars(count=10)
        write_bars(tmp_data_dir, daily)

        loaded = read_bars(tmp_data_dir, "SPY", date(2024, 1, 2))

        assert loaded.symbol == "SPY"
        assert loaded.date == date(2024, 1, 2)
        assert loaded.bar_count == 10

    def test_read_bars_values_match_written(self, tmp_data_dir):
        from src.file_writer import read_bars, write_bars
        from src.types import Bar, DailyBars

        bars = [Bar(timestamp=1704196200, open=476.23, high=476.25, low=476.20, close=476.22, volume=12450.0)]
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        write_bars(tmp_data_dir, daily)

        loaded = read_bars(tmp_data_dir, "SPY", date(2024, 1, 2))

        assert loaded.bars[0].timestamp == 1704196200
        assert abs(loaded.bars[0].open - 476.23) < 0.001

    def test_read_bars_raises_file_not_found_if_missing(self, tmp_data_dir):
        from src.file_writer import read_bars

        with pytest.raises(FileNotFoundError):
            read_bars(tmp_data_dir, "MISSING", date(2024, 1, 2))
