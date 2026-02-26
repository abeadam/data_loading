# Data Model: Historical Market Data Download from Interactive Brokers

**Feature**: 001-ib-historical-data
**Date**: 2026-02-26

---

## Overview

All entities are defined as Python dataclasses in `src/types.py`.
Internal modules import only from `types.py`; no module imports from another
module's types. This keeps the dependency graph flat.

---

## Configuration Entities (loaded from `config.yaml`)

### `InstrumentConfig`

One entry in the YAML instruments list. Represents a single downloadable instrument.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Ticker symbol (e.g., `"SPY"`, `"ES"`, `"VIX"`) |
| `sec_type` | `str` | IBKR security type: `"STK"`, `"IND"`, `"CONTFUT"` |
| `exchange` | `str` | IBKR exchange (e.g., `"SMART"`, `"CME"`, `"CBOE"`, `"CFE"`) |
| `currency` | `str` | Settlement currency (e.g., `"USD"`) |

**Validation rules**:
- `symbol` MUST be non-empty and uppercase.
- `sec_type` MUST be one of: `"STK"`, `"IND"`, `"CONTFUT"`, `"FUT"`.
- `exchange` and `currency` MUST be non-empty.

### `AppConfig`

Top-level configuration loaded from `config.yaml`.

| Field | Type | Description |
|-------|------|-------------|
| `data_dir` | `Path` | Root directory for all downloaded data (`/Users/abeadam/dev/data_loader/data`) |
| `ibkr_host` | `str` | TWS/IB Gateway host (default: `"127.0.0.1"`) |
| `ibkr_port` | `int` | TWS/IB Gateway port (default: `7497`) |
| `instruments` | `list[InstrumentConfig]` | All instruments to download |

---

## Bar Data Entities

### `Bar`

A single 5-second OHLCV bar.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `int` | Unix timestamp (seconds since epoch, UTC) |
| `open` | `float` | Open price |
| `high` | `float` | High price |
| `low` | `float` | Low price |
| `close` | `float` | Close price |
| `volume` | `float` | Volume (shares or contracts traded) |

### `DailyBars`

All bars for one instrument on one trading day.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Instrument symbol |
| `date` | `date` | The trading date |
| `bars` | `list[Bar]` | Ordered list of bars (ascending timestamp) |
| `bar_count` | `int` | Number of bars (property; always `len(bars)`) |

**Expected bar count** for a full US equities trading day at 5-second resolution:
- Regular trading hours (9:30 AM – 4:00 PM ET): 6.5 hours × 720 bars/hour = **4,680 bars**

---

## Gap Checking Entities

### `GapReport`

Result of validating one day's bars for a single instrument.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Instrument symbol |
| `date` | `date` | Trading date validated |
| `has_gaps` | `bool` | `True` if any gap was detected |
| `gaps` | `list[GapInterval]` | All detected gaps (empty list if none) |
| `total_bars` | `int` | Actual bar count in the file |
| `expected_bars` | `int` | Expected bar count (4,680 for regular session) |
| `bar_count_delta` | `int` | `total_bars - expected_bars` (negative = short) |

### `GapInterval`

A single detected gap in bar data.

| Field | Type | Description |
|-------|------|-------------|
| `start_timestamp` | `int` | Timestamp of the last bar before the gap |
| `end_timestamp` | `int` | Timestamp of the first bar after the gap |
| `missing_seconds` | `int` | Duration of gap in seconds (`end - start - 5`) |
| `missing_bars` | `int` | Number of expected 5-second bars missing |

---

## News and Sentiment Entities

### `NewsItem`

A single news article fetched from IBKR.

| Field | Type | Description |
|-------|------|-------------|
| `article_id` | `str` | IBKR article identifier |
| `provider_code` | `str` | News provider (e.g., `"BZ"` for Benzinga) |
| `timestamp` | `datetime` | Publication time (UTC) |
| `headline` | `str` | Article headline |
| `body` | `str \| None` | Full article text (may be unavailable) |
| `symbol` | `str` | Symbol this news was fetched for |

### `DailySentiment`

