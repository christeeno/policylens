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
                "gemini_calls": 1,
                "steps": ["UnifiedPolicyAnalyzer"],
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


def run_pipeline(policy_text: str, source_url: str = "manual_input") -> dict:
    start_time = time.time()
    try:
        policy_analysis = scorer.analyze_policy(policy_text)
        stocks = scorer.score_all_stocks(policy_analysis)
        end_time = time.time()
        processing_time_ms = int((end_time - start_time) * 1000)
        efficiency = scorer.estimate_pipeline_improvement(policy_analysis)

        return {
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "source_url": source_url,
            "policy_summary": policy_analysis.get("summary", ""),
            "ministry": policy_analysis.get("ministry", ""),
            "key_change": policy_analysis.get("key_change", ""),
            "policy_type": policy_analysis.get("policy_type", ""),
            "sectors": policy_analysis.get("sectors", []),
            "confidence": policy_analysis.get("confidence", "LOW"),
            "confidence_score": policy_analysis.get("confidence_score", 0.0),
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
