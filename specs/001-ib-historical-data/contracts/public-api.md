# Public API Contract

**Feature**: 001-ib-historical-data
**Date**: 2026-02-26

The public interface is the command-line entry point and the config file schema.
There is no importable library API — the tool is invoked as a script.

---

## Entry Points

### `python -m src.downloader`

Downloads 5-second bar data for all instruments in `config.yaml`, for all available
dates not already on disk. Connects to IBKR, walks backward from yesterday to the
earliest available date (approximately today minus 180 days), downloads each missing
day, runs gap checks, and saves files.

```bash
# From repository root
python -m src.downloader [--config PATH]

# Options:
#   --config PATH   Path to config.yaml (default: src/config.yaml)
```

**Behavior**:
- Skips weekends and US market holidays automatically.
- Skips any (symbol, date) pair where the file already exists.
- Logs gap reports to stdout; flags days with missing bars.
- Never deletes or overwrites existing files.
- Exits 0 on success (even with partial failures); logs failures per symbol/date.
- Exits 1 if IBKR connection cannot be established.

---

### `python -m src.news_pipeline`

Downloads news headlines from IBKR for all trading days that have a SPY bar file
on disk. Runs FinBERT sentiment on each day's headlines. Saves per-day JSON (articles)
and CSV (sentiment scores).

```bash
python -m src.news_pipeline [--config PATH]

# Options:
#   --config PATH   Path to config.yaml (default: src/config.yaml)
```

**Behavior**:
- Only processes dates where `{data_dir}/bars/SPY/YYYY-MM-DD_SPY.csv` exists.
- Skips dates where `{data_dir}/news/YYYY-MM-DD_sentiment.csv` already exists.
- Logs a warning (does not fail) if news subscription is unavailable for a date.

---

### `python -m tests.research.test_spy_sentiment_response`

Loads all available daily sentiment scores and SPY price data from disk. Computes
the percentage of days where SPY's next-day price direction matched the sentiment
sign. Prints a report to stdout.

```bash
python -m tests.research.test_spy_sentiment_response [--config PATH]
```

**Output example**:
```
SPY Sentiment Response Analysis
================================
Date range: 2024-08-01 → 2025-02-21
Days tested: 142
Days aligned: 79
Alignment rate: 55.6%

Date         Sentiment  SPY Return  Aligned
-----------  ---------  ----------  -------
2024-08-01    +0.42      +0.83%      YES
2024-08-02    -0.18      -0.51%      YES
2024-08-05    +0.03      -1.12%      NO
...
```

---

## Configuration File Schema

**Path**: `src/config.yaml`

```yaml
# Root directory for all downloaded data. Must be writable. Not in git repo.
data_dir: /Users/abeadam/dev/data_loader/data

# IBKR TWS / IB Gateway connection settings
ibkr_host: "127.0.0.1"
ibkr_port: 7497               # TWS live: 7496, TWS paper: 7497, IB Gateway live: 4001, paper: 4002

# Instruments to download. Add/remove entries to change what gets downloaded.
# sec_type values: STK (stocks), IND (indices), CONTFUT (futures - resolved to FUT at runtime)
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
    sec_type: CONTFUT
    exchange: CME
    currency: USD
  - symbol: VXM
    sec_type: CONTFUT
    exchange: CFE
    currency: USD

# News and sentiment settings
news:
  provider_codes: "BZ"        # Benzinga. Update per your IBKR news subscriptions.
  spy_symbol: SPY             # News is fetched for this symbol; dates matched to its bar files.
  sentiment_backend: finbert  # "finbert" (accurate, ~3GB install) or "vader" (fast, 2MB install)
```

**Validation rules**:
- `data_dir` MUST be an absolute path.
- `ibkr_port` MUST be an integer.
- Each instrument MUST have non-empty `symbol`, `sec_type`, `exchange`, `currency`.
- `sec_type` MUST be one of: `"STK"`, `"IND"`, `"CONTFUT"`, `"FUT"`.
- `sentiment_backend` MUST be `"finbert"` or `"vader"`.
- Duplicate symbols in the instruments list are silently deduplicated.

---

## Output File Paths

### Bar files
```
{data_dir}/bars/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}.csv
```

Example:
```
/Users/abeadam/dev/data_loader/data/bars/SPY/2024-08-01_SPY.csv
```

### News article file
```
{data_dir}/news/{YYYY-MM-DD}_articles.json
```

### Daily sentiment file
```
{data_dir}/news/{YYYY-MM-DD}_sentiment.csv
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Completed successfully (may have partial per-symbol failures) |
| 1 | IBKR connection failed; no data downloaded |
| 2 | Config file not found or invalid |
