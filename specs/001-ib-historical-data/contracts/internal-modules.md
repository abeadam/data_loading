# Internal Module Contracts

**Feature**: 001-ib-historical-data
**Date**: 2026-02-26

One responsibility per module. No module imports another module's types —
all share `types.py` only.

---

## `src/types.py`

Defines all dataclasses. No logic. No imports from other `src/` modules.

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

@dataclass(frozen=True)
class InstrumentConfig:
    symbol: str
    sec_type: str    # "STK" | "IND" | "CONTFUT" | "FUT"
    exchange: str
    currency: str

@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    ibkr_host: str
    ibkr_port: int
    instruments: tuple[InstrumentConfig, ...]
    news_provider_codes: str      # e.g. "BZ"
    news_spy_symbol: str
    sentiment_backend: str        # "finbert" | "vader"

@dataclass(frozen=True)
class Bar:
    timestamp: int    # Unix epoch seconds (UTC)
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
    missing_seconds: int    # end - start - 5
    missing_bars: int       # missing_seconds // 5

@dataclass(frozen=True)
class GapReport:
    symbol: str
    date: date
    has_gaps: bool
    gaps: tuple[GapInterval, ...]
    total_bars: int
    expected_bars: int
    bar_count_delta: int    # total_bars - expected_bars

@dataclass(frozen=True)
class NewsItem:
    article_id: str
    provider_code: str
    timestamp: datetime
    headline: str
    symbol: str

@dataclass(frozen=True)
class DailySentiment:
    date: date
    article_count: int
    sentiment_score: float    # mean(positive - negative), range [-1.0, +1.0]
    positive_count: int
    negative_count: int
    neutral_count: int

@dataclass(frozen=True)
class DayDownloadResult:
    symbol: str
    date: date
    success: bool
    skipped: bool        # File already existed — not re-downloaded
    bars_saved: int
    file_path: Path | None
    error_message: str | None
```

---

## `src/config_loader.py`

**Responsibility**: Load and validate `config.yaml` → `AppConfig`.

```python
from pathlib import Path
from .types import AppConfig, InstrumentConfig

def load_config(config_path: Path) -> AppConfig:
    """
    Loads and validates the YAML config file.
    Raises FileNotFoundError if config_path does not exist.
    Raises ValueError with a descriptive message for any validation failure:
      - Missing required keys
      - Invalid sec_type values
      - Non-absolute data_dir
      - Unknown sentiment_backend
    Returns a fully validated AppConfig.
    Duplicate instrument symbols are silently deduplicated (first occurrence kept).
    """
```

---

## `src/ibkr_client.py`

**Responsibility**: IBKR connection lifecycle and all direct ibapi calls.
No other module imports from `ibapi` directly.

```python
import threading
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from datetime import date, datetime

class IBKRClient(EWrapper, EClient):
    """
    Wraps ibapi EWrapper + EClient. Handles connection, threading,
    request dispatch, and result collection.

    All public methods block until the corresponding IBKR callback fires
    or a timeout expires. Callers do not manage threading.
    """

def connect_to_ibkr(host: str, port: int, client_ids: list[int] = [1, 2, 3, 4, 5]) -> IBKRClient:
    """
    Attempts connection with each client_id in order.
    Returns a connected IBKRClient on success.
    Raises ConnectionError if all client IDs fail.
    """

def disconnect(client: IBKRClient) -> None:
    """Cleanly disconnects and stops the API thread."""

def fetch_historical_bars(
    client: IBKRClient,
    contract: Contract,
    end_datetime: str,        # IBKR format: "YYYYMMDD-HH:MM:SS" (UTC)
    duration_str: str,        # e.g. "1 D", "24000 S"
    bar_size: str = "5 secs",
    what_to_show: str = "TRADES",
    use_rth: int = 0,
) -> list[dict]:
    """
    Requests historical bars for a contract. Blocks until historicalDataEnd fires.
    Returns list of raw bar dicts: {date, open, high, low, close, volume}.
    Returns empty list if no data available (does not raise for missing data).
    Raises ConnectionError on connection failure after retry.
    Respects IBKR pacing: sleeps 2 seconds after each request.
    Timeout: 1 minute per request (10 minutes for SPX).
    """

def resolve_con_id(client: IBKRClient, contract: Contract) -> int:
    """
    Fetches the conId for a contract via reqContractDetails.
    Returns the integer conId.
    Raises ValueError if the contract is ambiguous or not found.
    """

def fetch_historical_news(
    client: IBKRClient,
    con_id: int,
    provider_codes: str,
    start_datetime: str,    # "YYYY-MM-DD HH:MM:SS.0" UTC
    end_datetime: str,
    total_results: int = 300,
) -> list[dict]:
    """
    Requests historical news headlines for a conId.
    Returns list of dicts: {time, provider_code, article_id, headline}.
    Returns empty list if no news is available.
    Raises PermissionError if no news subscription is active (error code 10276).
    Pacing: obeys IBKR's 60-requests/10-minutes limit.
    """
