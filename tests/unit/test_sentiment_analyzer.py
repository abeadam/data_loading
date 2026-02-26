"""Tests for src/sentiment_analyzer.py — pure logic, mock model responses."""
from datetime import date, datetime
from unittest.mock import MagicMock



def make_news_item(article_id: str, headline: str, ts: datetime | None = None):
    from src.types import NewsItem

    return NewsItem(
        article_id=article_id,
        provider_code="BZ",
        timestamp=ts or datetime(2024, 1, 2, 10, 30, 0),
        headline=headline,
        body=None,
        symbol="SPY",
    )


class TestScoreHeadlinesFinbert:
    def test_positive_headline_returns_positive_score(self):
        """FinBERT pipeline output: positive_prob > negative_prob → positive score."""
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        mock_model.return_value = [[
            {"label": "positive", "score": 0.85},
            {"label": "negative", "score": 0.05},
            {"label": "neutral", "score": 0.10},
        ]]

        scores = score_headlines(mock_model, ["SPY beats expectations"], backend="finbert")
        assert len(scores) == 1
        assert abs(scores[0] - (0.85 - 0.05)) < 1e-6  # positive_prob - negative_prob

    def test_negative_headline_returns_negative_score(self):
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        mock_model.return_value = [[
            {"label": "positive", "score": 0.05},
            {"label": "negative", "score": 0.80},
            {"label": "neutral", "score": 0.15},
        ]]

        scores = score_headlines(mock_model, ["Market crash fears mount"], backend="finbert")
        assert scores[0] < 0

    def test_neutral_headline_near_zero(self):
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        mock_model.return_value = [[
            {"label": "positive", "score": 0.20},
            {"label": "negative", "score": 0.20},
            {"label": "neutral", "score": 0.60},
        ]]

        scores = score_headlines(mock_model, ["Trading volume normal today"], backend="finbert")
        assert abs(scores[0]) < 0.01  # 0.20 - 0.20 = 0.0

    def test_score_in_valid_range(self):
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        mock_model.return_value = [[
            {"label": "positive", "score": 1.0},
            {"label": "negative", "score": 0.0},
            {"label": "neutral", "score": 0.0},
        ]]

        scores = score_headlines(mock_model, ["Strong bull run"], backend="finbert")
        assert -1.0 <= scores[0] <= 1.0

    def test_multiple_headlines_returns_multiple_scores(self):
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        # Return separate list for each headline call
        mock_model.side_effect = [
            [[{"label": "positive", "score": 0.9}, {"label": "negative", "score": 0.05}, {"label": "neutral", "score": 0.05}]],
            [[{"label": "positive", "score": 0.1}, {"label": "negative", "score": 0.8}, {"label": "neutral", "score": 0.1}]],
        ]

        scores = score_headlines(mock_model, ["Bullish news", "Bearish news"], backend="finbert")
        assert len(scores) == 2
        assert scores[0] > 0
        assert scores[1] < 0


class TestScoreHeadlinesVader:
    def test_vader_returns_compound_score(self):
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        mock_model.polarity_scores.return_value = {"compound": 0.65, "pos": 0.5, "neg": 0.1, "neu": 0.4}

        scores = score_headlines(mock_model, ["Great news today"], backend="vader")
        assert len(scores) == 1
        assert abs(scores[0] - 0.65) < 1e-6

    def test_vader_negative_returns_negative_compound(self):
        from src.sentiment_analyzer import score_headlines

        mock_model = MagicMock()
        mock_model.polarity_scores.return_value = {"compound": -0.45, "pos": 0.05, "neg": 0.6, "neu": 0.35}

        scores = score_headlines(mock_model, ["Bad earnings report"], backend="vader")
        assert scores[0] < 0


class TestAggregateDailySentiment:
    def test_empty_news_returns_zero_sentiment(self):
        from src.sentiment_analyzer import aggregate_daily_sentiment

        mock_model = MagicMock()
        result = aggregate_daily_sentiment(mock_model, "finbert", [], date(2024, 1, 2))

        assert result.article_count == 0
        assert result.sentiment_score == 0.0
        assert result.positive_count == 0
        assert result.negative_count == 0
        assert result.neutral_count == 0

    def test_three_items_mean_score(self):
        from src.sentiment_analyzer import aggregate_daily_sentiment

        mock_model = MagicMock()
        # Three calls: scores +0.6, -0.3, +0.1 → mean = 0.1333...
        mock_model.side_effect = [
            [[{"label": "positive", "score": 0.8}, {"label": "negative", "score": 0.2}, {"label": "neutral", "score": 0.0}]],
            [[{"label": "positive", "score": 0.1}, {"label": "negative", "score": 0.4}, {"label": "neutral", "score": 0.5}]],
            [[{"label": "positive", "score": 0.3}, {"label": "negative", "score": 0.2}, {"label": "neutral", "score": 0.5}]],
        ]

        news_items = [
            make_news_item("a1", "Great news"),   # +0.6
            make_news_item("a2", "Bad news"),     # -0.3
            make_news_item("a3", "Neutral news"), # +0.1
        ]

        result = aggregate_daily_sentiment(mock_model, "finbert", news_items, date(2024, 1, 2))

        assert result.article_count == 3
        expected_mean = (0.6 + (-0.3) + 0.1) / 3
        assert abs(result.sentiment_score - expected_mean) < 1e-6

    def test_positive_negative_neutral_counts(self):
        from src.sentiment_analyzer import aggregate_daily_sentiment

        mock_model = MagicMock()
        mock_model.side_effect = [
            [[{"label": "positive", "score": 0.9}, {"label": "negative", "score": 0.05}, {"label": "neutral", "score": 0.05}]],
            [[{"label": "positive", "score": 0.05}, {"label": "negative", "score": 0.9}, {"label": "neutral", "score": 0.05}]],
            [[{"label": "positive", "score": 0.1}, {"label": "negative", "score": 0.1}, {"label": "neutral", "score": 0.8}]],
        ]

        news_items = [
            make_news_item("a1", "Positive"),
            make_news_item("a2", "Negative"),
            make_news_item("a3", "Neutral"),
        ]

        result = aggregate_daily_sentiment(mock_model, "finbert", news_items, date(2024, 1, 2))

        assert result.positive_count == 1
        assert result.negative_count == 1
        assert result.neutral_count == 1

    def test_date_preserved_in_result(self):
        from src.sentiment_analyzer import aggregate_daily_sentiment

        mock_model = MagicMock()
        result = aggregate_daily_sentiment(mock_model, "finbert", [], date(2024, 8, 1))
        assert result.date == date(2024, 8, 1)
