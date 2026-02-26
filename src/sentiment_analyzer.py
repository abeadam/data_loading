"""Sentiment analysis using FinBERT or VADER. Pure input/output — no file I/O."""
from datetime import date
from typing import Any

from src.types import DailySentiment, NewsItem

SENTIMENT_THRESHOLD_POSITIVE = 0.0
SENTIMENT_THRESHOLD_NEGATIVE = 0.0


def load_model(backend: str) -> Any:
    """
    Load and return the sentiment model for the given backend.

    backend="finbert": loads ProsusAI/finbert via HuggingFace transformers pipeline.
    backend="vader": loads VADER SentimentIntensityAnalyzer.
    """
    if backend == "finbert":
        from transformers import pipeline

        print("Loading FinBERT model...", flush=True)
        return pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            top_k=None,
        )

    if backend == "vader":
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        return SentimentIntensityAnalyzer()

    raise ValueError(f"Unknown sentiment backend: '{backend}'. Must be 'finbert' or 'vader'.")


def score_headlines(model: Any, headlines: list[str], backend: str) -> list[float]:
    """
    Score a list of headlines, returning one float per headline in [-1.0, +1.0].

    FinBERT: score = positive_prob - negative_prob
    VADER: score = compound score
    """
    scores: list[float] = []

    for headline in headlines:
        if backend == "finbert":
            result = model(headline)
            # result is a list of lists: [[{label, score}, ...]]
            label_scores = {item["label"]: item["score"] for item in result[0]}
            score = label_scores.get("positive", 0.0) - label_scores.get("negative", 0.0)
        else:  # vader
            polarity = model.polarity_scores(headline)
            score = polarity["compound"]

        scores.append(score)

    return scores


def aggregate_daily_sentiment(
    model: Any,
    backend: str,
    news_items: list[NewsItem],
    target_date: date,
) -> DailySentiment:
    """
    Score all news items and aggregate into a DailySentiment for one trading day.

    The daily sentiment_score is the mean of per-article scores.
    Returns a zero-score DailySentiment if news_items is empty.
    """
    if not news_items:
        return DailySentiment(
            date=target_date,
            article_count=0,
            sentiment_score=0.0,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
        )

    headlines = [item.headline for item in news_items]
    per_article_scores = score_headlines(model, headlines, backend)

    positive_count = sum(1 for s in per_article_scores if s > SENTIMENT_THRESHOLD_POSITIVE)
    negative_count = sum(1 for s in per_article_scores if s < SENTIMENT_THRESHOLD_NEGATIVE)
    neutral_count = len(per_article_scores) - positive_count - negative_count

    mean_score = sum(per_article_scores) / len(per_article_scores)

    return DailySentiment(
        date=target_date,
        article_count=len(news_items),
        sentiment_score=mean_score,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
    )
