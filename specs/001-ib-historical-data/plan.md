# Implementation Plan: Historical Market Data + News Sentiment from IBKR

**Branch**: `001-ib-historical-data` | **Date**: 2026-02-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ib-historical-data/spec.md`

## Summary

Build a Python tool that:
1. Downloads 5-second OHLCV bar data from Interactive Brokers for configurable
   instruments (stocks, indices, futures), saving one CSV file per symbol per trading day.
2. Validates each day's data for sequence gaps.
3. Downloads news headlines from IBKR and computes daily FinBERT sentiment for SPY.
4. Provides a pytest test that asserts SPY's 30-second bar price direction matches
   per-article sentiment in ≥ 80% of intraday news items.

Instruments are configured in `src/config.yaml`. Data lands in
`/Users/abeadam/dev/data_loader/data/` (outside the git repo). Existing files are
NEVER overwritten — this preserves data beyond IBKR's 6-month 5-second bar lookback.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `ibapi` — IBKR official Python API (EWrapper/EClient pattern, matching reference code)
- `PyYAML` — config file parsing
- `transformers` + `torch` — FinBERT sentiment analysis (ProsusAI/finbert)
- `vaderSentiment` — lightweight sentiment fallback (optional, configured per install)
- `zoneinfo` — DST-correct ET→UTC conversion (stdlib in Python 3.9+)

**Storage**: CSV files. One file per (symbol, trading day).
Path: `/Users/abeadam/dev/data_loader/data/bars/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}.csv`
News: `/Users/abeadam/dev/data_loader/data/news/{YYYY-MM-DD}_{articles.json|sentiment.csv}`

**Testing**: `pytest`
- `tests/unit/` — pure logic tests; no IBKR connection required
- `tests/integration/` — require live TWS; marked `@pytest.mark.integration`
- `tests/research/` — data-driven test; asserts ≥ 80% alignment between per-article
  sentiment and SPY price direction over the following 30 seconds (6 five-second bars)

**Target Platform**: macOS / Linux (researcher's local machine with TWS running)

**Project Type**: CLI tool invoked as `python -m src.downloader` and `python -m src.news_pipeline`

**Performance Goals**:
- IBKR 5-second bar lookback: ≈180 calendar days (hard IBKR constraint)
- File existence check prevents redundant downloads on every run
- Pacing: 2-second sleep between bar requests; 0.5-second between news article fetches

**Constraints**:
- IBKR pacing: max 60 historical requests / 10 minutes
- IBKR 5-second bar history: max ~6 months lookback — data older than this CANNOT be re-downloaded
- News requires a Benzinga (BZ) subscription on the IBKR account
- `useRTH=0` — includes pre/post market; VIX and SPX bars must be filtered to RTH range

**Scale/Scope**: Up to ~20 instruments × 180 days ≈ 3,600 files per full initial run

## Constitution Check

*GATE: Must pass before implementation. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|---------|
| I. Module Separation | ✅ PASS | 11 modules, one responsibility each. `ibkr_client.py` owns all ibapi calls. `gap_checker.py` is pure logic. `file_writer.py` owns all file I/O. `sentiment_analyzer.py` owns all model inference. No module combines more than one of these concerns. |
| II. Code Quality | ✅ PASS (enforce at impl) | Named constants (`EXPECTED_REGULAR_SESSION_BARS`, `IBKR_MAX_LOOKBACK_DAYS`). Descriptive names (`target_date` not `d`, `provider_codes` not `pc`). Short pure functions for gap detection, contract resolution, sentiment aggregation. Post-task review mandatory. |
| III. Test-First | ✅ PASS (enforce in tasks) | `gap_checker.py`, `contract_resolver.py`, and `sentiment_analyzer.py` are pure functions with no external deps — ideal for writing tests first. Tasks.md will mandate test tasks before every implementation task. |
| IV. Incremental Development | ✅ PASS | Deliverable in 3 independent increments: (1) bar download pipeline, (2) gap checking, (3) news + sentiment. Each is independently testable and usable. |
| V. Git Workflow | ✅ PASS | Branch `001-ib-historical-data`. Data directory is a sibling of the repo (not inside it) — no gitignore needed. `main` untouched until explicit approval. |

**Important boundary to enforce during review**:
- `file_writer.py` MUST raise `FileExistsError` if the file exists. Callers check first.
  This is the last line of defense for data preservation.
- `gap_checker.py` MUST NOT write to disk or call IBKR — pure input/output only.
- `sentiment_analyzer.py` MUST NOT read/write files — pure headline-in, score-out.

**No violations. Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-ib-historical-data/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Library, format, gap, news, sentiment decisions
├── data-model.md        # Entity definitions and file schemas
├── quickstart.md        # End-to-end validation guide
├── contracts/
│   ├── public-api.md        # CLI entry points, config schema, exit codes
│   └── internal-modules.md  # Per-module function contracts
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
src/
├── config.yaml                  # Instruments, data_dir, ibkr settings, news config
├── types.py                     # All dataclasses (no logic)
├── config_loader.py             # Load + validate config.yaml → AppConfig
├── ibkr_client.py               # IBKRClient, connect_to_ibkr, fetch_historical_bars,
│                                # resolve_con_id, fetch_historical_news
├── contract_resolver.py         # resolve_contract(), ES/VXM expiry resolution,
│                                # VIX sec_type override
├── bar_downloader.py            # download_day(), compute_end_datetime()
│                                # SPX duration override, VIX/SPX RTH filtering
├── gap_checker.py               # check_gaps() — pure function
├── file_writer.py               # day_file_path(), file_exists(), write_bars(),
│                                # read_bars() — raises FileExistsError on overwrite
├── news_downloader.py           # download_news_for_date(), resolve_spy_con_id()
├── sentiment_analyzer.py        # load_model(), score_headlines(),
│                                # aggregate_daily_sentiment()
├── downloader.py                # run_download() — bar pipeline orchestration
│                                # is_market_holiday()
└── news_pipeline.py             # run_news_pipeline() — news + sentiment orchestration

tests/
├── unit/
│   ├── test_types.py
│   ├── test_config_loader.py
│   ├── test_contract_resolver.py    # Pure logic — no IBKR
│   ├── test_gap_checker.py          # Pure logic — no IBKR, no files
│   ├── test_file_writer.py          # File I/O — tmp dirs, no IBKR
│   └── test_sentiment_analyzer.py  # Pure logic — mock model responses
├── integration/                     # @pytest.mark.integration — requires live TWS
│   ├── test_bar_downloader.py
│   └── test_news_downloader.py
└── research/                        # Asserts ≥ 80% alignment; per-article, 30-second bar window
    └── test_spy_sentiment_response.py
```

