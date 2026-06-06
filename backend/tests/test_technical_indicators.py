import os
import sys
import unittest

import pandas as pd


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import technical_indicators


class TechnicalIndicatorsTests(unittest.TestCase):
    def _build_ohlcv(self, rows=260):
        index = pd.date_range("2024-01-01", periods=rows, freq="D")
        close = pd.Series([100 + (i * 0.4) + ((i % 5) * 0.2) for i in range(rows)], index=index)
        return pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": [1000 + (i * 25) for i in range(rows)],
            },
            index=index,
        )

    def test_calculate_technical_indicators_returns_expected_shape(self):
        frame = self._build_ohlcv()

        result = technical_indicators.calculate_technical_indicators(frame)

        self.assertIn("rsi", result)
        self.assertIn("macd", result)
        self.assertIn("ema20", result)
        self.assertIn("ema50", result)
        self.assertIn("ema200", result)
        self.assertIn("bollinger_bands", result)
        self.assertIn("atr", result)
        self.assertIn("adx", result)
        self.assertIn("vwap", result)
        self.assertEqual(len(result["rsi"]["series"]), len(frame))
        self.assertEqual(len(result["macd"]["macd"]["series"]), len(frame))
        self.assertIsInstance(result["ema20"]["value"], float)
        self.assertIsInstance(result["ema50"]["value"], float)
        self.assertIsInstance(result["ema200"]["value"], float)
        self.assertIsInstance(result["vwap"]["value"], float)

    def test_calculate_technical_indicators_accepts_mixed_case_columns(self):
        frame = self._build_ohlcv().rename(
            columns={
                "open": "Open",
                "high": "HIGH",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )

        result = technical_indicators.calculate_technical_indicators(frame)

        self.assertIn("bollinger_bands", result)
        self.assertIn("adx", result)

    def test_calculate_technical_indicators_rejects_missing_columns(self):
        frame = self._build_ohlcv().drop(columns=["volume"])

        with self.assertRaisesRegex(ValueError, "missing required columns"):
            technical_indicators.calculate_technical_indicators(frame)

    def test_calculate_technical_indicators_rejects_empty_frame(self):
        frame = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        with self.assertRaisesRegex(ValueError, "at least one row"):
            technical_indicators.calculate_technical_indicators(frame)


if __name__ == "__main__":
    unittest.main()
