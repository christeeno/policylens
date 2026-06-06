import math
import time
import uuid
from datetime import datetime

import scorer


LEGACY_PIPELINE_CALLS = {
    "policy_parser": 1,
    "report_writer": 1,
}
ESTIMATED_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, math.ceil(len(cleaned) / ESTIMATED_CHARS_PER_TOKEN))


def _coerce_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, confidence)), 2)


def _build_feed_event_classification(
    article_class: str = "",
    classification_confidence=None,
    classification_reasoning: str = "",
) -> dict | None:
    event_type = str(article_class or "").strip().upper()
    if not event_type or event_type not in scorer.EVENT_TYPES:
        return None

    reasoning = str(classification_reasoning or "").strip()
    if not reasoning:
        reasoning = f"Feed item was classified as {event_type}."

    return {
        "event_type": event_type,
        "confidence_score": _coerce_confidence(classification_confidence),
        "reasoning": reasoning,
        "is_actionable": event_type in scorer.ACTIONABLE_EVENT_TYPES,
        "classification_failed": False,
        "error_type": "",
        "error_message": "",
        "source": "feed_article_class",
    }


def _build_benchmark(policy_text: str, policy_analysis: dict, efficiency: dict, processing_time_ms: int) -> dict:
    rendered_prompt = scorer.render_single_call_prompt(policy_text)
    prompt_tokens = _estimate_tokens(rendered_prompt)
    output_tokens = _estimate_tokens(str(policy_analysis))
    legacy_prompt_tokens = _estimate_tokens(policy_text) * sum(LEGACY_PIPELINE_CALLS.values())

    return {
        "architecture": {
            "legacy": {
                "gemini_calls": sum(LEGACY_PIPELINE_CALLS.values()),
                "steps": ["PolicyParser", "ReportWriter"],
                "estimated_prompt_tokens": legacy_prompt_tokens,
            },
            "current": {
                "gemini_calls": 2,
                "steps": ["PolicyEventClassifier", "UnifiedPolicyAnalyzer"],
                "estimated_prompt_tokens": prompt_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_total_tokens": prompt_tokens + output_tokens,
            },
        },
        "token_reduction_pct_vs_legacy_two_call": round(
            ((legacy_prompt_tokens - prompt_tokens) / legacy_prompt_tokens) * 100, 2
        ) if legacy_prompt_tokens else 0.0,
        "latency": {
            "measured_processing_time_ms": processing_time_ms,
            "estimated_pipeline_efficiency": efficiency,
        },
        "prompt_design": {
            "model": "gemini-2.5-flash",
            "temperature": 0,
            "response_mode": "JSON only",
            "template_preview": scorer.SINGLE_CALL_PROMPT_TEMPLATE,
        },
    }


