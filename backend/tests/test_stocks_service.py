import os
import sys
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
import stocks_service


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows
        self.empty = not rows

    def iterrows(self):
        for item in self._rows:
            yield item["index"], item["row"]


class StocksServiceTests(unittest.TestCase):
    def setUp(self):
        stocks_service._CACHE.clear()

    def test_normalize_ticker_supports_nse_stock(self):
        self.assertEqual(stocks_service.normalize_ticker("tcs"), "TCS.NS")
        self.assertEqual(stocks_service.normalize_ticker("INFY.NS"), "INFY.NS")

    def test_normalize_ticker_supports_nifty_index(self):
        self.assertEqual(stocks_service.normalize_ticker("NIFTY 50"), "^NSEI")
        self.assertEqual(stocks_service.normalize_ticker("banknifty"), "^NSEBANK")

    @patch("stocks_service.yf.Ticker")
    def test_fetch_stock_history_returns_ohlcv_rows(self, mock_ticker_class):
        history_frame = FakeDataFrame(
            [
                {
                    "index": datetime(2026, 6, 1),
                    "row": {"Open": 100.0, "High": 110.0, "Low": 99.5, "Close": 108.25, "Volume": 123456},
                },
                {
                    "index": datetime(2026, 6, 2),
                    "row": {"Open": 108.25, "High": 111.0, "Low": 107.0, "Close": 109.75, "Volume": 150000},
                },
            ]
        )
        ticker = Mock()
        ticker.history.return_value = history_frame
        ticker.fast_info = {"currency": "INR"}
        mock_ticker_class.return_value = ticker

        result = stocks_service.fetch_stock_history("RELIANCE")

        self.assertEqual(result["ticker"], "RELIANCE.NS")
        self.assertEqual(result["currency"], "INR")
        self.assertEqual(len(result["ohlcv"]), 2)
        self.assertEqual(result["ohlcv"][0]["date"], "2026-06-01")
        self.assertEqual(result["ohlcv"][0]["close"], 108.25)
        self.assertEqual(result["ohlcv"][1]["volume"], 150000)

    @patch("stocks_service.yf.Ticker")
    def test_fetch_stock_history_uses_cache(self, mock_ticker_class):
        history_frame = FakeDataFrame(
            [{"index": datetime(2026, 6, 1), "row": {"Open": 1, "High": 2, "Low": 0.5, "Close": 1.5, "Volume": 10}}]
        )
        ticker = Mock()
        ticker.history.return_value = history_frame
        ticker.fast_info = {}
        mock_ticker_class.return_value = ticker

        first = stocks_service.fetch_stock_history("SBIN")
        second = stocks_service.fetch_stock_history("SBIN")

        self.assertEqual(first, second)
        ticker.history.assert_called_once()

    @patch("stocks_service.time.sleep", return_value=None)
    @patch("stocks_service.yf.Ticker")
    def test_fetch_stock_history_retries_transient_errors(self, mock_ticker_class, _mock_sleep):
        history_frame = FakeDataFrame(
            [{"index": datetime(2026, 6, 1), "row": {"Open": 10, "High": 12, "Low": 9, "Close": 11, "Volume": 25}}]
        )
        ticker = Mock()
        ticker.history.side_effect = [RuntimeError("temporary"), RuntimeError("temporary"), history_frame]
        ticker.fast_info = {}
        mock_ticker_class.return_value = ticker

        result = stocks_service.fetch_stock_history("ITC")

        self.assertEqual(result["ticker"], "ITC.NS")
        self.assertEqual(ticker.history.call_count, 3)

    def test_build_history_request_rejects_partial_date_range(self):
        with self.assertRaises(stocks_service.StockDataError):
            stocks_service.build_history_request("TCS", start="2026-01-01")


class StocksApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    @patch("main.fetch_stock_history")
    def test_history_endpoint_returns_payload(self, mock_fetch_stock_history):
        mock_fetch_stock_history.return_value = {
            "ticker": "TCS.NS",
            "interval": "1d",
            "period": "6mo",
            "start": None,
            "end": None,
            "currency": "INR",
            "ohlcv": [
                {
                    "date": "2026-06-01",
                    "open": 100.0,
                    "high": 102.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 1000,
                }
            ],
        }

        response = self.client.get("/api/stocks/TCS/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ticker"], "TCS.NS")

    @patch("main.fetch_stock_history", side_effect=stocks_service.StockNotFoundError("No data found"))
    def test_history_endpoint_maps_not_found_errors(self, _mock_fetch_stock_history):
        response = self.client.get("/api/stocks/UNKNOWN/history")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No data found")

    @patch("main.fetch_stock_history", side_effect=stocks_service.StockDataError("Bad request"))
    def test_history_endpoint_maps_validation_errors(self, _mock_fetch_stock_history):
        response = self.client.get("/api/stocks/TCS/history?interval=5m")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Bad request")


if __name__ == "__main__":
    unittest.main()
