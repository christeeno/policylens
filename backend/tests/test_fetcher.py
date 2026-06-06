import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fetcher


class FetcherTests(unittest.TestCase):
    def test_infer_article_class_marks_preview(self):
        result = fetcher.infer_article_class(
            "Reserve Bank of India to announce its bi-monthly Monetary Policy today.",
            source_type="NEWS",
            publisher="News On AIR",
        )
        self.assertEqual(result["article_class"], "PREVIEW")
        self.assertFalse(result["is_actionable"])

    def test_infer_article_class_marks_news_report(self):
        result = fetcher.infer_article_class(
            "Reuters: RBI raises repo rate by 50 basis points.",
            source_type="NEWS",
            publisher="Reuters",
        )
        self.assertEqual(result["article_class"], "NEWS_REPORT")
        self.assertTrue(result["is_actionable"])

    def test_infer_article_class_marks_official_policy(self):
        result = fetcher.infer_article_class(
            "SEBI revises framework for margin obligations.",
            source_type="OFFICIAL",
            publisher="Securities and Exchange Board of India",
        )
        self.assertEqual(result["article_class"], "OFFICIAL_POLICY")
        self.assertTrue(result["is_actionable"])

    def test_infer_article_class_marks_personnel_update_other(self):
        result = fetcher.infer_article_class(
            "Shri Swaminathan Janakiraman re-appointed as RBI Deputy Governor.",
            source_type="OFFICIAL",
            publisher="Reserve Bank of India",
        )

        self.assertEqual(result["article_class"], "OTHER")
        self.assertFalse(result["is_actionable"])

    def test_infer_article_class_marks_market_reaction(self):
        result = fetcher.infer_article_class(
            "Sensex rallies after RBI policy decision lifts banking stocks.",
            source_type="NEWS",
            publisher="Moneycontrol",
        )
        self.assertEqual(result["article_class"], "MARKET_REACTION")
        self.assertFalse(result["is_actionable"])

    def test_dedupe_prefers_official_item_over_news_duplicate(self):
        official = {
            "id": "1",
            "title": "RBI raises repo rate by 50 basis points",
            "date": "2022-08-05T10:00:00+00:00",
            "link": "https://rbi.org.in/fallback-1",
            "source_type": "OFFICIAL",
        }
        news = {
            "id": "2",
            "title": "RBI raises repo rate by 50 basis points",
            "date": "2022-08-05T12:00:00+00:00",
            "link": "https://example.com/rbi-rate-story",
            "source_type": "NEWS",
        }

        result = fetcher._dedupe_items([news, official])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_type"], "OFFICIAL")

    def test_fallback_feed_includes_source_metadata(self):
        items = fetcher.get_fallback_feed()
        self.assertTrue(items)
        self.assertEqual(items[0]["source_type"], "OFFICIAL")
        self.assertIn("article_class", items[0])
        self.assertIn("publisher", items[0])


if __name__ == "__main__":
    unittest.main()
