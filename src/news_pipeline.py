"""Orchestrate news download + FinBERT sentiment: config → SPY dates → save files."""
import argparse
import json
from datetime import date
from pathlib import Path

from src.config_loader import load_config
from src.ibkr_client import CLIENT_IDS_TO_TRY, connect_to_ibkr, disconnect
from src.news_downloader import download_news_for_date, resolve_spy_con_id
from src.sentiment_analyzer import aggregate_daily_sentiment, load_model, score_headlines
from src.types import AppConfig, DailySentiment

ARTICLES_FILENAME_TEMPLATE = "{date}_articles.json"
SENTIMENT_FILENAME_TEMPLATE = "{date}_sentiment.csv"
SENTIMENT_CSV_HEADER = "date,article_count,sentiment_score,positive_count,negative_count,neutral_count"


def write_articles_json(data_dir: Path, target_date: date, articles: list[dict]) -> Path:
    """
    Write per-article news data (including sentiment_score) to JSON.

    Skips writing if the file already exists. Returns the file path.
    """
    path = _articles_path(data_dir, target_date)
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(articles, f, indent=2, default=str)

    return path


def write_sentiment_csv(data_dir: Path, target_date: date, sentiment: DailySentiment) -> Path:
    """
    Write the daily sentiment aggregate to a CSV file.

    Skips writing if the file already exists. Returns the file path.
    """
    path = _sentiment_path(data_dir, target_date)
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(SENTIMENT_CSV_HEADER + "\n")
        f.write(
            f"{sentiment.date},{sentiment.article_count},{sentiment.sentiment_score:.6f},"
            f"{sentiment.positive_count},{sentiment.negative_count},{sentiment.neutral_count}\n"
        )

    return path


def run_news_pipeline(
    config: AppConfig,
    override_dates: list[date] | None = None,
) -> None:
    """
    Orchestrate news download and sentiment scoring for all SPY dates.

    If override_dates is provided, those dates are processed directly (useful for
    debugging a specific date without requiring SPY bar files to exist).

    Otherwise:
    1. Scan bars/SPY/ for existing CSV files → date list.
    2. Filter to dates without existing sentiment files.
    3. Connect to IBKR; resolve SPY conId once.
    4. Load sentiment model once.
    5. For each date: download headlines → score each article → aggregate → save files.
    """
    if override_dates is not None:
        pending_dates = override_dates
        print(f"Override mode: processing {len(pending_dates)} specified date(s).")
    else:
        spy_bar_dir = config.data_dir / "bars" / config.spy_symbol
        available_dates = _find_bar_dates(spy_bar_dir, config.spy_symbol)

        if not available_dates:
            print(f"No {config.spy_symbol} bar files found in {spy_bar_dir}. Run downloader first.")
            return

        pending_dates = [d for d in available_dates if not _sentiment_exists(config.data_dir, d)]
        print(f"Found {len(available_dates)} {config.spy_symbol} dates with bar data.")
        print(f"Skipping {len(available_dates) - len(pending_dates)} dates with existing sentiment files.")

    if not pending_dates:
        print("All dates already processed.")
        return

    print(f"Loading {config.sentiment_backend} model...", flush=True)
    model = load_model(config.sentiment_backend)

    spy_instruments = [i for i in config.instruments if i.symbol == config.spy_symbol]
    if not spy_instruments:
        raise ValueError(f"spy_symbol '{config.spy_symbol}' not found in instruments config")
    spy_instrument = spy_instruments[0]

    client_ids = (
        [config.news_ibkr_client_id]
        if config.news_ibkr_client_id is not None
        else CLIENT_IDS_TO_TRY
    )
    print(f"Connecting to IBKR on {config.ibkr_host}:{config.ibkr_port} (client_id={client_ids[0] if len(client_ids) == 1 else client_ids})...", flush=True)
    client = connect_to_ibkr(config.ibkr_host, config.ibkr_port, client_ids)
    print("Connected successfully.", flush=True)

    try:
        con_id = resolve_spy_con_id(client, spy_instrument)
        print(f"Resolved {config.spy_symbol} conId: {con_id}", flush=True)

        for target_date in pending_dates:
            print(f"[{target_date}] Fetching news for {config.spy_symbol} (conId={con_id})...", flush=True)
            try:
                news_items = download_news_for_date(
                    client=client,
                    symbol=config.spy_symbol,
                    con_id=con_id,
                    provider_codes=config.news_provider_codes,
                    target_date=target_date,
                )
            except PermissionError as exc:
                print(f"  → WARNING: {exc} — skipping date.")
                continue

            # Score each article individually (store per-article score)
            per_article_scores = score_headlines(
                model,
                [item.headline for item in news_items],
                backend=config.sentiment_backend,
            ) if news_items else []

            # Build article dicts with per-article sentiment_score
            article_dicts = [
                {
                    "article_id": item.article_id,
                    "provider_code": item.provider_code,
                    "timestamp": item.timestamp.isoformat(),
                    "headline": item.headline,
                    "symbol": item.symbol,
                    "sentiment_score": round(score, 6),
                }
                for item, score in zip(news_items, per_article_scores)
            ]

            daily_sentiment = aggregate_daily_sentiment(
                model, config.sentiment_backend, news_items, target_date
            )

            articles_path = write_articles_json(config.data_dir, target_date, article_dicts)
            sentiment_path = write_sentiment_csv(config.data_dir, target_date, daily_sentiment)

            headline_count = len(news_items)
            print(f"  → {headline_count} headlines found")
            if headline_count > 0:
                print(f"  → Sentiment score: {daily_sentiment.sentiment_score:+.2f} "
                      f"({daily_sentiment.positive_count} positive, "
                      f"{daily_sentiment.negative_count} negative, "
                      f"{daily_sentiment.neutral_count} neutral)")
            print(f"  → Saved: {articles_path}")
            print(f"  → Saved: {sentiment_path}")

    finally:
        disconnect(client)


def _find_bar_dates(spy_bar_dir: Path, symbol: str) -> list[date]:
    """Return sorted list of dates for which bar CSV files exist."""
    if not spy_bar_dir.exists():
        return []

    dates = []
    for csv_file in spy_bar_dir.glob(f"*_{symbol}.csv"):
        date_str = csv_file.stem.split(f"_{symbol}")[0]
        try:
            dates.append(date.fromisoformat(date_str))
        except ValueError:
            continue

    return sorted(dates)


def _sentiment_exists(data_dir: Path, target_date: date) -> bool:
    return _sentiment_path(data_dir, target_date).exists()


def _articles_path(data_dir: Path, target_date: date) -> Path:
    return data_dir / "news" / ARTICLES_FILENAME_TEMPLATE.format(date=target_date)


def _sentiment_path(data_dir: Path, target_date: date) -> Path:
    return data_dir / "news" / SENTIMENT_FILENAME_TEMPLATE.format(date=target_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download IBKR news and compute sentiment")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Process a specific date (bypasses SPY bar file scanning)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    override = [args.date] if args.date else None
    run_news_pipeline(cfg, override_dates=override)
