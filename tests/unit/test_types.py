"""Tests for src/types.py — all dataclasses, derived properties, and computed fields."""
from datetime import date, datetime
from pathlib import Path

import pytest


class TestBar:
    def test_fields_accessible(self):
        from src.types import Bar

        bar = Bar(timestamp=1704196200, open=476.23, high=476.25, low=476.20, close=476.22, volume=12450.0)
        assert bar.timestamp == 1704196200
        assert bar.open == 476.23
        assert bar.volume == 12450.0

    def test_frozen(self):
        from src.types import Bar

        bar = Bar(timestamp=1, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0)
        with pytest.raises(Exception):
            bar.timestamp = 999  # type: ignore[misc]


class TestDailyBars:
    def _make_bars(self, count: int):
        from src.types import Bar

        return [
            Bar(timestamp=1704196200 + i * 5, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0)
            for i in range(count)
        ]

    def test_bar_count_property_returns_len(self):
        from src.types import DailyBars

        bars = self._make_bars(10)
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        assert daily.bar_count == 10

    def test_bar_count_empty(self):
        from src.types import DailyBars

        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=[])
        assert daily.bar_count == 0

    def test_bar_count_matches_len_always(self):
        from src.types import DailyBars

        bars = self._make_bars(4680)
        daily = DailyBars(symbol="SPY", date=date(2024, 1, 2), bars=bars)
        assert daily.bar_count == len(daily.bars)


class TestGapInterval:
    def test_missing_bars_derived_from_missing_seconds(self):
        from src.types import GapInterval

        gap = GapInterval(
            start_timestamp=1704196200,
            end_timestamp=1704196210,
            missing_seconds=5,
            missing_bars=1,
        )
        assert gap.missing_bars == gap.missing_seconds // 5

    def test_missing_bars_multiple(self):
        from src.types import GapInterval

        gap = GapInterval(
            start_timestamp=1704196200,
            end_timestamp=1704196260,
            missing_seconds=55,
            missing_bars=11,
        )
        assert gap.missing_bars == 11
        assert gap.missing_seconds // 5 == 11


class TestGapReport:
    def test_fields(self):
        from src.types import GapReport

        report = GapReport(
            symbol="SPY",
            date=date(2024, 1, 2),
            has_gaps=False,
            gaps=[],
            total_bars=4680,
            expected_bars=4680,
            bar_count_delta=0,
        )
        assert report.has_gaps is False
        assert report.bar_count_delta == 0

    def test_bar_count_delta_negative(self):
        from src.types import GapReport

        report = GapReport(
            symbol="SPY",
            date=date(2024, 1, 2),
            has_gaps=True,
            gaps=[],
            total_bars=4000,
            expected_bars=4680,
            bar_count_delta=-680,
        )
        assert report.bar_count_delta == -680


class TestSentimentTestResult:
    def test_passed_true_when_at_or_above_threshold(self):
        from src.types import SentimentTestResult

        result = SentimentTestResult(
            items_tested=100,
            items_aligned=80,
            alignment_pct=80.0,
            passed=True,
            details=[],
        )
        assert result.passed is True

    def test_passed_false_when_below_threshold(self):
        from src.types import SentimentTestResult

        result = SentimentTestResult(
            items_tested=100,
            items_aligned=79,
            alignment_pct=79.0,
            passed=False,
            details=[],
        )
        assert result.passed is False


class TestDayDownloadResult:
    def test_success_fields(self):
        from src.types import DayDownloadResult

        result = DayDownloadResult(
            symbol="SPY",
            date=date(2024, 1, 2),
            success=True,
            skipped=False,
            bars_saved=4680,
            file_path=Path("/data/bars/SPY/2024-01-02_SPY.csv"),
            error_message=None,
        )
        assert result.success is True
        assert result.bars_saved == 4680
        assert result.error_message is None

    def test_failure_fields(self):
        from src.types import DayDownloadResult

        result = DayDownloadResult(
            symbol="ES",
            date=date(2024, 1, 2),
            success=False,
            skipped=False,
            bars_saved=0,
            file_path=None,
            error_message="Connection timeout",
        )
        assert result.success is False
        assert result.file_path is None
        assert result.error_message == "Connection timeout"


class TestNewsItem:
    def test_fields(self):
        from src.types import NewsItem

        item = NewsItem(
            article_id="BZ$abc123",
            provider_code="BZ",
            timestamp=datetime(2024, 1, 2, 10, 32, 0),
            headline="SPY outperforms expectations",
            body=None,
            symbol="SPY",
        )
        assert item.article_id == "BZ$abc123"
        assert item.body is None


class TestDailySentiment:
    def test_fields(self):
        from src.types import DailySentiment

        ds = DailySentiment(
            date=date(2024, 1, 2),
            article_count=12,
            sentiment_score=0.42,
            positive_count=7,
            negative_count=2,
            neutral_count=3,
        )
        assert ds.sentiment_score == 0.42
        assert ds.positive_count + ds.negative_count + ds.neutral_count == ds.article_count


class TestInstrumentConfig:
    def test_fields(self):
        from src.types import InstrumentConfig

        inst = InstrumentConfig(symbol="SPY", sec_type="STK", exchange="SMART", currency="USD")
        assert inst.symbol == "SPY"
        assert inst.sec_type == "STK"


class TestAppConfig:
    def test_fields(self):
        from src.types import AppConfig, InstrumentConfig

        instruments = [InstrumentConfig(symbol="SPY", sec_type="STK", exchange="SMART", currency="USD")]
        cfg = AppConfig(
            data_dir=Path("/data"),
            ibkr_host="127.0.0.1",
            ibkr_port=7497,
            instruments=instruments,
            news_provider_codes="BZ",
            spy_symbol="SPY",
            sentiment_backend="finbert",
        )
        assert cfg.ibkr_port == 7497
        assert len(cfg.instruments) == 1