def _build_no_actionable_event_report(
    policy_text: str,
    source_url: str,
    event_classification: dict,
    processing_time_ms: int,
    source_type: str = "",
    publisher: str = "",
) -> dict:
    efficiency = {
        "assumptions": {
            "old_pipeline_calls": "1 parser + 1 sector classifier + N stock-level Gemini calls + 1 report writer",
            "new_pipeline_calls": "1 policy event classifier Gemini call",
            "old_stock_call_concurrency": scorer.OLD_PIPELINE_CONCURRENCY,
            "estimated_gemini_call_ms": scorer.ESTIMATED_GEMINI_CALL_MS,
            "affected_stock_count": 0,
        },
        "old": {
            "gemini_calls": scorer.OLD_PIPELINE_BASE_CALLS,
            "estimated_relative_cost_units": scorer.OLD_PIPELINE_BASE_CALLS,
            "estimated_latency_ms": scorer.OLD_PIPELINE_BASE_CALLS * scorer.ESTIMATED_GEMINI_CALL_MS,
        },
        "new": {
            "gemini_calls": 1,
            "estimated_relative_cost_units": 1,
            "estimated_latency_ms": scorer.ESTIMATED_GEMINI_CALL_MS,
        },
        "improvement": {
            "llm_call_reduction_pct": round(((scorer.OLD_PIPELINE_BASE_CALLS - 1) / scorer.OLD_PIPELINE_BASE_CALLS) * 100, 2),
            "cost_reduction_pct": round(((scorer.OLD_PIPELINE_BASE_CALLS - 1) / scorer.OLD_PIPELINE_BASE_CALLS) * 100, 2),
            "latency_reduction_pct": round((((scorer.OLD_PIPELINE_BASE_CALLS * scorer.ESTIMATED_GEMINI_CALL_MS) - scorer.ESTIMATED_GEMINI_CALL_MS) / (scorer.OLD_PIPELINE_BASE_CALLS * scorer.ESTIMATED_GEMINI_CALL_MS)) * 100, 2),
        },
    }
    event_type = event_classification.get("event_type", "OTHER")
    event_reasoning = event_classification.get("reasoning", "")
    return {
        "report_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "source_url": source_url,
        "source_type": source_type,
        "publisher": publisher,
        "policy_summary": (policy_text or "").strip(),
        "ministry": "",
        "key_change": "No actionable policy event detected.",
        "policy_type": "NON_ACTIONABLE",
        "sectors": [],
        "confidence": "LOW",
        "confidence_score": 0.0,
        "analysis_failed": False,
        "analysis_status": "NO_ACTIONABLE_EVENT",
        "analysis_error_type": "",
        "analysis_error_message": "",
        "article_class": event_type,
        "classification_confidence": event_classification.get("confidence_score", 0.0),
        "classification_reasoning": event_reasoning,
        "event_type": event_type,
        "event_confidence_score": event_classification.get("confidence_score", 0.0),
        "event_reasoning": event_reasoning,
        "sector_reasoning": event_reasoning,
        "sector_details": [],
        "stocks": [],
        "analyst_brief": "No actionable policy event detected.",
        "ranking_formula": scorer.FORMULA_TEXT,
        "llm_efficiency": efficiency,
        "benchmarking": {
            "architecture": {
                "legacy": {
                    "gemini_calls": scorer.OLD_PIPELINE_BASE_CALLS,
                    "steps": ["PolicyParser", "ReportWriter"],
                    "estimated_prompt_tokens": _estimate_tokens(policy_text) * sum(LEGACY_PIPELINE_CALLS.values()),
                },
                "current": {
                    "gemini_calls": 1,
                    "steps": ["PolicyEventClassifier"],
                    "estimated_prompt_tokens": _estimate_tokens(scorer.render_event_classifier_prompt(policy_text)),
                    "estimated_output_tokens": _estimate_tokens(str(event_classification)),
                    "estimated_total_tokens": _estimate_tokens(scorer.render_event_classifier_prompt(policy_text)) + _estimate_tokens(str(event_classification)),
                },
            },
            "token_reduction_pct_vs_legacy_two_call": 0.0,
            "latency": {
                "measured_processing_time_ms": processing_time_ms,
                "estimated_pipeline_efficiency": efficiency,
            },
            "prompt_design": {
                "model": "gemini-2.5-flash",
                "temperature": 0,
                "response_mode": "JSON only",
                "template_preview": scorer.EVENT_CLASSIFIER_PROMPT_TEMPLATE,
            },
        },
        "processing_time_ms": processing_time_ms,
    }


def _build_failed_classification_report(
    policy_text: str,
    source_url: str,
    event_classification: dict,
    processing_time_ms: int,
    source_type: str = "",
    publisher: str = "",
) -> dict:
    return {
        "report_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "source_url": source_url,
        "source_type": source_type,
        "publisher": publisher,
        "policy_summary": (policy_text or "").strip(),
        "ministry": "",
        "key_change": "Policy event classification failed.",
        "policy_type": "OTHER",
        "sectors": [],
        "confidence": "LOW",
        "confidence_score": 0.0,
        "analysis_failed": True,
        "analysis_status": "FAILED",
        "analysis_error_type": event_classification.get("error_type", ""),
        "analysis_error_message": event_classification.get("error_message", ""),
        "article_class": event_classification.get("event_type", "OTHER"),
        "classification_confidence": event_classification.get("confidence_score", 0.0),
        "classification_reasoning": event_classification.get("reasoning", ""),
        "event_type": event_classification.get("event_type", "OTHER"),
        "event_confidence_score": event_classification.get("confidence_score", 0.0),
        "event_reasoning": event_classification.get("reasoning", ""),
        "sector_reasoning": event_classification.get("reasoning", ""),
        "sector_details": [],
        "stocks": [],
        "analyst_brief": "Analysis unavailable because the policy event classifier failed.",
        "ranking_formula": scorer.FORMULA_TEXT,
        "llm_efficiency": {},
        "benchmarking": {},
        "processing_time_ms": processing_time_ms,
    }