**Structure Decision**: Single project layout. CLI entry points via `python -m`.
Source under `src/`, tests under `tests/`, data outside the repo at
`/Users/abeadam/dev/data_loader/data/`.

## Complexity Tracking

> Not applicable — no Constitution violations to justify.

## Key Implementation Notes

### Data Safety (highest priority)

The `file_exists()` check in `file_writer.py` is the only protection against permanent
data loss. Once a 5-second bar file is older than 6 months, IBKR will refuse to
provide it again. Implementation MUST:
1. Check `file_exists()` before every download attempt.
2. `write_bars()` MUST raise `FileExistsError` as a second safety net.
3. `run_download()` MUST catch `FileExistsError` and log it — never propagate as a crash.

### Futures Contract Resolution

Matching the reference code exactly:
- ES: `secType="FUT"` + `lastTradeDateOrContractMonth` = active quarterly expiry
  (Mar/Jun/Sep/Dec, 3rd Friday) + `includeExpired=True`
- VXM: `secType="FUT"` + `lastTradeDateOrContractMonth` = active monthly expiry
  (3rd Wednesday) + `includeExpired=True`
- VIX: `secType="IND"` + `exchange="CBOE"` (override config)
- All other instruments: use config values as-is

### VIX/SPX Timestamp Filtering

The reference code shows that VIX and SPX return data outside RTH when `useRTH=0`.
The filtering strategy (from reference):
1. If SPY file for same date exists: use SPY's first/last timestamp as the range filter.
2. If SPY file doesn't exist: trim to expected 4,680 bars from center of the data.

This logic belongs in `bar_downloader.py` and MUST be tested with synthetic bar
sequences that include GTH data.

### SPX Duration Override

SPX requires `durationStr="24000 S"` (6.67 hours) instead of `"1 D"` to reliably
capture the full trading session. This is a known IBKR quirk from the reference code.
The override is in `bar_downloader.py`, not in `ibkr_client.py`.

### SPY Sentiment Response Test (30-second bar window, ≥ 80% required)

The test in `tests/research/test_spy_sentiment_response.py` is a proper pytest test
with a hard assertion:

```
assert alignment_pct >= 80.0
```

**Test methodology** (per individual news article, not per day):
1. Load per-article data from `{data_dir}/news/*_articles.json`.
   Each article JSON object MUST include a `sentiment_score` field (stored during
   the news pipeline run — this avoids re-running FinBERT at test time).
2. Skip articles published outside regular trading hours (9:30–15:59:30 ET) —
   there must be 30 seconds of bar data remaining in the session.
3. Skip near-neutral articles where `abs(sentiment_score) < 0.05` (ambiguous signal).
4. For each eligible article at timestamp T:
   - Find the first SPY 5-second bar at or after T (using the bar's timestamp column).
   - Find the bar exactly 30 seconds later (6 bars ahead).
   - `price_change = close_at_T+30s - close_at_T`
   - `aligned = (sign(sentiment_score) == sign(price_change))`
5. `alignment_pct = aligned_count / tested_count × 100`
6. Assert `alignment_pct >= 80.0`.

The `articles.json` schema MUST include a `sentiment_score` field per article:
```json
{
  "article_id": "BZ$abc123",
  "provider_code": "BZ",
  "timestamp": "2024-08-01T10:32:00Z",
  "headline": "...",
  "symbol": "SPY",
  "sentiment_score": 0.74
}
```
