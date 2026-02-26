# Research: Historical Market Data + News Sentiment from Interactive Brokers

**Feature**: 001-ib-historical-data
**Date**: 2026-02-26
**Status**: Complete

Reference code studied: `/Users/abeadam/dev/interactive-broker-python/Updated Stats/download_daily.py`

---

## Decision 1: IBKR Python Library

**Decision**: `ibapi` (IBKR's official Python API — raw `EWrapper`/`EClient` pattern)

**Rationale**:
The reference code uses `ibapi` directly and demonstrates working patterns for all
the required operations: connection management, historical bar requests, futures contract
resolution, and client ID rotation. The user explicitly pointed to this code as the
reference. The sequential day-by-day download approach does not benefit from the async
concurrency model that `ib-async` provides. Adopting `ibapi` directly means zero
translation from reference patterns.

The reference code reveals several important quirks that the new implementation must
reproduce faithfully:
- **VIX** must use `secType="IND"` on `CBOE`, not `CONTFUT`/`CFE` (avoids ambiguity error)
- **ES** and **VXM** must use `secType="FUT"` with `lastTradeDateOrContractMonth` set to
  the active expiry for the target date (not `CONTFUT`, which fails for historical dates)
- `includeExpired=True` must be set for expired futures contracts
- `formatDate=2` (epoch timestamps) is the correct format for 5-second bars
- `useRTH=0` is used to include pre/post market data

**Pacing**: `ibapi` requires manual pacing. The reference uses a 2-second sleep between
requests and 1-second sleep between days. This will be encapsulated in `ibkr_client.py`.

**Alternatives considered**:
- `ib-async`: Cleaner API, pandas-native, maintained fork of ib_insync. Appropriate for
  async/concurrent workloads. Rejected because (1) reference code uses ibapi, (2) the
  sequential download pattern gains nothing from async, (3) adds a dependency translation
  layer with no practical benefit here.

---

## Decision 2: Bar Size and Historical Depth

**Decision**: Fixed `"5 secs"` bars. Maximum lookback ≈ 6 months (180 calendar days).

**Rationale**:
The user requires 5-second bars exclusively — this is not configurable. The reference
code confirms this: `self.barSizeSetting = '5 secs'`.

IBKR limits 5-second historical bar requests to approximately 6 months of history.
The reference code corroborates this: `start_date = end_date - timedelta(days=180)`.

This creates a critical data preservation constraint: any day file written to disk
cannot be re-downloaded after 6 months have passed. The system MUST check for
existing files before downloading and MUST NEVER overwrite existing files.

**Download strategy**: On each run, compute `earliest_date = today - 180 days`. Walk
forward from `earliest_date` to `yesterday`, skipping:
1. Weekends
2. Known US market holidays
3. Dates where the per-day file already exists on disk

---

## Decision 3: File Format and Organization

**Decision**: CSV files, one per (symbol, date). Named `YYYY-MM-DD_SYMBOL.csv`.
Stored under `{data_dir}/bars/{SYMBOL}/`.

**Rationale**:
The reference code uses this exact naming convention (`YYYY-MM-DD_symbol.txt`). CSV
is human-readable, trivially inspectable, and requires no dependencies to write.

For 5-second bars, a single file is ~280 KB per trading day per symbol (4,680 rows ×
~60 bytes). 180 days × 15 symbols ≈ 750 MB total — manageable flat files.

Parquet was considered and rejected for this use case: the files are too small for
columnar compression to be meaningful, and the user's workflow centers on per-day
inspection and safety, not analytical query performance.

**Directory layout**:
```
/Users/abeadam/dev/data_loader/data/
├── bars/
│   ├── SPY/
│   │   ├── 2024-08-01_SPY.csv
│   │   └── ...
│   ├── ES/
│   └── VIX/
└── news/
    ├── 2024-08-01_articles.json
    ├── 2024-08-01_sentiment.csv
    └── ...
```

This directory is OUTSIDE the git repo (`data_loading/` is the repo root; `data/` is
a sibling directory). No `.gitignore` entry required.

**File existence = do not re-download**: The existence check is the safety gate that
preserves data beyond the 6-month IBKR lookback window.

---

## Decision 4: Instrument Configuration

**Decision**: YAML config file at `src/config.yaml`. Instruments grouped by type.

**Rationale**:
YAML is human-readable, supports comments, handles lists natively, and is widely
supported by `PyYAML` (no additional dependencies beyond the existing Python ecosystem).

The reference code hardcodes instruments in a dict — this violates the principle of
making instrument lists maintainable without code changes.

**Config schema**:
```yaml
data_dir: /Users/abeadam/dev/data_loader/data
ibkr_host: "127.0.0.1"
ibkr_port: 7497

instruments:
  - symbol: SPY
    sec_type: STK
    exchange: SMART
    currency: USD
  - symbol: SPX
    sec_type: IND
    exchange: CBOE
    currency: USD
  - symbol: VIX
    sec_type: IND
    exchange: CBOE
    currency: USD
  - symbol: ES
    sec_type: CONTFUT        # resolved to FUT + contract month at runtime
    exchange: CME
    currency: USD
  - symbol: VXM
    sec_type: CONTFUT        # resolved to FUT + contract month at runtime
    exchange: CFE
    currency: USD

news:
  provider_codes: "BZ"      # Benzinga; update per account subscriptions
  spy_symbol: SPY            # Symbol whose available dates drive news download
```

---

## Decision 5: Gap Checking Algorithm

**Decision**: After writing each day's file, compare expected vs actual timestamps.
A gap is any consecutive pair of bars where the time difference exceeds 5 seconds
during regular trading hours (9:30 AM – 4:00 PM ET).

**Rationale**:
For 5-second bars during regular trading hours (RTH), the expected interval between
consecutive bars is exactly 5 seconds. Any gap > 5 seconds during RTH is a missing
bar. The gap checker computes:

1. Load bars sorted ascending by timestamp.
2. For each consecutive pair (bar_i, bar_i+1): if `bar_i+1.timestamp - bar_i.timestamp > 5`,
   record a `GapInterval`.
3. Count expected bars: 4,680 for a full RTH session.
4. Flag the day if any gaps exist OR if `bar_count < 4,680`.

**Gap checker is a pure module** (no IBKR dependency, no file I/O — takes `DailyBars`,
returns `GapReport`). This makes it fully unit testable.

Gaps are logged and flagged but do NOT block saving the file — partial data is
better than no data for a day that can never be re-downloaded.

---

## Decision 6: News Download

**Decision**: IBKR `reqHistoricalNews` API with Benzinga (`"BZ"`) provider.
Run sentiment on headlines only (do not fetch full article bodies).

**Rationale**:
IBKR provides `reqHistoricalNews(reqId, conId, providerCodes, startDateTime, endDateTime,
totalResults, historicalNewsOptions)`. The `historicalNews` callback returns per-article
metadata: `(time, providerCode, articleId, headline)`. The SPY `conId` must be resolved
dynamically via `reqContractDetails` (do not hardcode it; IBKR can reassign IDs).

Headlines alone are sufficient for daily sentiment aggregation. Fetching full article
bodies via `reqNewsArticle` multiplies the number of IBKR API calls by the article
count per day, adding pacing risk with negligible accuracy benefit at the daily
aggregation level.

**Subscription requirement**: Benzinga (`BZ`) requires a paid IBKR news subscription.
The system logs a clear error if news is unavailable and falls back to storing an empty
sentiment record for that day (does not block bar data download).

**News download scope**: News is downloaded only for dates where a `SPY` bar file
already exists on disk. This ensures sentiment dates are always paired with price data.

**Date matching**: For a trading day `D`, news is fetched for the window
`D 00:00:00 UTC` to `D+1 00:00:00 UTC`. This captures pre-market, intraday, and
after-hours news published on that calendar day.

**Pacing**: 0.5-second delay between `reqNewsArticle` calls if invoked. General
60-requests-per-10-minutes limit applies.

---

## Decision 7: Sentiment Analysis Library

**Decision**: `ProsusAI/finbert` via HuggingFace `transformers`. CPU-only inference.

**Rationale**:
FinBERT achieves ~87% accuracy on Financial PhraseBank, compared to ~70% for VADER.
The accuracy gap is large enough to affect signal quality materially. For 5–20
headlines per day, CPU inference takes 2–10 seconds — entirely acceptable for a
nightly batch job.

**Daily score formula**: For N headlines, the daily sentiment score is:
```
score = mean(positive_prob - negative_prob) for each headline
```
This produces a value in [-1.0, +1.0]. Positive scores indicate net positive news.

**VADER fallback**: `vaderSentiment` is included as an optional lightweight fallback
(set `sentiment_backend: vader` in config). VADER requires no model download and runs
in milliseconds, making it useful for rapid development and testing.

---

## Decision 8: SPY Sentiment Response Test

**Decision**: Pytest test in `tests/research/test_spy_sentiment_response.py` that
**asserts alignment ≥ 80%**. Tests are per individual news article against the SPY
5-second bars in the 30 seconds following the article's publication timestamp.

**Methodology**:
1. Load per-article news data from `{data_dir}/news/*_articles.json`.
   Each article includes a `sentiment_score` stored at news pipeline run time.
2. Load the corresponding SPY 5-second bar CSV for each article's date.
3. For each article published during regular trading hours (9:30–15:59:30 ET)
   with `abs(sentiment_score) >= 0.05`:
   - Find first SPY bar at or after the article timestamp.
   - Find the bar 30 seconds later (6 bars ahead).
   - `price_change = close_30s - close_at_news`
   - `aligned = (sign(sentiment_score) == sign(price_change))`
4. `alignment_pct = aligned_count / tested_count × 100`
5. `assert alignment_pct >= 80.0`

This is a proper pytest assertion, not a report. The 80% threshold is the required
success rate specified by the user. Articles with near-neutral scores and those
published outside market hours are excluded to reduce noise.

---

## Module Architecture

| Module | Responsibility |
|--------|---------------|
| `types.py` | All dataclasses: `InstrumentConfig`, `AppConfig`, `Bar`, `DailyBars`, `GapReport`, `GapInterval`, `NewsItem`, `DailySentiment`, `DayDownloadResult` |
| `config_loader.py` | Load and validate `config.yaml` → `AppConfig` |
| `ibkr_client.py` | IBKR connection lifecycle, pacing, `reqHistoricalData`, `reqHistoricalNews`, `reqContractDetails` |
| `contract_resolver.py` | Build `ibapi.Contract` objects; resolve ES/VXM expiry months; set `includeExpired` |
| `bar_downloader.py` | Download one symbol's bars for one date; apply SPX/VIX timestamp filtering |
| `gap_checker.py` | Validate bar sequence; detect gaps; return `GapReport` |
| `file_writer.py` | Write/read per-day CSV; check existence; NEVER overwrite |
| `news_downloader.py` | Resolve SPY conId; download headlines for a date range |
| `sentiment_analyzer.py` | Load FinBERT (or VADER); score headlines; return `DailySentiment` |
| `downloader.py` | Orchestrate: config → dates → per-day bar download loop |
| `news_pipeline.py` | Orchestrate: config → SPY dates → news download → sentiment → save |

**Critical constraint**: `file_writer.py` MUST return without writing if the file
already exists. This is the only protection against losing historical data forever.
