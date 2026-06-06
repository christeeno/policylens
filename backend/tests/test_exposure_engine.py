import json
import os
import sys
import tempfile
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import exposure_engine


class ExposureEngineTests(unittest.TestCase):
    def test_calculate_exposure_matches_example_bucket(self):
        company = {
            "ticker": "PRAJIND",
            "name": "Praj Industries",
            "segments": [
                {
                    "name": "Bioenergy",
                    "sector": "energy_transition",
                    "revenue_share": 0.82,
                    "policy_sensitivity": 0.95,
                    "annual_report_signal": 0.92,
                },
                {
                    "name": "Engineering",
                    "sector": "industrial_capex",
                    "revenue_share": 0.10,
                    "policy_sensitivity": 0.55,
                    "annual_report_signal": 0.52,
                },
                {
                    "name": "HiPurity and Others",
                    "sector": "industrial_specialty",
                    "revenue_share": 0.08,
                    "policy_sensitivity": 0.35,
                    "annual_report_signal": 0.30,
                },
            ],
        }

        result = exposure_engine.calculate_exposure(company)

        self.assertEqual(result["score_1_to_5"], 5)
        self.assertAlmostEqual(result["raw_score"], 0.8132, places=4)
        self.assertEqual(result["dominant_sector"], "energy_transition")

    def test_calculate_exposure_defaults_to_minimum_without_segments(self):
        result = exposure_engine.calculate_exposure({"ticker": "EMPTY", "name": "No Segments Ltd"})

        self.assertEqual(result["score_1_to_5"], 1)
        self.assertEqual(result["raw_score"], 0.0)
        self.assertIn("defaulting to minimum exposure", result["explanation"])

    def test_refresh_exposure_scores_writes_materialized_snapshot(self):
        fundamentals = {
            "companies": [
                {
                    "ticker": "SBIN",
                    "name": "State Bank of India",
                    "segments": [
                        {
                            "name": "Retail Banking",
                            "sector": "banking",
                            "revenue_share": 0.45,
                            "policy_sensitivity": 0.82,
                            "annual_report_signal": 0.78,
                        },
                        {
                            "name": "Corporate Banking",
                            "sector": "banking",
                            "revenue_share": 0.35,
                            "policy_sensitivity": 0.80,
                            "annual_report_signal": 0.72,
                        },
                        {
                            "name": "Treasury",
                            "sector": "banking",
                            "revenue_share": 0.20,
                            "policy_sensitivity": 0.58,
                            "annual_report_signal": 0.60,
                        },
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            fundamentals_path = os.path.join(temp_dir, "fundamentals.json")
            output_path = os.path.join(temp_dir, "scores.json")

            with open(fundamentals_path, "w", encoding="utf-8") as handle:
                json.dump(fundamentals, handle)

            payload = exposure_engine.refresh_exposure_scores(
                fundamentals_file=fundamentals_path,
                output_file=output_path,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                written = json.load(handle)

        self.assertIn("refreshed_at", payload)
        self.assertEqual(payload["scores"]["SBIN"]["score_1_to_5"], 4)
        self.assertEqual(written["scores"]["SBIN"]["dominant_sector"], "banking")
        self.assertEqual(written["source_file"], fundamentals_path)

    def test_get_exposure_score_returns_fallback_for_missing_ticker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scores.json")
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump({"scores": {}}, handle)

            score, details = exposure_engine.get_exposure_score(
                "UNKNOWN",
                fallback=2,
                scores_file=output_path,
            )

        self.assertEqual(score, 2)
        self.assertIsNone(details)


if __name__ == "__main__":
    unittest.main()