```

---

## `src/contract_resolver.py`

**Responsibility**: Build `ibapi.Contract` objects from `InstrumentConfig`.
Handles the ES/VXM expiry resolution and VIX special-casing from reference code.

```python
from ibapi.contract import Contract
from datetime import date
from .types import InstrumentConfig

def resolve_contract(instrument: InstrumentConfig, target_date: date) -> Contract:
    """
    Builds an ibapi Contract for the given instrument and date.

    Special cases (matching reference code behavior):
    - VIX: overrides sec_type to "IND", exchange to "CBOE"
    - ES with CONTFUT: sets sec_type="FUT", lastTradeDateOrContractMonth to the
      active quarterly expiry (Mar/Jun/Sep/Dec, 3rd Friday roll), includeExpired=True
    - VXM with CONTFUT: sets sec_type="FUT", lastTradeDateOrContractMonth to the
      active monthly expiry (3rd Wednesday roll), includeExpired=True

    Returns a fully configured ibapi Contract ready for reqHistoricalData.
    """

def get_active_es_contract_month(target_date: date) -> str:
    """
    Returns the YYYYMM string for the ES futures contract active on target_date.
    ES expires quarterly (Mar/Jun/Sep/Dec) on the 3rd Friday.
    """

def get_active_vxm_contract_month(target_date: date) -> str:
    """
    Returns the YYYYMM string for the VXM futures contract active on target_date.
    VXM (VIX futures) expires monthly on the 3rd Wednesday.
    """
```

---

## `src/bar_downloader.py`

**Responsibility**: Download one day of 5-second bars for one instrument.
Handles SPX duration override and VIX/SPX timestamp filtering from reference code.

```python
from datetime import date
from .types import InstrumentConfig, DailyBars
from .ibkr_client import IBKRClient

REGULAR_SESSION_BAR_COUNT: int = 4680  # 6.5 hours × 720 bars/hour

def download_day(
    client: IBKRClient,
    instrument: InstrumentConfig,
    target_date: date,
    spy_bars: DailyBars | None = None,
) -> DailyBars | None:
    """
    Downloads 5-second bars for one instrument on one trading date.

    - Resolves the ibapi Contract via contract_resolver.
    - Sets end_datetime to 4:00 PM ET converted to UTC for target_date.
    - Uses duration "1 D" for most instruments; "24000 S" for SPX.
    - For VIX and SPX: filters returned bars to match SPY's timestamp range
      if spy_bars is provided, or trims to expected RTH count otherwise.
      (Matches reference code behavior to handle GTH data bleed.)

    Returns DailyBars if data was retrieved, None if no data available.
    Does NOT write to disk — that is file_writer's responsibility.
    """

def compute_end_datetime(target_date: date) -> str:
    """
    Returns the IBKR-format end datetime string for 4:00 PM ET on target_date,
    correctly converted to UTC with DST handling via zoneinfo.
    Format: "YYYYMMDD-HH:MM:SS"
    """
```

---

## `src/gap_checker.py`

**Responsibility**: Validate bar sequence; detect gaps. Pure function — no I/O, no IBKR.

```python
from .types import DailyBars, GapReport, GapInterval

EXPECTED_BAR_INTERVAL_SECONDS: int = 5
EXPECTED_REGULAR_SESSION_BARS: int = 4680

def check_gaps(bars: DailyBars) -> GapReport:
    """
    Validates the bar sequence for one instrument-day.

    Algorithm:
    1. Sort bars ascending by timestamp.
    2. For each consecutive pair (b_i, b_{i+1}):
       - gap = b_{i+1}.timestamp - b_i.timestamp - 5
       - If gap > 0, record a GapInterval.
    3. Compare total_bars to EXPECTED_REGULAR_SESSION_BARS.
    4. has_gaps = any gap found OR total_bars < EXPECTED_REGULAR_SESSION_BARS.

    Returns GapReport. Pure function — takes DailyBars, returns GapReport.
    No file reads, no IBKR calls.
    """
```

---

## `src/file_writer.py`

**Responsibility**: Write per-day CSV files and check file existence.
MUST NEVER overwrite an existing file.

```python
from pathlib import Path
from datetime import date
from .types import DailyBars

CSV_HEADER: str = "timestamp,open,high,low,close,volume"

def day_file_path(data_dir: Path, symbol: str, target_date: date) -> Path:
    """
    Returns the canonical path for a (symbol, date) bar file.
    Format: {data_dir}/bars/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}.csv
    Does not create the file or its parent directories.
    """

def file_exists(data_dir: Path, symbol: str, target_date: date) -> bool:
    """Returns True if the day file already exists on disk."""

