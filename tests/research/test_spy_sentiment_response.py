"""
SPY Sentiment → 30-Second Price Response Analysis

Research test: asserts that SPY's 30-second price direction matches per-article
FinBERT sentiment in >= 80% of eligible intraday news items.

Requires on-disk data:
  - {data_dir}/news/*_articles.json (with sentiment_score per article)
  - {data_dir}/bars/SPY/*_SPY.csv

Run with: pytest tests/research/test_spy_sentiment_response.py -v
"""
import json
from datetime import date, datetime, timezone
from math import copysign
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ALIGNMENT_THRESHOLD_PCT = 80.0
NEAR_NEUTRAL_THRESHOLD = 0.05
BARS_FOR_30_SECONDS = 6          # 6 × 5-second bars = 30 seconds
ET_TIMEZONE = ZoneInfo("America/New_York")
RTH_START_HOUR = 9
RTH_START_MINUTE = 30
RTH_END_HOUR = 15
RTH_END_MINUTE = 59
RTH_END_SECOND = 30              # Last eligible start: 15:59:30 ET (30 seconds remain)

CONFIG_PATH = Path(__file__).parent.parent.parent / "src" / "config.yaml"


def _load_config():
    """Load AppConfig from the default config.yaml."""
    from src.config_loader import load_config

    return load_config(CONFIG_PATH)


def _load_all_articles(news_dir: Path) -> list[dict]:
    """Load all articles from *_articles.json files in news_dir."""
    articles = []
    for articles_file in sorted(news_dir.glob("*_articles.json")):
        with open(articles_file) as f:
            articles.extend(json.load(f))
    return articles


def _load_spy_bars_for_date(bars_spy_dir: Path, target_date: date) -> dict[int, float]:
    """
    Load SPY bars for a specific date and return a dict mapping timestamp → close price.
    Returns an empty dict if the file does not exist.
    """
    csv_file = bars_spy_dir / f"{target_date}_SPY.csv"
    if not csv_file.exists():
        return {}

    bars: dict[int, float] = {}
    import csv

    with open(csv_file, newline="") as f:
        for row in csv.DictReader(f):
            bars[int(row["timestamp"])] = float(row["close"])

    return bars


def _is_within_rth(timestamp_utc: datetime) -> bool:
    """Return True if the UTC timestamp falls within regular trading hours (ET)."""
    et_time = timestamp_utc.astimezone(ET_TIMEZONE)
    rth_start = et_time.replace(hour=RTH_START_HOUR, minute=RTH_START_MINUTE, second=0, microsecond=0)
    rth_end = et_time.replace(hour=RTH_END_HOUR, minute=RTH_END_MINUTE, second=RTH_END_SECOND, microsecond=0)
    return rth_start <= et_time <= rth_end


def _find_bar_at_or_after(sorted_timestamps: list[int], target_ts: int) -> int | None:
    """Binary search for the first bar timestamp >= target_ts."""
    lo, hi = 0, len(sorted_timestamps) - 1
    result = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_timestamps[mid] >= target_ts:
            result = sorted_timestamps[mid]
            hi = mid - 1
        else:
            lo = mid + 1
    return result


