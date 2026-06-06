import os
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scorer


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def invoke(self, _prompt):
        self.calls += 1
        return self.response


class PolicyAnalysisTests(unittest.TestCase):
    def test_analyze_policy_returns_ranked_sector_impacts(self):
        fake_llm = FakeLLM(
            {
                "summary": "The RBI increased the repo rate by 50 basis points.",
                "ministry": "Reserve Bank of India",
                "key_change": "Policy repo rate increased by 50 basis points.",
                "policy_type": "RATE_CHANGE",
                "overall_confidence_score": 0.91,
                "overall_reasoning": "Banks and rate-sensitive sectors react first to repo changes.",
                "sector_impacts": [
                    {
                        "sector": "banking",
                        "confidence_score": 0.96,
                        "impact_direction": "POSITIVE",
                        "impact_strength": "HIGH",
                        "impact_strength_score": 0.94,
                        "reasoning": "Repo transmission directly changes lending spreads.",
                        "evidence": "repo rate increased by 50 basis points",
                        "is_supported_sector": True,
                    },
                    {
                        "sector": "real_estate",
                        "confidence_score": 0.89,
                        "impact_direction": "NEGATIVE",
                        "impact_strength": "HIGH",
                        "impact_strength_score": 0.87,
                        "reasoning": "Higher mortgage costs can reduce housing demand.",
                        "evidence": "to contain inflationary pressures",
                        "is_supported_sector": True,
                    },
                    {
                        "sector": "auto",
                        "confidence_score": 0.74,
                        "impact_direction": "NEGATIVE",
                        "impact_strength": "MEDIUM",
                        "impact_strength_score": 0.63,
                        "reasoning": "Vehicle financing becomes more expensive.",
                        "evidence": "policy repo rate stands adjusted upward",
                        "is_supported_sector": True,
                    },
                ],
            }
        )

        result = scorer.analyze_policy(
            "The RBI has increased the repo rate by 50 basis points to tackle inflation.",
            llm=fake_llm,
        )

        self.assertEqual(fake_llm.calls, 1)
        self.assertEqual(result["sectors"], ["banking", "real_estate", "auto"])
        self.assertEqual(result["confidence"], "HIGH")
        self.assertEqual(result["policy_type"], "RATE_CHANGE")
        self.assertEqual(result["sector_details"][0]["impact_direction"], "POSITIVE")
        self.assertEqual(result["sector_details"][1]["impact_strength"], "HIGH")

    def test_analyze_policy_normalizes_unseen_sector_labels(self):
        result = scorer.analyze_policy(
            "The cabinet approved a domestic defence procurement push with local sourcing mandates.",
            llm=FakeLLM(
                {
                    "summary": "The cabinet approved a domestic defence sourcing push.",
                    "ministry": "Cabinet Committee on Security",
                    "key_change": "Domestic sourcing norms were tightened for defence procurement.",
                    "policy_type": "APPROVAL",
                    "overall_confidence_score": 0.68,
                    "overall_reasoning": "Defence procurement is primary and infrastructure is secondary.",
                    "sector_impacts": [
                        {
                            "sector": "Defence Manufacturing",
                            "confidence_score": 0.81,
                            "impact_direction": "POSITIVE",
                            "impact_strength": "HIGH",
                            "impact_strength_score": 0.88,
                            "reasoning": "The policy directly expands local procurement for defence platforms.",
                            "evidence": "domestic defence procurement",
                            "is_supported_sector": False,
                        },
                        {
                            "sector": "Infrastructure",
                            "confidence_score": 0.55,
                            "impact_direction": "POSITIVE",
                            "impact_strength": "LOW",
                            "impact_strength_score": 0.31,
                            "reasoning": "Some logistics and buildout is also implied.",
                            "evidence": "capacity expansion",
                            "is_supported_sector": True,
                        },
                    ],
                }
            ),
        )

        self.assertEqual(result["sectors"], ["defence_manufacturing", "infrastructure"])
        self.assertFalse(result["sector_details"][0]["is_supported_sector"])
        self.assertTrue(result["sector_details"][1]["is_supported_sector"])

    def test_analyze_policy_returns_safe_fallback_when_response_is_invalid(self):
        result = scorer.analyze_policy(
            "A broad administrative circular was issued.",
            llm=FakeLLM("not-json"),
        )

        self.assertEqual(result["sectors"], [])
        self.assertEqual(result["confidence"], "LOW")
        self.assertEqual(result["confidence_score"], 0.0)
        self.assertEqual(result["sector_details"], [])

    def test_map_sectors_remains_compatible_wrapper(self):
        result = scorer.map_sectors(
            "The RBI has increased the repo rate by 50 basis points.",
            llm=FakeLLM(
                {
                    "summary": "Repo rate hiked.",
                    "ministry": "RBI",
                    "key_change": "Rate increased.",
                    "policy_type": "RATE_CHANGE",
                    "overall_confidence_score": 0.8,
                    "overall_reasoning": "Banks are the first-order impact.",
                    "sector_impacts": [
                        {
                            "sector": "banking",
                            "confidence_score": 0.8,
                            "impact_direction": "POSITIVE",
                            "impact_strength": "HIGH",
                            "impact_strength_score": 0.9,
                            "reasoning": "Banks are directly affected.",
                            "evidence": "repo rate",
                            "is_supported_sector": True,
                        }
                    ],
                }
            ),
        )

        self.assertEqual(result["sectors"], ["banking"])

    @patch("scorer.resolve_exposure")
    @patch("scorer._build_stock_tasks")
    def test_score_all_stocks_is_deterministic(self, mock_build_stock_tasks, mock_resolve_exposure):
        mock_build_stock_tasks.return_value = (
            [
                {
                    "ticker": "AAA",
                    "name": "Alpha Bank",
                    "type": "Private",
                    "base_exposure": 5,
                    "rate_sensitivity": 3,
                    "matched_sectors": ["banking"],
                    "matched_sector_labels": ["Banking"],
                    "source_indices": ["NIFTY BANK"],
                    "sector_impacts": [
                        {
                            "sector": "banking",
                            "confidence_score": 0.95,
                            "impact_direction": "POSITIVE",
                            "impact_strength": "HIGH",
                            "impact_strength_score": 0.95,
                            "reasoning": "Banks are direct beneficiaries of wider spreads.",
                        }
                    ],
                },
                {
                    "ticker": "BBB",
                    "name": "Beta Bank",
                    "type": "Private",
                    "base_exposure": 4,
                    "rate_sensitivity": 2,
                    "matched_sectors": ["banking"],
                    "matched_sector_labels": ["Banking"],
                    "source_indices": ["NIFTY BANK"],
                    "sector_impacts": [
                        {
                            "sector": "banking",
                            "confidence_score": 0.95,
                            "impact_direction": "POSITIVE",
                            "impact_strength": "HIGH",
                            "impact_strength_score": 0.95,
                            "reasoning": "Banks are direct beneficiaries of wider spreads.",
                        }
                    ],
                },
                {
                    "ticker": "CCC",
                    "name": "Gamma Bank",
                    "type": "Private",
                    "base_exposure": 3,
                    "rate_sensitivity": 1,
                    "matched_sectors": ["banking"],
                    "matched_sector_labels": ["Banking"],
                    "source_indices": ["NIFTY BANK"],
                    "sector_impacts": [
                        {
                            "sector": "banking",
                            "confidence_score": 0.95,
                            "impact_direction": "POSITIVE",
                            "impact_strength": "HIGH",
                            "impact_strength_score": 0.95,
                            "reasoning": "Banks are direct beneficiaries of wider spreads.",
                        }
                    ],
                },
            ],
            {
                "banking": {
                    "sector": "banking",
                    "confidence_score": 0.95,
                    "impact_direction": "POSITIVE",
                    "impact_strength": "HIGH",
                    "impact_strength_score": 0.95,
                    "reasoning": "Banks are direct beneficiaries of wider spreads.",
                }
            },
        )
        mock_resolve_exposure.side_effect = lambda ticker, stock_data: {
            "AAA": (5, {"ticker": "AAA"}),
            "BBB": (4, {"ticker": "BBB"}),
            "CCC": (2, {"ticker": "CCC"}),
        }[ticker]

        policy_analysis = {
            "policy_type": "RATE_CHANGE",
            "sector_details": [
                {
                    "sector": "banking",
                    "confidence_score": 0.95,
                    "impact_direction": "POSITIVE",
                    "impact_strength": "HIGH",
                    "impact_strength_score": 0.95,
                    "reasoning": "Banks are direct beneficiaries of wider spreads.",
                }
            ],
        }

        ranked = scorer.score_all_stocks(policy_analysis)

        self.assertEqual([stock["ticker"] for stock in ranked], ["AAA", "BBB", "CCC"])
        self.assertTrue(ranked[0]["score"] > ranked[1]["score"] > ranked[2]["score"])
        self.assertEqual(ranked[0]["components"]["direction_score"], 1)
        self.assertIn("sector_alignment_score", ranked[0]["components"])
        self.assertIn("transmission_factor", ranked[0]["components"])

    def test_estimate_pipeline_improvement_exceeds_ninety_percent(self):
        metrics = scorer.estimate_pipeline_improvement(
            {
                "sectors": ["banking", "real_estate", "auto"],
            }
        )

        self.assertEqual(metrics["new"]["gemini_calls"], 1)
        self.assertGreater(metrics["old"]["gemini_calls"], 10)
        self.assertGreaterEqual(metrics["improvement"]["llm_call_reduction_pct"], 90.0)
        self.assertGreater(metrics["improvement"]["latency_reduction_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