def run_pipeline(
    policy_text: str,
    source_url: str = "manual_input",
    llm=None,
    source_type: str = "",
    publisher: str = "",
    article_class: str = "",
    classification_confidence=None,
    classification_reasoning: str = "",
) -> dict:
    start_time = time.time()
    try:
        feed_classification = _build_feed_event_classification(
            article_class=article_class,
            classification_confidence=classification_confidence,
            classification_reasoning=classification_reasoning,
        )
        if feed_classification and not feed_classification.get("is_actionable"):
            end_time = time.time()
            return _build_no_actionable_event_report(
                policy_text=policy_text,
                source_url=source_url,
                event_classification=feed_classification,
                processing_time_ms=int((end_time - start_time) * 1000),
                source_type=source_type,
                publisher=publisher,
            )

        event_classification = scorer.classify_policy_event(
            policy_text,
            llm=llm,
            source_type=source_type,
            publisher=publisher,
        )
        if event_classification.get("classification_failed"):
            end_time = time.time()
            return _build_failed_classification_report(
                policy_text=policy_text,
                source_url=source_url,
                event_classification=event_classification,
                processing_time_ms=int((end_time - start_time) * 1000),
                source_type=source_type,
                publisher=publisher,
            )
        if not event_classification.get("is_actionable"):
            end_time = time.time()
            return _build_no_actionable_event_report(
                policy_text=policy_text,
                source_url=source_url,
                event_classification=event_classification,
                processing_time_ms=int((end_time - start_time) * 1000),
                source_type=source_type,
                publisher=publisher,
            )

        policy_analysis = scorer.analyze_policy(policy_text, llm=llm)
        stocks = scorer.score_all_stocks(policy_analysis)
        end_time = time.time()
        processing_time_ms = int((end_time - start_time) * 1000)
        efficiency = scorer.estimate_pipeline_improvement(policy_analysis)

        return {
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "source_url": source_url,
            "source_type": source_type,
            "publisher": publisher,
            "policy_summary": policy_analysis.get("summary", ""),
            "ministry": policy_analysis.get("ministry", ""),
            "key_change": policy_analysis.get("key_change", ""),
            "policy_type": policy_analysis.get("policy_type", ""),
            "sectors": policy_analysis.get("sectors", []),
            "confidence": policy_analysis.get("confidence", "LOW"),
            "confidence_score": policy_analysis.get("confidence_score", 0.0),
            "analysis_failed": policy_analysis.get("analysis_failed", False),
            "analysis_status": "FAILED" if policy_analysis.get("analysis_failed") else "SUCCESS",
            "analysis_error_type": policy_analysis.get("error_type", ""),
            "analysis_error_message": policy_analysis.get("error_message", ""),
            "article_class": article_class or event_classification.get("event_type", "OTHER"),
            "classification_confidence": classification_confidence
            if classification_confidence is not None
            else event_classification.get("confidence_score", 0.0),
            "classification_reasoning": classification_reasoning or event_classification.get("reasoning", ""),
            "event_type": event_classification.get("event_type", "OTHER"),
            "event_confidence_score": event_classification.get("confidence_score", 0.0),
            "event_reasoning": event_classification.get("reasoning", ""),
            "sector_reasoning": policy_analysis.get("reasoning", ""),
            "sector_details": policy_analysis.get("sector_details", []),
            "stocks": stocks,
            "analyst_brief": policy_analysis.get("analyst_brief", ""),
            "ranking_formula": scorer.FORMULA_TEXT,
            "llm_efficiency": efficiency,
            "benchmarking": _build_benchmark(
                policy_text=policy_text,
                policy_analysis=policy_analysis,
                efficiency=efficiency,
                processing_time_ms=processing_time_ms,
            ),
            "processing_time_ms": processing_time_ms,
        }

    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
        }