@pytest.mark.research
def test_sentiment_price_alignment():
    """Assert >= 80% of eligible articles have SPY price movement aligned with sentiment."""
    config = _load_config()
    news_dir = config.data_dir / "news"
    bars_spy_dir = config.data_dir / "bars" / config.spy_symbol

    if not news_dir.exists():
        pytest.skip(f"News directory not found: {news_dir}")
    if not bars_spy_dir.exists():
        pytest.skip(f"SPY bars directory not found: {bars_spy_dir}")

    all_articles = _load_all_articles(news_dir)
    if not all_articles:
        pytest.skip("No articles.json files found — run news_pipeline first")

    items_tested = 0
    items_aligned = 0
    details = []

    # Cache bars per date to avoid re-reading the same file
    _bar_cache: dict[date, dict[int, float]] = {}

    for article in all_articles:
        sentiment_score = article.get("sentiment_score")
        if sentiment_score is None:
            continue  # articles without stored score are skipped

        # Skip near-neutral articles (ambiguous signal)
        if abs(sentiment_score) < NEAR_NEUTRAL_THRESHOLD:
            continue

        # Parse article timestamp (ISO 8601 UTC)
        timestamp_str = article.get("timestamp", "")
        try:
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            article_ts = datetime.fromisoformat(timestamp_str)
            if article_ts.tzinfo is None:
                article_ts = article_ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        # Skip articles outside regular trading hours
        if not _is_within_rth(article_ts):
            continue

        # Determine the article's date and load SPY bars
        article_date = article_ts.astimezone(ET_TIMEZONE).date()
        if article_date not in _bar_cache:
            _bar_cache[article_date] = _load_spy_bars_for_date(bars_spy_dir, article_date)
        bars = _bar_cache[article_date]

        if not bars:
            continue  # No SPY bars for this date

        sorted_ts = sorted(bars.keys())
        article_unix_ts = int(article_ts.timestamp())

        # Find first bar at or after article timestamp
        bar_open_ts = _find_bar_at_or_after(sorted_ts, article_unix_ts)
        if bar_open_ts is None:
            continue

        # Find bar 30 seconds later (6 bars ahead)
        open_idx = sorted_ts.index(bar_open_ts)
        close_idx = open_idx + BARS_FOR_30_SECONDS
        if close_idx >= len(sorted_ts):
            continue  # Not enough bars remaining in session

        bar_close_ts = sorted_ts[close_idx]
        spy_bar_open = bars[bar_open_ts]
        spy_bar_close_30s = bars[bar_close_ts]
        price_change = spy_bar_close_30s - spy_bar_open

        if price_change == 0.0:
            continue  # No movement — skip (indeterminate alignment)

        aligned = (copysign(1, sentiment_score) == copysign(1, price_change))

        items_tested += 1
        if aligned:
            items_aligned += 1

        details.append({
            "article_id": article.get("article_id", "?"),
            "timestamp": article_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "sentiment": sentiment_score,
            "price_change": price_change,
            "aligned": aligned,
        })

    if items_tested == 0:
        pytest.skip("No eligible articles found — need RTH articles with |sentiment| >= 0.05")

    alignment_pct = items_aligned / items_tested * 100

    # Print analysis table
    print("\nSPY Sentiment → 30-Second Price Response Analysis")
    print("=" * 51)
    print(f"Articles tested:  {items_tested:>4d}  (excluded near-neutral and outside RTH)")
    print(f"Articles aligned: {items_aligned:>4d}")
    status = "✅" if alignment_pct >= ALIGNMENT_THRESHOLD_PCT else "❌"
    print(f"Alignment rate:   {alignment_pct:.1f}%  {status}  (threshold: {ALIGNMENT_THRESHOLD_PCT:.1f}%)")
    print()
    print(f"{'Article ID':<14} {'Timestamp':<21} {'Sentiment':>9} {'Price Chg':>9} {'Aligned'}")
    print(f"{'-'*14} {'-'*21} {'-'*9} {'-'*9} {'-'*7}")
    for row in details[:20]:  # Show first 20 rows
        aligned_str = "YES" if row["aligned"] else "NO"
        print(
            f"{row['article_id']:<14} {row['timestamp']:<21} "
            f"{row['sentiment']:>+9.2f} {row['price_change']:>+9.4f} {aligned_str}"
        )
    if len(details) > 20:
        print(f"... and {len(details) - 20} more rows")

    assert alignment_pct >= ALIGNMENT_THRESHOLD_PCT, (
        f"Sentiment-price alignment {alignment_pct:.1f}% is below the required {ALIGNMENT_THRESHOLD_PCT:.1f}% threshold. "
        f"({items_aligned}/{items_tested} articles aligned)"
    )
