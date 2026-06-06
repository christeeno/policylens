import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def load_json(filename: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, payload: dict) -> None:
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


@dataclass
class ExposureFormula:
    revenue_weight: float = 0.40
    mix_weight: float = 0.20
    annual_report_weight: float = 0.25
    sector_concentration_weight: float = 0.15

    def as_dict(self) -> dict[str, float]:
        return {
            "revenue_weight": self.revenue_weight,
            "mix_weight": self.mix_weight,
            "annual_report_weight": self.annual_report_weight,
            "sector_concentration_weight": self.sector_concentration_weight,
        }


DEFAULT_FORMULA = ExposureFormula()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalize_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_share = sum(float(segment.get("revenue_share", 0.0)) for segment in segments)
    if total_share <= 0:
        return []

    normalized = []
    for segment in segments:
        share = float(segment.get("revenue_share", 0.0)) / total_share
        normalized.append(
            {
                **segment,
                "revenue_share": share,
                "policy_sensitivity": _clamp(float(segment.get("policy_sensitivity", 0.0))),
                "annual_report_signal": _clamp(float(segment.get("annual_report_signal", 0.0))),
            }
        )
    return normalized


def _business_mix_score(segments: list[dict[str, Any]]) -> float:
    # HHI naturally rises when revenue is concentrated in fewer segments.
    return _clamp(sum(float(segment["revenue_share"]) ** 2 for segment in segments))


def _sector_revenue_map(segments: list[dict[str, Any]]) -> dict[str, float]:
    sector_revenue: dict[str, float] = {}
    for segment in segments:
        sector = segment.get("sector", "other")
        sector_revenue[sector] = sector_revenue.get(sector, 0.0) + float(segment["revenue_share"])
    return sector_revenue


def _bucketize_exposure(raw_score: float) -> int:
    if raw_score < 0.20:
        return 1
    if raw_score < 0.40:
        return 2
    if raw_score < 0.60:
        return 3
    if raw_score < 0.80:
        return 4
    return 5


def calculate_exposure(company_data: dict[str, Any], formula: ExposureFormula = DEFAULT_FORMULA) -> dict[str, Any]:
    segments = _normalize_segments(company_data.get("segments", []))
    if not segments:
        return {
            "ticker": company_data.get("ticker"),
            "name": company_data.get("name"),
            "score_1_to_5": 1,
            "raw_score": 0.0,
            "components": {
                "revenue_factor": 0.0,
                "business_mix_factor": 0.0,
                "annual_report_factor": 0.0,
                "sector_concentration_factor": 0.0,
            },
            "formula": formula.as_dict(),
            "explanation": "No segment fundamentals available; defaulting to minimum exposure.",
        }

    revenue_factor = sum(
        float(segment["revenue_share"]) * float(segment["policy_sensitivity"]) for segment in segments
    )
    annual_report_factor = sum(
        float(segment["revenue_share"]) * float(segment["annual_report_signal"]) for segment in segments
    )
    business_mix_factor = _business_mix_score(segments)
    sector_revenue = _sector_revenue_map(segments)
    sector_concentration_factor = max(sector_revenue.values()) if sector_revenue else 0.0

    raw_score = (
        formula.revenue_weight * revenue_factor
        + formula.mix_weight * business_mix_factor
        + formula.annual_report_weight * annual_report_factor
        + formula.sector_concentration_weight * sector_concentration_factor
    )
    raw_score = _clamp(raw_score)

    return {
        "ticker": company_data.get("ticker"),
        "name": company_data.get("name"),
        "score_1_to_5": _bucketize_exposure(raw_score),
        "raw_score": round(raw_score, 4),
        "components": {
            "revenue_factor": round(revenue_factor, 4),
            "business_mix_factor": round(business_mix_factor, 4),
            "annual_report_factor": round(annual_report_factor, 4),
            "sector_concentration_factor": round(sector_concentration_factor, 4),
        },
        "formula": formula.as_dict(),
        "dominant_sector": max(sector_revenue, key=sector_revenue.get) if sector_revenue else None,
    }


def refresh_exposure_scores(
    fundamentals_file: str = "company_fundamentals.json",
    output_file: str = "exposure_scores.json",
    formula: ExposureFormula = DEFAULT_FORMULA,
) -> dict[str, Any]:
    fundamentals = load_json(fundamentals_file)
    companies = fundamentals.get("companies", [])
    scores = [calculate_exposure(company, formula=formula) for company in companies]

    payload = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "formula": formula.as_dict(),
        "scores": {score["ticker"]: score for score in scores if score.get("ticker")},
        "source_file": fundamentals_file,
    }
    save_json(output_file, payload)
    return payload


def get_exposure_score(
    ticker: str,
    fallback: int = 1,
    scores_file: str = "exposure_scores.json",
) -> tuple[int, dict[str, Any] | None]:
    try:
        payload = load_json(scores_file)
        stock = payload.get("scores", {}).get(ticker)
        if not stock:
            return fallback, None
        return int(stock.get("score_1_to_5", fallback)), stock
    except FileNotFoundError:
        return fallback, None
    except json.JSONDecodeError:
        return fallback, None


FORMULA_TEXT = """
revenue_factor = sum(segment_revenue_share * policy_sensitivity)
business_mix_factor = sum(segment_revenue_share^2)
annual_report_factor = sum(segment_revenue_share * annual_report_signal)
sector_concentration_factor = max(revenue_share grouped by sector)

raw_exposure =
    0.40 * revenue_factor +
    0.20 * business_mix_factor +
    0.25 * annual_report_factor +
    0.15 * sector_concentration_factor

normalized_exposure_score =
    1 if raw_exposure < 0.20
    2 if raw_exposure < 0.40
    3 if raw_exposure < 0.60
    4 if raw_exposure < 0.80
    5 otherwise
""".strip()
