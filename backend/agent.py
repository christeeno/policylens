import time
import uuid
from datetime import datetime

import scorer


def _build_analyst_brief(policy_analysis: dict, stocks: list[dict]) -> str:
    summary = policy_analysis.get("summary", "").strip()
    sectors = policy_analysis.get("sectors", [])
    sector_text = ", ".join(sectors[:3]) if sectors else "no clearly mapped sectors"

    top_stocks = stocks[:3]
    if top_stocks:
        stock_text = "; ".join(
            f'{stock["name"]} ({stock["ticker"]}) at {stock["score"]:+.2f}'
            for stock in top_stocks
        )
        implication = (
            "Portfolio action should focus on the highest-exposure names because the ranking is now driven by sector intensity and company fundamentals."
        )
        return f"{summary} The policy is most relevant for {sector_text}. Top ranked stocks are {stock_text}. {implication}"

    return f"{summary} The policy maps to {sector_text}, but no stock cleared the deterministic ranking threshold. Portfolio action should wait for clearer company-level transmission."


def run_pipeline(policy_text: str, source_url: str = "manual_input") -> dict:
    start_time = time.time()
    try:
        policy_analysis = scorer.analyze_policy(policy_text)
        stocks = scorer.score_all_stocks(policy_analysis)
        efficiency = scorer.estimate_pipeline_improvement(policy_analysis)
        end_time = time.time()

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
            "analyst_brief": _build_analyst_brief(policy_analysis, stocks),
            "ranking_formula": scorer.FORMULA_TEXT,
            "llm_efficiency": efficiency,
            "processing_time_ms": int((end_time - start_time) * 1000),
        }

    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
        }