Aggregated sentiment for a single trading day.

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | The trading date |
| `article_count` | `int` | Number of articles contributing to the score |
| `sentiment_score` | `float` | Aggregate sentiment in range `[-1.0, +1.0]` |
| `positive_count` | `int` | Articles classified positive |
| `negative_count` | `int` | Articles classified negative |
| `neutral_count` | `int` | Articles classified neutral |

**Aggregation rule**: `sentiment_score` is the mean of per-article scores.
A positive score indicates net positive news; negative indicates net negative.

### `SentimentTestResult`

Result of the SPY price response validation.

| Field | Type | Description |
|-------|------|-------------|
| `items_tested` | `int` | Number of individual news items tested (only intraday items with 30 seconds of subsequent bars) |
| `items_aligned` | `int` | News items where SPY 30-second price direction matched sentiment sign |
| `alignment_pct` | `float` | `items_aligned / items_tested × 100` |
| `passed` | `bool` | `True` if `alignment_pct >= 80.0` |
| `details` | `list[NewsItemAlignment]` | Per-news-item breakdown |

### `NewsItemAlignment`

One row in the per-item breakdown of the sentiment test.

| Field | Type | Description |
|-------|------|-------------|
| `article_id` | `str` | IBKR article identifier |
| `timestamp` | `datetime` | News publication time (UTC) |
| `headline` | `str` | Article headline |
| `sentiment_score` | `float` | Per-article sentiment score in [-1.0, +1.0] |
| `spy_bar_open` | `float` | SPY close price at the first 5-second bar at or after the news timestamp |
| `spy_bar_close_30s` | `float` | SPY close price at the 5-second bar 30 seconds later (6 bars ahead) |
| `price_change` | `float` | `spy_bar_close_30s - spy_bar_open` |
| `aligned` | `bool` | `True` if `sign(sentiment_score) == sign(price_change)` |

---

## Download Result Entities

### `DayDownloadResult`

Outcome of downloading one instrument for one day.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Instrument symbol |
| `date` | `date` | Trading date attempted |
| `success` | `bool` | Whether the download completed |
| `skipped` | `bool` | `True` if the file already existed (not re-downloaded) |
| `bars_saved` | `int` | Number of bars written (0 if failed or skipped) |
| `file_path` | `Path \| None` | Path to the CSV file |
| `error_message` | `str \| None` | Description of failure, if any |

---

## Stored File Schemas

### Per-day bar file
**Path**: `{data_dir}/bars/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}.csv`

```
timestamp,open,high,low,close,volume
1704196200,476.23,476.25,476.20,476.22,12450
1704196205,476.22,476.28,476.21,476.26,8930
...
```

- `timestamp`: Unix epoch seconds (UTC)
- Header row always present
- Rows ordered ascending by timestamp
- No trailing newline

### Daily sentiment file
**Path**: `{data_dir}/news/{YYYY-MM-DD}_sentiment.csv`

```
date,article_count,sentiment_score,positive_count,negative_count,neutral_count
2024-01-02,12,0.42,7,2,3
```

### Daily news articles file
**Path**: `{data_dir}/news/{YYYY-MM-DD}_articles.json`

```json
[
  {
    "article_id": "BZ$abc123",
    "provider_code": "BZ",
    "timestamp": "2024-01-02T10:32:00Z",
    "headline": "SPY outperforms expectations...",
    "symbol": "SPY",
    "sentiment_score": 0.74
  }
]
```

**Note**: `sentiment_score` (per-article FinBERT score in `[-1.0, +1.0]`) MUST be
stored at news pipeline run time. The sentiment response test loads this field directly
rather than re-running the model at test time.

---

## State Transitions

### Daily Download Lifecycle

```
Pending → Exists on disk? → Yes → Skipped (file preserved, not re-downloaded)
                          → No  → Downloading → IBKR call →
                                   Success → Gap Check → Writing → Complete
                                   Failure → Failed (logged, no file written)
```

The "Exists on disk" check is the critical safety gate that preserves historical
data beyond IBKR's 6-month 5-second bar lookback limit.
