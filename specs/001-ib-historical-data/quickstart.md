# Quickstart: Historical Market Data + News Sentiment

**Feature**: 001-ib-historical-data
**Date**: 2026-02-26

---

## Prerequisites

1. Interactive Brokers TWS or IB Gateway is running and accepting API connections on `127.0.0.1:7497`.
2. Python 3.11+ is installed.
3. Project dependencies are installed (see Step 1 below).
4. For news: a Benzinga news subscription is active on the IBKR account.

---

## Step 1: Install Dependencies

```bash
cd /Users/abeadam/dev/data_loader/data_loading

pip install ibapi PyYAML

# For FinBERT sentiment (large install, ~3 GB):
pip install transformers torch

# OR for VADER fallback (lightweight, ~2 MB):
pip install vaderSentiment
```

---

## Step 2: Create the Data Directory

```bash
mkdir -p /Users/abeadam/dev/data_loader/data/bars
mkdir -p /Users/abeadam/dev/data_loader/data/news
```

This directory is outside the git repo — no `.gitignore` entry needed.

---

## Step 3: Configure `src/config.yaml`

Edit `src/config.yaml` to add or remove instruments:

```yaml
data_dir: /Users/abeadam/dev/data_loader/data
ibkr_host: "127.0.0.1"
ibkr_port: 7497

instruments:
  - symbol: SPY
    sec_type: STK
    exchange: SMART
    currency: USD
  - symbol: VIX
    sec_type: IND
    exchange: CBOE
    currency: USD
  - symbol: ES
    sec_type: CONTFUT
    exchange: CME
    currency: USD

news:
  provider_codes: "BZ"
  spy_symbol: SPY
  sentiment_backend: finbert   # or "vader" for faster, smaller install
```

---

## Step 4: Download Bar Data

```bash
python -m src.downloader
```

Expected output (truncated):
```
Connecting to IBKR on 127.0.0.1:7497 (client ID 1)...
Connected successfully.
Download range: 2024-08-01 → 2026-02-25 (180 days)

[2024-08-01] SPY: already have file, skipping.
[2024-08-01] VIX: downloading...
  → 4680 bars saved to /Users/abeadam/dev/data_loader/data/bars/VIX/2024-08-01_VIX.csv
  → Gap check: OK
[2024-08-01] ES: downloading...
  → Contract: ESU24 (active contract for 2024-08-01)
  → 4680 bars saved to /Users/abeadam/dev/data_loader/data/bars/ES/2024-08-01_ES.csv
  → Gap check: OK
...
```

---

## Step 5: Verify Bar Files

```python
import csv
from pathlib import Path

spy_file = Path("/Users/abeadam/dev/data_loader/data/bars/SPY/2024-08-01_SPY.csv")
assert spy_file.exists(), "SPY file not found"

with open(spy_file) as f:
    rows = list(csv.DictReader(f))

assert len(rows) == 4680, f"Expected 4680 bars, got {len(rows)}"
assert rows[0].keys() == {"timestamp", "open", "high", "low", "close", "volume"}

# Verify sequence — no gaps
timestamps = [int(r["timestamp"]) for r in rows]
diffs = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]
gaps = [(i, d) for i, d in enumerate(diffs) if d > 5]
assert gaps == [], f"Gaps detected at bar indices: {gaps}"

print(f"✅ SPY 2024-08-01: {len(rows)} bars, no gaps")
print(f"   First bar: {rows[0]}")
print(f"   Last bar:  {rows[-1]}")
```

---

## Step 6: Download News and Compute Sentiment

```bash
python -m src.news_pipeline
```

Expected output:
```
Loading FinBERT model...
Found 142 SPY dates with bar data.
Skipping 0 dates with existing sentiment files.

[2024-08-01] Fetching news for SPY (conId=756733)...
  → 8 headlines found
  → Sentiment score: +0.34 (6 positive, 1 negative, 1 neutral)
  → Saved: /Users/abeadam/dev/data_loader/data/news/2024-08-01_articles.json
  → Saved: /Users/abeadam/dev/data_loader/data/news/2024-08-01_sentiment.csv
...
```

---

## Step 7: Verify Sentiment Files

```python
import json
import csv
from pathlib import Path

# Check articles JSON
articles_file = Path("/Users/abeadam/dev/data_loader/data/news/2024-08-01_articles.json")
with open(articles_file) as f:
    articles = json.load(f)
print(f"Articles: {len(articles)}")
for a in articles[:2]:
    print(f"  [{a['provider_code']}] {a['headline']}")

# Check sentiment CSV
sentiment_file = Path("/Users/abeadam/dev/data_loader/data/news/2024-08-01_sentiment.csv")
with open(sentiment_file) as f:
    row = list(csv.DictReader(f))[0]
print(f"Sentiment score: {row['sentiment_score']}")
assert -1.0 <= float(row["sentiment_score"]) <= 1.0
print("✅ Sentiment file valid")
```

---

## Step 7: Verify Articles JSON Contains Per-Article Sentiment Score

```python
import json
from pathlib import Path

articles_file = Path("/Users/abeadam/dev/data_loader/data/news/2024-08-01_articles.json")
with open(articles_file) as f:
    articles = json.load(f)

for a in articles[:2]:
    assert "sentiment_score" in a, "Missing sentiment_score field"
    assert -1.0 <= a["sentiment_score"] <= 1.0
    print(f"  [{a['provider_code']}] score={a['sentiment_score']:+.2f}  {a['headline'][:60]}")

print("✅ Articles JSON valid")
```

---

## Step 8: Run SPY Sentiment Response Test

```bash
pytest tests/research/test_spy_sentiment_response.py -v
```

Expected output:
```
tests/research/test_spy_sentiment_response.py::test_sentiment_price_alignment

SPY Sentiment → 30-Second Price Response Analysis
===================================================
Articles tested:  234  (excluded 18 near-neutral, 41 outside RTH)
Articles aligned: 192
Alignment rate:   82.1%  ✅  (threshold: 80.0%)

Article ID   Timestamp            Sentiment  Price Chg  Aligned
-----------  -------------------  ---------  ---------  -------
BZ$1234567   2024-08-01 10:32:00   +0.74     +0.03      YES
BZ$1234568   2024-08-01 11:05:00   -0.51     -0.07      YES
BZ$1234569   2024-08-01 13:15:00   +0.22     -0.01      NO
...

PASSED
```

This test ASSERTS `alignment_pct >= 80.0`. `pytest` will report `FAILED` if the
rate drops below 80%.

---

## Validation Checklist

- [ ] At least one bar file exists per instrument in `{data_dir}/bars/`
- [ ] Each bar file has exactly 4,680 rows (or fewer for shortened sessions)
- [ ] No consecutive bar pair has a timestamp gap > 5 seconds
- [ ] Re-running `python -m src.downloader` does NOT modify existing files
- [ ] Each `_articles.json` entry has a `sentiment_score` field in `[-1.0, +1.0]`
- [ ] `pytest tests/research/test_spy_sentiment_response.py` PASSES (≥ 80% alignment)
