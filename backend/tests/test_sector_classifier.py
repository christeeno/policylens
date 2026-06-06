import os
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agent
import scorer


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def invoke(self, _prompt):
        self.calls += 1
        return self.response


class SequencedFakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def invoke(self, _prompt):
        self.calls += 1
        if not self.responses:
            raise AssertionError("No more fake responses configured.")
        return self.responses.pop(0)


class PolicyAnalysisTests(unittest.TestCase):
    def test_analyze_policy_returns_ranked_sector_impacts(self):
        fake_llm = FakeLLM(
            {
                "summary": "The RBI increased the repo rate by 50 basis points.",
                "ministry": "Reserve Bank of India",
                "key_change": "Policy repo rate increased by 50 basis points.",
                "policy_type": "RATE_CHANGE",
                "analyst_brief": "The RBI has tightened monetary policy with a 50 basis point repo hike. Banks and other rate-sensitive sectors should react first as lending and funding costs reset. Investors should watch transmission into mortgages, auto finance, and credit growth.",
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
        self.assertIn("repo hike", result["analyst_brief"].lower())
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
                    "analyst_brief": "The defence procurement push directly favors local manufacturers. Domestic sourcing requirements should create immediate demand visibility for defence platforms and components. Infrastructure spillovers are secondary and less direct.",
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
                    "analyst_brief": "The RBI has raised rates again. Banks are the clearest first-order transmission channel. Investors should expect funding conditions to tighten.",
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

    def test_classify_policy_event_marks_preview_as_non_actionable(self):
        result = scorer.classify_policy_event(
            "Reserve Bank of India to announce its bi-monthly Monetary Policy today.",
            llm=FakeLLM(
                {
                    "event_type": "PREVIEW",
                    "confidence_score": 0.97,
                    "reasoning": "The text describes an upcoming announcement rather than a completed policy action.",
                }
            ),
        )

        self.assertEqual(result["event_type"], "PREVIEW")
        self.assertFalse(result["is_actionable"])
        self.assertGreater(result["confidence_score"], 0.9)

    def test_classify_policy_event_marks_news_report_as_actionable(self):
        result = scorer.classify_policy_event(
            "Reuters: RBI raises repo rate by 50 basis points.",
            llm=FakeLLM(
                {
                    "event_type": "NEWS_REPORT",
                    "confidence_score": 0.94,
                    "reasoning": "A news outlet is reporting a completed policy action.",
                }
            ),
            source_type="NEWS",
            publisher="Reuters",
        )

        self.assertEqual(result["event_type"], "NEWS_REPORT")
        self.assertTrue(result["is_actionable"])

    def test_classify_policy_event_marks_official_policy_as_actionable(self):
        result = scorer.classify_policy_event(
            "RBI raises repo rate by 50 basis points.",
            llm=FakeLLM(
                {
                    "event_type": "OFFICIAL_POLICY",
                    "confidence_score": 0.98,
                    "reasoning": "An official issuer is announcing a completed policy action.",
                }
            ),
            source_type="OFFICIAL",
            publisher="Reserve Bank of India",
        )

        self.assertEqual(result["event_type"], "OFFICIAL_POLICY")
        self.assertTrue(result["is_actionable"])

    def test_classify_policy_event_skips_personnel_update_without_llm(self):
        fake_llm = SequencedFakeLLM([])

        result = scorer.classify_policy_event(
            "Shri Swaminathan Janakiraman re-appointed as RBI Deputy Governor.",
            llm=fake_llm,
            source_type="OFFICIAL",
            publisher="Reserve Bank of India",
        )

        self.assertEqual(fake_llm.calls, 0)
        self.assertEqual(result["event_type"], "OTHER")
        self.assertFalse(result["is_actionable"])

    def test_run_pipeline_skips_stock_analysis_for_non_actionable_event(self):
        fake_llm = SequencedFakeLLM(
            [
                {
                    "event_type": "COMMENTARY",
                    "confidence_score": 0.91,
                    "reasoning": "The text is an investor explainer and does not report a concrete policy action.",
                }
            ]
        )

        result = agent.run_pipeline(
            "What investors should watch after the RBI policy meeting.",
            source_url="manual_input",
            llm=fake_llm,
        )

        self.assertEqual(fake_llm.calls, 1)
        self.assertEqual(result["analysis_status"], "NO_ACTIONABLE_EVENT")
        self.assertEqual(result["event_type"], "COMMENTARY")
        self.assertEqual(result["stocks"], [])
        self.assertEqual(result["key_change"], "No actionable policy event detected.")

    @patch("scorer.score_all_stocks")
    @patch("scorer.analyze_policy")
    def test_run_pipeline_uses_feed_article_class_to_skip_stock_analysis(
        self,
        mock_analyze_policy,
        mock_score_all_stocks,
    ):
        fake_llm = SequencedFakeLLM([])

        result = agent.run_pipeline(
            "Why RBI chose dollars over rate hikes?",
            source_url="manual_input",
            source_type="NEWS",
            publisher="Moneycontrol.com",
            llm=fake_llm,
            article_class="COMMENTARY",
            classification_confidence=0.88,
            classification_reasoning="The text reads like commentary rather than a concrete policy decision.",
        )

        self.assertEqual(fake_llm.calls, 0)
        mock_analyze_policy.assert_not_called()
        mock_score_all_stocks.assert_not_called()
        self.assertEqual(result["analysis_status"], "NO_ACTIONABLE_EVENT")
        self.assertEqual(result["event_type"], "COMMENTARY")
        self.assertEqual(result["policy_type"], "NON_ACTIONABLE")
        self.assertEqual(result["stocks"], [])

    @patch("scorer.classify_policy_event")
    @patch("scorer.score_all_stocks", return_value=[{"ticker": "SBIN"}])
    @patch("scorer.analyze_policy")
    def test_run_pipeline_reuses_actionable_feed_classification(
        self,
        mock_analyze_policy,
        _mock_score_all_stocks,
        mock_classify_policy_event,
    ):
        fake_llm = SequencedFakeLLM([])
        mock_analyze_policy.return_value = {
            "summary": "RBI will conduct a VRR auction.",
            "ministry": "Reserve Bank of India",
            "key_change": "VRR auction announced.",
            "policy_type": "LIQUIDITY",
            "analyst_brief": "The RBI is adjusting short-term liquidity. Money-market transmission should react first. Investors should monitor banking and funding-sensitive segments.",
            "sectors": ["banking"],
            "confidence": "MEDIUM",
            "confidence_score": 0.66,
            "reasoning": "Official liquidity operation by RBI.",
            "sector_details": [
                {
                    "sector": "banking",
                    "confidence_score": 0.66,
                    "impact_direction": "POSITIVE",
                    "impact_strength": "MEDIUM",
                    "impact_strength_score": 0.65,
                    "reasoning": "Liquidity operations primarily affect funding conditions.",
                    "is_supported_sector": True,
                }
            ],
        }

        result = agent.run_pipeline(
            "On a review of current and evolving liquidity conditions, it has been decided to conduct a Variable Rate Repo (VRR) auction.",
            source_url="manual_input",
            source_type="OFFICIAL",
            publisher="Reserve Bank of India",
            llm=fake_llm,
            article_class="OFFICIAL_POLICY",
            classification_confidence=0.97,
            classification_reasoning="The text comes from Reserve Bank of India and describes a concrete policy action.",
        )

        self.assertEqual(fake_llm.calls, 0)
        mock_classify_policy_event.assert_not_called()
        mock_analyze_policy.assert_called_once()
        self.assertEqual(result["analysis_status"], "SUCCESS")
        self.assertEqual(result["event_type"], "OFFICIAL_POLICY")
        self.assertEqual(result["stocks"], [{"ticker": "SBIN"}])

    @patch("scorer.score_all_stocks")
    @patch("scorer.analyze_policy")
    def test_run_pipeline_skips_personnel_update_even_if_feed_marked_actionable(
        self,
        mock_analyze_policy,
        mock_score_all_stocks,
    ):
        fake_llm = SequencedFakeLLM([])

        result = agent.run_pipeline(
            "Shri Swaminathan Janakiraman re-appointed as RBI Deputy Governor.",
            source_url="manual_input",
            source_type="OFFICIAL",
            publisher="Reserve Bank of India",
            llm=fake_llm,
            article_class="OFFICIAL_POLICY",
            classification_confidence=0.97,
            classification_reasoning="The text comes from Reserve Bank of India and describes a concrete policy action.",
        )

        self.assertEqual(fake_llm.calls, 0)
        mock_analyze_policy.assert_not_called()
        mock_score_all_stocks.assert_not_called()
        self.assertEqual(result["analysis_status"], "NO_ACTIONABLE_EVENT")
        self.assertEqual(result["event_type"], "OTHER")
        self.assertEqual(result["stocks"], [])

    @patch("scorer.score_all_stocks", return_value=[{"ticker": "SBIN"}])
    def test_run_pipeline_analyzes_actionable_official_policy(self, _mock_score_all_stocks):
        fake_llm = SequencedFakeLLM(
            [
                {
                    "event_type": "OFFICIAL_POLICY",
                    "confidence_score": 0.98,
                    "reasoning": "This is an official completed policy action.",
                },
                {
                    "summary": "RBI raised the repo rate.",
                    "ministry": "Reserve Bank of India",
                    "key_change": "Repo rate increased by 50 basis points.",
                    "policy_type": "RATE_CHANGE",
                    "analyst_brief": "The policy is actionable. Banks and rate-sensitive sectors should react first. Investors should watch credit transmission.",
                    "overall_confidence_score": 0.9,
                    "overall_reasoning": "Completed RBI action with clear transmission.",
                    "sector_impacts": [
                        {
                            "sector": "banking",
                            "confidence_score": 0.92,
                            "impact_direction": "NEGATIVE",
                            "impact_strength": "HIGH",
                            "impact_strength_score": 0.91,
                            "reasoning": "Higher rates tighten conditions.",
                            "evidence": "repo rate increased",
                            "is_supported_sector": True,
                        }
                    ],
                },
            ]
        )

        result = agent.run_pipeline(
            "RBI raises repo rate by 50 basis points.",
            source_url="manual_input",
            llm=fake_llm,
            source_type="OFFICIAL",
            publisher="Reserve Bank of India",
        )

        self.assertEqual(result["analysis_status"], "SUCCESS")
        self.assertEqual(result["event_type"], "OFFICIAL_POLICY")
        self.assertEqual(result["stocks"], [{"ticker": "SBIN"}])

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

    @patch("scorer.resolve_exposure", return_value=(3, {"ticker": "RATECUT"}))
    def test_calculate_score_repo_cut_favors_rate_beneficiaries(self, _mock_resolve_exposure):
        policy_analysis = {
            "summary": "The RBI announced a 50 basis points repo rate cut and a liquidity infusion.",
            "key_change": "Repo rate cut by 50 basis points.",
            "reasoning": "Lower borrowing costs support credit demand.",
            "policy_type": "RATE_CHANGE",
        }
        sector_rank_map = {"banking": 0, "real_estate": 1, "auto": 2}
        impact_template = {
            "confidence_score": 0.9,
            "impact_strength": "HIGH",
            "impact_strength_score": 0.9,
            "reasoning": "RBI action transmits quickly.",
        }

        bank_result = scorer.calculate_score(
            {
                "ticker": "BANK1",
                "name": "Bank One",
                "type": "Bank",
                "base_exposure": 3,
                "rate_sensitivity": 3,
                "matched_sectors": ["banking"],
                "source_indices": ["NIFTY BANK"],
                "sector_impacts": [{**impact_template, "sector": "banking", "impact_direction": "POSITIVE"}],
            },
            policy_analysis,
            sector_rank_map,
        )
        realty_result = scorer.calculate_score(
            {
                "ticker": "REAL1",
                "name": "Realty One",
                "type": "Real Estate",
                "base_exposure": 3,
                "rate_sensitivity": 3,
                "matched_sectors": ["real_estate"],
                "source_indices": ["NIFTY REALTY"],
                "sector_impacts": [{**impact_template, "sector": "real_estate", "impact_direction": "POSITIVE"}],
            },
            policy_analysis,
            sector_rank_map,
        )
        auto_result = scorer.calculate_score(
            {
                "ticker": "AUTO1",
                "name": "Auto One",
                "type": "Auto",
                "base_exposure": 3,
                "rate_sensitivity": 2,
                "matched_sectors": ["auto"],
                "source_indices": ["NIFTY AUTO"],
                "sector_impacts": [{**impact_template, "sector": "auto", "impact_direction": "POSITIVE"}],
            },
            policy_analysis,
            sector_rank_map,
        )

        self.assertLess(bank_result["components"]["monetary_policy_multiplier"], 1.0)
        self.assertGreater(realty_result["components"]["monetary_policy_multiplier"], 1.0)
        self.assertGreater(auto_result["components"]["monetary_policy_multiplier"], 1.0)
        self.assertGreater(realty_result["score"], bank_result["score"])
        self.assertEqual(realty_result["components"]["policy_measures"]["repo_bps"], -50)

    @patch("scorer.resolve_exposure", return_value=(3, {"ticker": "RATEHIKE"}))
    def test_calculate_score_repo_hike_supports_banks_and_hurts_nbfcs(self, _mock_resolve_exposure):
        policy_analysis = {
            "summary": "The RBI increased the repo rate by 25 basis points and kept liquidity tight.",
            "key_change": "Repo rate hiked by 25 basis points.",
            "reasoning": "The central bank is tightening monetary conditions.",
            "policy_type": "RATE_CHANGE",
        }
        impact_template = {
            "confidence_score": 0.92,
            "impact_strength": "HIGH",
            "impact_strength_score": 0.88,
            "reasoning": "Funding conditions change immediately.",
        }

        bank_result = scorer.calculate_score(
            {
                "ticker": "BANK2",
                "name": "Bank Two",
                "type": "Bank",
                "base_exposure": 3,
                "rate_sensitivity": 3,
                "matched_sectors": ["banking"],
                "source_indices": ["NIFTY BANK"],
                "sector_impacts": [{**impact_template, "sector": "banking", "impact_direction": "POSITIVE"}],
            },
            policy_analysis,
            {"banking": 0},
        )
        nbfc_result = scorer.calculate_score(
            {
                "ticker": "NBFC1",
                "name": "NBFC One",
                "type": "NBFC",
                "base_exposure": 3,
                "rate_sensitivity": 3,
                "matched_sectors": ["nbfc"],
                "source_indices": ["CUSTOM NBFC"],
                "sector_impacts": [{**impact_template, "sector": "nbfc", "impact_direction": "POSITIVE"}],
            },
            policy_analysis,
            {"nbfc": 0},
        )

        self.assertGreater(bank_result["components"]["monetary_policy_multiplier"], 1.0)
        self.assertLess(nbfc_result["components"]["monetary_policy_multiplier"], 1.0)
        self.assertGreater(bank_result["score"], nbfc_result["score"])
        self.assertEqual(nbfc_result["components"]["policy_measures"]["policy_bucket"], "nbfc")
        self.assertEqual(bank_result["components"]["policy_measures"]["repo_bps"], 25)


if __name__ == "__main__":
    unittest.main()