def write_bars(data_dir: Path, bars: DailyBars) -> Path:
    """
    Writes bars to the canonical path.
    Creates parent directories if they do not exist.
    RAISES FileExistsError if the file already exists — callers MUST check
    file_exists() before calling write_bars().
    Writes header row followed by one CSV row per bar, ascending timestamp.
    Returns the path written to.
    """

def read_bars(data_dir: Path, symbol: str, target_date: date) -> DailyBars:
    """
    Reads a day file from disk and returns DailyBars.
    Raises FileNotFoundError if the file does not exist.
    """
```

---

## `src/news_downloader.py`

**Responsibility**: Download news headlines from IBKR for a given date range.

```python
from datetime import date
from .types import InstrumentConfig, NewsItem
from .ibkr_client import IBKRClient

def download_news_for_date(
    client: IBKRClient,
    symbol: str,
    con_id: int,
    provider_codes: str,
    target_date: date,
) -> list[NewsItem]:
    """
    Downloads all available news headlines for `symbol` on `target_date`.
    Fetches for window: midnight UTC on target_date to midnight UTC on target_date + 1.
    Returns list of NewsItem. Returns empty list if no news is available.
    Raises PermissionError if no news subscription is active.
    Does NOT fetch full article bodies (headlines only).
    """

def resolve_spy_con_id(client: IBKRClient, spy_instrument: InstrumentConfig) -> int:
    """
    Resolves and returns the IBKR conId for the SPY instrument.
    Called once at startup; result is reused for all news requests.
    """
```

---

## `src/sentiment_analyzer.py`

**Responsibility**: Compute sentiment scores from news headlines. No I/O, no IBKR.

```python
from datetime import date
from .types import NewsItem, DailySentiment

def load_model(backend: str) -> object:
    """
    Loads and returns the sentiment model.
    backend: "finbert" loads ProsusAI/finbert via transformers pipeline.
    backend: "vader" loads SentimentIntensityAnalyzer from vaderSentiment.
    Raises ValueError for unknown backend.
    Model is loaded once and reused across calls.
    """

def score_headlines(model: object, headlines: list[str], backend: str) -> list[float]:
    """
    Returns a list of per-headline scores in [-1.0, +1.0].
    For finbert: score = positive_prob - negative_prob.
    For vader: score = compound value directly.
    """

def aggregate_daily_sentiment(
    model: object,
    backend: str,
    news_items: list[NewsItem],
    target_date: date,
) -> DailySentiment:
    """
    Scores all headlines and aggregates to a single DailySentiment.
    Returns a DailySentiment with sentiment_score = mean of per-headline scores.
    Returns DailySentiment with article_count=0 and sentiment_score=0.0 if
    news_items is empty.
    """
```

---

## `src/downloader.py`

**Responsibility**: Orchestrate the full bar download pipeline from config to files.

```python
from pathlib import Path
from .types import AppConfig, DayDownloadResult

IBKR_MAX_LOOKBACK_DAYS: int = 180

def run_download(config: AppConfig) -> list[DayDownloadResult]:
    """
    Main orchestration function.

    1. Connect to IBKR.
    2. Compute date range: today - IBKR_MAX_LOOKBACK_DAYS to yesterday.
    3. For each date in range (weekdays, non-holidays):
       For each instrument in config.instruments:
         a. Check file existence → skip if exists (log "already have {date} {symbol}")
         b. Download via bar_downloader.download_day()
         c. If data returned: run gap_checker.check_gaps(); log gaps if any
         d. Write via file_writer.write_bars()
         e. Record DayDownloadResult
    4. Disconnect.
    5. Return all results.

    Never raises on per-symbol/per-date failures — records in DayDownloadResult.
    Raises ConnectionError if IBKR connection cannot be established.
    """

def is_market_holiday(target_date: date) -> bool:
    """
    Returns True if target_date is a US equity market holiday.
    Covers: New Year's Day, MLK Day, Presidents' Day, Good Friday, Memorial Day,
    Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas.
    (Good Friday added vs reference code — it is an NYSE holiday.)
    """
```

---

## `src/news_pipeline.py`

**Responsibility**: Orchestrate news download and sentiment for SPY-matched dates.

```python
from .types import AppConfig

def run_news_pipeline(config: AppConfig) -> None:
    """
    1. Scan {data_dir}/bars/{spy_symbol}/ for existing day files → get date list.
    2. Filter to dates without an existing {data_dir}/news/YYYY-MM-DD_sentiment.csv.
    3. Connect to IBKR.
    4. Resolve SPY conId once via news_downloader.resolve_spy_con_id().
    5. Load sentiment model once via sentiment_analyzer.load_model().
    6. For each date:
       a. Download headlines via news_downloader.download_news_for_date()
       b. Score via sentiment_analyzer.aggregate_daily_sentiment()
       c. Save articles JSON and sentiment CSV (via file_writer equivalents)
    7. Disconnect.

    Logs a warning and continues if news is unavailable for a date.
    Does not raise on per-date failures.
    """
```
