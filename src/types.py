"""All dataclasses for the data loading pipeline. No logic, no imports from other src/ modules."""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class InstrumentConfig:
    symbol: str
    sec_type: str
    exchange: str
    currency: str


@dataclass
class AppConfig:
    data_dir: Path
    ibkr_host: str
    ibkr_port: int
    instruments: list[InstrumentConfig]
    news_provider_codes: str
    spy_symbol: str
    sentiment_backend: str
    news_ibkr_client_id: int | None = None  # None → try default ID pool


@dataclass(frozen=True)
class Bar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class DailyBars:
    symbol: str
    date: date
    bars: list[Bar]

    @property
    def bar_count(self) -> int:
        return len(self.bars)


@dataclass(frozen=True)
class GapInterval:
    start_timestamp: int
    end_timestamp: int
    missing_seconds: int
    missing_bars: int


@dataclass
class GapReport:
    symbol: str
    date: date
    has_gaps: bool
    gaps: list[GapInterval]
    total_bars: int
    expected_bars: int
    bar_count_delta: int


@dataclass
class NewsItem:
    article_id: str
    provider_code: str
    timestamp: datetime
    headline: str
    body: str | None
    symbol: str


@dataclass
class DailySentiment:
    date: date
    article_count: int
    sentiment_score: float
    positive_count: int
    negative_count: int
    neutral_count: int


@dataclass
class NewsItemAlignment:
    article_id: str
    timestamp: datetime
    headline: str
    sentiment_score: float
    spy_bar_open: float
    spy_bar_close_30s: float
    price_change: float
    aligned: bool


@dataclass
class SentimentTestResult:
    items_tested: int
    items_aligned: int
    alignment_pct: float
    passed: bool
    details: list[NewsItemAlignment]


@dataclass
class DayDownloadResult:
    symbol: str
    date: date
    success: bool
    skipped: bool
    bars_saved: int
    file_path: Path | None
    error_message: str | None
