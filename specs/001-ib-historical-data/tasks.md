---
description: "Task list for 001-ib-historical-data"
---

# Tasks: Historical Market Data + News Sentiment from IBKR

**Input**: Design documents from `/specs/001-ib-historical-data/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**TDD Mandate**: Per Constitution Principle III — tests MUST be written and verified to FAIL
before each implementation task. No implementation code is written before a failing test exists.

**Organization**: 7 user story phases + setup + foundation + polish.
- US1 (P1): Bar download — equities and indices
- US2 (P2): Bar download — futures with expiry contract resolution
- US3 (P3): Batch download — all instruments from config
- US4: News download + FinBERT sentiment pipeline
- US5: SPY sentiment response test (asserts ≥ 80% 30-second alignment)

---

## Phase 1: Setup

**Purpose**: Project initialization, directory structure, dependencies

- [x] T001 Create directory structure: `src/`, `tests/unit/`, `tests/integration/`, `tests/research/` at repo root
- [x] T002 Create `src/config.yaml` with default instruments: SPY (STK/SMART), SPX (IND/CBOE), VIX (IND/CBOE), ES (CONTFUT/CME), VXM (CONTFUT/CFE); include `data_dir`, `ibkr_host`, `ibkr_port`, `news` section
- [x] T003 [P] Create `requirements.txt` with: `ibapi`, `PyYAML`, `transformers`, `torch`, `vaderSentiment`, `pytest`, `ruff`
- [x] T004 [P] Create `tests/conftest.py` with pytest markers: `@pytest.mark.integration` (requires live TWS), `@pytest.mark.research` (requires on-disk data); include `tmp_data_dir` fixture for file I/O tests

---

## Phase 2: Foundation (Blocking All User Stories)

**Purpose**: Shared types and config loading — no user story can start without these.

**⚠️ CRITICAL**: All user story phases depend on T005–T008 being complete.

- [x] T005 Write tests for `src/types.py` in `tests/unit/test_types.py`: verify all dataclasses are frozen where specified, DailyBars.bar_count returns len(bars), GapInterval.missing_bars = missing_seconds // 5, SentimentTestResult.passed = (alignment_pct >= 80.0)
- [x] T006 Implement `src/types.py`: InstrumentConfig, AppConfig, Bar, DailyBars (with bar_count property), GapInterval, GapReport, NewsItem, DailySentiment, DayDownloadResult, NewsItemAlignment, SentimentTestResult — no logic, no imports from other src/ modules
- [x] T007 Write tests for `src/config_loader.py` in `tests/unit/test_config_loader.py`: valid config returns AppConfig, missing `data_dir` raises ValueError, non-absolute `data_dir` raises ValueError, invalid `sec_type` raises ValueError, unknown `sentiment_backend` raises ValueError, duplicate symbols are deduplicated
- [x] T008 Implement `src/config_loader.py`: load_config(config_path: Path) → AppConfig; validate all fields per contracts/internal-modules.md; deduplicate instruments silently

**Checkpoint**: `pytest tests/unit/test_types.py tests/unit/test_config_loader.py` passes

---

## Phase 3: User Story 1 — Bar Download for Equities & Indices (P1) 🎯 MVP

**Goal**: `python -m src.downloader` downloads 5-second bars for SPY, SPX, VIX into
`/Users/abeadam/dev/data_loader/data/bars/{SYMBOL}/YYYY-MM-DD_{SYMBOL}.csv`,
skipping existing files, flagging gaps.

**Independent Test**: Run `python -m src.downloader --config src/config.yaml` with only
SPY in the config. Verify files appear in `data/bars/SPY/`, each with 4,680 rows.
Re-run — verify no files are modified.

### Tests for User Story 1 ⚠️ Write and verify FAIL before implementing

- [x] T009 [P] [US1] Write tests for `src/gap_checker.py` in `tests/unit/test_gap_checker.py`: perfect 4,680-bar sequence → no gaps; one 10-second gap at bar 100 → GapInterval with missing_bars=1; two gaps → two GapIntervals; only 4,000 bars → has_gaps=True, bar_count_delta=-680; empty bars list → GapReport with 0 bars and has_gaps=True
- [x] T010 [P] [US1] Write tests for `src/file_writer.py` in `tests/unit/test_file_writer.py`: day_file_path returns correct path format; write_bars creates file with CSV header and correct rows; read_bars returns DailyBars matching written data; write_bars raises FileExistsError if file exists (data safety test); file_exists returns True/False correctly
- [x] T011 [P] [US1] Write tests for `src/contract_resolver.py` (equity/index cases) in `tests/unit/test_contract_resolver.py`: STK instrument → Contract with secType="STK"; IND instrument → Contract with secType="IND"; VIX with any config sec_type → Contract overridden to secType="IND", exchange="CBOE"; CONTFUT instrument without date → raises NotImplementedError (stub until US2)

### Implementation for User Story 1

- [x] T012 [US1] Implement `src/gap_checker.py`: EXPECTED_BAR_INTERVAL_SECONDS = 5, EXPECTED_REGULAR_SESSION_BARS = 4680; check_gaps(bars: DailyBars) → GapReport; sort bars ascending; compute consecutive diffs; collect GapIntervals where diff > 5; set has_gaps if any gap or total < expected
- [x] T013 [US1] Implement `src/file_writer.py`: CSV_HEADER = "timestamp,open,high,low,close,volume"; day_file_path(data_dir, symbol, date) → Path using `{data_dir}/bars/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}.csv`; file_exists(data_dir, symbol, date) → bool; write_bars(data_dir, bars) → Path — creates parent dirs, raises FileExistsError if file exists, writes header + rows ascending; read_bars(data_dir, symbol, date) → DailyBars
- [x] T014 [US1] Implement `src/contract_resolver.py` for STK and IND: resolve_contract(instrument, target_date) → ibapi.Contract; apply VIX override (secType="IND", exchange="CBOE"); for CONTFUT raise NotImplementedError with message "Futures contract resolution not yet implemented — see US2"; stubs get_active_es_contract_month() and get_active_vxm_contract_month() as NotImplementedError
- [x] T015 [US1] Implement `src/ibkr_client.py`: IBKRClient(EWrapper, EClient) with historicalData/historicalDataEnd/error/nextValidId callbacks; connect_to_ibkr(host, port, client_ids=[1,2,3,4,5]) → IBKRClient (tries each ID, raises ConnectionError on all fail); disconnect(client); fetch_historical_bars(client, contract, end_datetime, duration_str, bar_size="5 secs", what_to_show="TRADES", use_rth=0) → list[dict] (blocks until historicalDataEnd, 2-second pacing sleep after each call, 1-minute timeout, 10-minute timeout for SPX)
- [x] T016 [US1] Implement `src/bar_downloader.py`: REGULAR_SESSION_BAR_COUNT = 4680; compute_end_datetime(target_date) → str using zoneinfo to convert 4:00 PM ET → UTC in IBKR format "YYYYMMDD-HH:MM:SS"; download_day(client, instrument, target_date, spy_bars=None) → DailyBars | None; set duration_str="24000 S" for SPX, "1 D" for all others; apply RTH timestamp filtering for VIX and SPX using spy_bars range or center-trim to 4,680 bars
- [x] T017 [US1] Implement `src/downloader.py`: IBKR_MAX_LOOKBACK_DAYS = 180; is_market_holiday(date) → bool (New Year's, MLK, Presidents', Good Friday, Memorial, Juneteenth, Independence, Labor, Thanksgiving, Christmas); run_download(config) → list[DayDownloadResult] — connect, compute date range (today-180 → yesterday), walk dates forward, skip weekends/holidays, for each (date, instrument): check file_exists → log skip if true; else download_day → gap_check → write_bars → record result; disconnect; add `if __name__ == "__main__":` block with --config argparse arg
- [x] T018 [US1] Write integration test for single SPY download in `tests/integration/test_bar_downloader.py` (@pytest.mark.integration): connect, download SPY for yesterday, verify DailyBars returned with bar_count >= 1, verify file written with correct path, verify re-download raises FileExistsError

**Checkpoint**: `python -m src.downloader` downloads SPY, SPX, VIX files to `data/bars/`; re-run is fully safe (no overwrites); gap report logged to stdout.

---

## Phase 4: User Story 2 — Bar Download for Futures (P2)

**Goal**: Futures instruments (ES, VXM) download with correct expiry contract for each historical date.

**Independent Test**: Run `python -m src.downloader` with ES in config for a date spanning a quarterly expiry. Verify the correct `lastTradeDateOrContractMonth` is used for each day.

### Tests for User Story 2 ⚠️ Write and verify FAIL before implementing

- [ ] T019 [P] [US2] Write tests for futures contract resolution in `tests/unit/test_contract_resolver.py`: get_active_es_contract_month for dates in each quarter (e.g., 2024-01-15 → "202403", 2024-03-17 (after 3rd Friday) → "202406"); get_active_vxm_contract_month for dates mid-month and post-3rd-Wednesday; resolve_contract with CONTFUT ES → secType="FUT", lastTradeDateOrContractMonth set, includeExpired=True; same for VXM

### Implementation for User Story 2

- [ ] T020 [US2] Implement get_active_es_contract_month(target_date) and get_active_vxm_contract_month(target_date) in `src/contract_resolver.py` using get_third_friday() and get_third_wednesday() helpers; match reference code logic exactly
- [ ] T021 [US2] Extend resolve_contract() in `src/contract_resolver.py` to handle CONTFUT: set secType="FUT", lastTradeDateOrContractMonth via get_active_es/vxm_contract_month(), includeExpired=True; remove NotImplementedError stubs
- [ ] T022 [US2] Verify run_download() in `src/downloader.py` handles CONTFUT instruments without changes (contract resolution is in contract_resolver); confirm ES and VXM download correctly end-to-end
- [ ] T023 [US2] Write integration test for ES futures download in `tests/integration/test_bar_downloader.py` (@pytest.mark.integration): download ES for a specific historical date, verify contract month matches expected expiry, verify bars returned

**Checkpoint**: `python -m src.downloader` downloads ES and VXM correctly; each day uses the right expiry contract; files appear in `data/bars/ES/` and `data/bars/VXM/`.

---

## Phase 5: User Story 3 — Batch Download for All Configured Instruments (P3)

**Goal**: A single `python -m src.downloader` run processes every instrument in config.yaml,
handling individual failures without aborting the entire batch.

**Independent Test**: Add 5 instruments to config.yaml. Run downloader. Verify files appear
for each instrument. Introduce an invalid symbol. Re-run. Verify valid instruments are
downloaded and the invalid one is logged as failed.

### Implementation for User Story 3

- [ ] T024 [US3] Verify run_download() in `src/downloader.py` already iterates all instruments from AppConfig.instruments (should be true from T017); if not, extend to loop over all; confirm DayDownloadResult is recorded per (symbol, date) pair
- [ ] T025 [US3] Add partial-failure handling in run_download() in `src/downloader.py`: catch all exceptions per (symbol, date) pair, record error_message in DayDownloadResult, continue to next instrument; print summary at end: N files downloaded, M skipped, K failed
- [ ] T026 [US3] Write integration test for batch download in `tests/integration/test_bar_downloader.py` (@pytest.mark.integration): configure 3 instruments, run download, verify 3 × N day files created; include one invalid symbol, verify it produces failed DayDownloadResult without aborting others

**Checkpoint**: `python -m src.downloader` with full config (SPY, SPX, VIX, ES, VXM) produces files for all instruments; failures are logged but do not crash the run.

---

## Phase 6: User Story 4 — News Download + FinBERT Sentiment Pipeline

**Goal**: `python -m src.news_pipeline` fetches IBKR news headlines for each SPY bar date,
scores them with FinBERT, saves per-article `sentiment_score` to `*_articles.json` and
per-day aggregate to `*_sentiment.csv`.

**Independent Test**: Verify that `{data_dir}/news/YYYY-MM-DD_articles.json` contains a
`sentiment_score` field for every article, and `YYYY-MM-DD_sentiment.csv` has a score
in [-1.0, +1.0]. Re-running skips already-processed dates.

### Tests for User Story 4 ⚠️ Write and verify FAIL before implementing

- [ ] T027 [P] [US4] Write tests for `src/sentiment_analyzer.py` in `tests/unit/test_sentiment_analyzer.py`: mock finbert pipeline output → score_headlines returns floats in [-1,+1]; vader backend → compound score returned; aggregate_daily_sentiment with empty list → article_count=0, sentiment_score=0.0; aggregate with 3 items → mean of per-article scores; positive/negative/neutral counts correct

### Implementation for User Story 4

- [ ] T028 [US4] Implement `src/sentiment_analyzer.py`: load_model(backend) → model object (finbert: transformers pipeline("text-classification", model="ProsusAI/finbert", top_k=None); vader: SentimentIntensityAnalyzer()); score_headlines(model, headlines, backend) → list[float] (finbert: positive_prob - negative_prob; vader: compound); aggregate_daily_sentiment(model, backend, news_items, date) → DailySentiment
- [ ] T029 [US4] Implement `src/news_downloader.py`: resolve_spy_con_id(client, spy_instrument) → int using fetch_historical_bars via reqContractDetails callback; download_news_for_date(client, symbol, con_id, provider_codes, target_date) → list[NewsItem]; window = midnight UTC to midnight UTC next day; return empty list if no news; raise PermissionError on error code 10276
- [ ] T030 [US4] Add news file writers to `src/news_pipeline.py`: write_articles_json(data_dir, date, articles_with_scores) → Path; write_sentiment_csv(data_dir, date, daily_sentiment) → Path; check existence before writing (skip if already saved)
- [ ] T031 [US4] Implement `src/news_pipeline.py`: run_news_pipeline(config): scan `{data_dir}/bars/{spy_symbol}/` for existing CSV files → date list; filter to dates without existing `*_sentiment.csv`; connect to IBKR; resolve SPY conId once; load sentiment model once; for each date: download headlines → score each article (store per-article score) → aggregate DailySentiment → save articles.json + sentiment.csv; log warning and continue if PermissionError (no subscription); add `if __name__ == "__main__":` block with --config argparse arg
- [ ] T032 [US4] Write integration test for news download in `tests/integration/test_news_downloader.py` (@pytest.mark.integration): connect, download news for SPY for one date, verify list[NewsItem] returned, verify each item has article_id and headline

**Checkpoint**: `python -m src.news_pipeline` produces `*_articles.json` with `sentiment_score` field per article and `*_sentiment.csv` per day; re-run skips existing dates.

---

## Phase 7: User Story 5 — SPY Sentiment Response Test (≥ 80%)

**Goal**: A pytest test that loads all on-disk articles + SPY bars, matches each intraday
article to the next 30 seconds of SPY price movement, and ASSERTS alignment ≥ 80%.

**Independent Test**: Run `pytest tests/research/test_spy_sentiment_response.py`. The test
passes only if ≥ 80% of eligible articles have price movement in the direction of sentiment.

### Implementation for User Story 5

- [ ] T033 [US5] Implement `tests/research/test_spy_sentiment_response.py`: load all `*_articles.json` from `{data_dir}/news/`; for each article: skip if outside 9:30–15:59:30 ET or abs(sentiment_score) < 0.05; load SPY bar CSV for article's date; find first bar at or after article timestamp; find bar 6 positions later (30 seconds); price_change = close[+6] - close[+0]; aligned = sign(sentiment_score) == sign(price_change); compute alignment_pct; print per-article breakdown table; `assert alignment_pct >= 80.0, f"Alignment {alignment_pct:.1f}% < 80%"`; mark test @pytest.mark.research

**Checkpoint**: `pytest tests/research/test_spy_sentiment_response.py -v` PASSES.

---

## Phase N: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Run `ruff check src/ tests/` from repo root; fix all reported issues; re-run until clean
- [ ] T035 [P] Post-task code review: verify all modules against Constitution Principle II — no magic numbers (check for bare `4680`, `5`, `180`, `0.05`, `80.0` — all must be named constants), descriptive names throughout, all public functions have type annotations, no function longer than ~20 lines without a clear reason
- [ ] T036 Manually run quickstart.md Steps 1–8; confirm each step produces the expected output; update quickstart.md if any step is stale

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T003 and T004 are parallel.
- **Foundation (Phase 2)**: Depends on Setup. T007–T008 depend on T005–T006. T005 and T007 are parallel once T001 is done.
- **US1 (Phase 3)**: Depends on Foundation. T009–T011 are parallel (different test files). T012–T014 depend on T009–T011 respectively. T015–T017 depend on T012–T014.
- **US2 (Phase 4)**: Depends on US1 Foundation (ibkr_client, file_writer, downloader); T019 can start once T011 is done.
- **US3 (Phase 5)**: Depends on US1 and US2 both complete.
- **US4 (Phase 6)**: Depends on Foundation (types, config) and file_writer; T027 can start once T005–T006 are done; T028 can start after T027; T029 depends on ibkr_client (T015).
- **US5 (Phase 7)**: Depends on US4 complete (needs articles.json on disk with sentiment_score).
- **Polish (Phase N)**: Depends on all user stories complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Foundation — no dependencies on US2/US3/US4.
- **US2 (P2)**: Can start after US1 (reuses ibkr_client, file_writer, downloader scaffold).
- **US3 (P3)**: Can start after US2 (adds batch behavior to existing downloader).
- **US4**: Can start independently after Foundation (ibkr_client + file_writer needed; otherwise independent).
- **US5**: Depends on US1 (SPY bars on disk) and US4 (articles.json with sentiment_score on disk).

### Within Each User Story

1. Test tasks first — verify FAIL before implementing.
2. Pure logic modules before modules with external deps (gap_checker, contract_resolver before bar_downloader).
3. Implementation modules before orchestration (bar_downloader before downloader).
4. Integration tests after implementation is complete.

---

## Parallel Opportunities

### Within Phase 3 (US1)

```bash
# Launch all US1 test tasks together (must FAIL before next step):
Task: "Write gap_checker tests in tests/unit/test_gap_checker.py"       # T009
Task: "Write file_writer tests in tests/unit/test_file_writer.py"       # T010
Task: "Write contract_resolver tests in tests/unit/test_contract_resolver.py"  # T011
```

### Within Phase 4 (US2)

```bash
# T019 can start immediately after T011 (same test file, different test class):
Task: "Write futures contract resolution tests"   # T019
```

### Within Phase 6 (US4)

```bash
# T027 can start as soon as types.py is done (T005-T006):
Task: "Write sentiment_analyzer tests"   # T027
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundation
3. Complete Phase 3: US1 (equities + indices only)
4. **STOP and VALIDATE**: Run `python -m src.downloader` for SPY only. Verify files, bar counts, gap reporting, safety re-run.
5. Proceed to US2 (futures).

### Incremental Delivery

1. Setup + Foundation → types and config work
2. US1 complete → SPY/SPX/VIX downloading
3. US2 complete → ES/VXM futures downloading
4. US3 complete → all configured instruments in one run
5. US4 complete → news + sentiment per day
6. US5 complete → 30-second sentiment response test ≥ 80%

---

## Notes

- `[P]` = parallelizable with other `[P]` tasks (different files, no shared state)
- TDD is non-negotiable: every test task MUST produce failing tests before its implementation task begins
- **Data safety rule**: Never modify existing bar files. `write_bars()` raises `FileExistsError`. `run_download()` checks `file_exists()` first. Both checks must always be present.
- Integration tests require a live TWS connection and active market data subscriptions. Run them with `pytest -m integration`.
- Research test requires SPY bar files AND articles.json on disk. Run with `pytest -m research` or `pytest tests/research/`.
- Total: **36 tasks** across 9 phases
