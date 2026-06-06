import json
import math
import os
import re
from typing import Any

from exposure_engine import get_exposure_score
from index_loader import OfficialNiftyIndexUniverse
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


_UNIVERSE_LOADER: OfficialNiftyIndexUniverse | None = None

POLICY_TYPE_RATE_SENSITIVE = {"RATE_CHANGE", "LIQUIDITY", "MONETARY_POLICY"}
IMPACT_STRENGTH_SCORES = {"HIGH": 0.95, "MEDIUM": 0.65, "LOW": 0.35}
DIRECTION_SCORES = {"POSITIVE": 1, "NEGATIVE": -1, "NEUTRAL": 0}
SECTOR_RANK_WEIGHTS = [1.0, 0.88, 0.76]
OLD_PIPELINE_BASE_CALLS = 3
OLD_PIPELINE_CONCURRENCY = 10
ESTIMATED_GEMINI_CALL_MS = 1200
RATE_SENSITIVITY_SCALE = {1: 0.75, 2: 1.0, 3: 1.25}
MONETARY_POLICY_SECTOR_BETAS = {
    "banking": {"repo": 0.10, "crr": -0.08, "liquidity": 0.04},
    "nbfc": {"repo": -0.18, "crr": -0.04, "liquidity": 0.12},
    "real_estate": {"repo": -0.28, "crr": -0.10, "liquidity": 0.08},
    "auto": {"repo": -0.16, "crr": -0.05, "liquidity": 0.05},
}

SUPPORTED_SECTOR_HINTS = {
    "broad_market": "broad market, benchmark policy, economy-wide or index-level implications captured through Nifty 50",
    "auto": "automobiles, EVs, auto ancillaries, vehicle manufacturing",
    "banking": "banks, lending, deposits, repo transmission, credit growth",
    "defence": "defence production, military procurement, aerospace, shipbuilding",
    "energy": "oil and gas, power, renewables, electricity generation and distribution",
    "fmcg": "consumer staples, packaged foods, household products, tobacco",
    "infrastructure": "roads, railways, ports, logistics, construction, public capex",
    "it": "software services, digital infrastructure, data policy, electronics, startups",
    "pharma": "drugs, medical devices, healthcare manufacturing, pharma regulation",
    "psu": "public sector enterprises, disinvestment, state-owned companies, government-backed corporates",
    "real_estate": "housing, mortgages, developers, commercial and residential property",
}
SUPPORTED_SECTORS = sorted(SUPPORTED_SECTOR_HINTS.keys())


class SectorImpact(BaseModel):
    sector: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    impact_direction: str
    impact_strength: str
    impact_strength_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence: str = ""
    is_supported_sector: bool


class PolicyAnalysisResult(BaseModel):
    summary: str
    ministry: str
    key_change: str
    policy_type: str
    analyst_brief: str
    sectors: list[str]
    confidence: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    sector_details: list[SectorImpact]


def load_json(filename: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _get_universe_loader() -> OfficialNiftyIndexUniverse:
    global _UNIVERSE_LOADER
    if _UNIVERSE_LOADER is None:
        _UNIVERSE_LOADER = OfficialNiftyIndexUniverse()
    return _UNIVERSE_LOADER


def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


def _normalize_sector_name(raw_sector: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (raw_sector or "").strip().lower())
    return normalized.strip("_")


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, score))


def _extract_json_object(raw_response: Any) -> dict:
    if isinstance(raw_response, dict):
        return raw_response

    content = getattr(raw_response, "content", raw_response)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        text = "".join(parts)
    else:
        text = str(content)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


SINGLE_CALL_PROMPT_TEMPLATE = """You are a senior Indian policy and equity analyst.

Analyze the policy announcement below and return exactly one valid JSON object.

Your output must contain:
- summary
- ministry
- policy_type
- affected_sectors
- confidence
- analyst_brief

Supported sectors:
{sector_guide}

Rules:
1. Use only the policy text provided.
2. Keep summary to at most 2 sentences.
3. Set ministry to the issuing ministry, regulator, department, or authority.
4. Set key_change to the single most important policy action.
5. policy_type must be one of: RATE_CHANGE, REGULATION, SUBSIDY, TAX, BAN, APPROVAL, LIQUIDITY, MONETARY_POLICY, OTHER.
6. Return up to 3 affected sectors ranked by first-order impact on listed Indian equities.
7. Prefer supported sectors when appropriate, but you may return a concise snake_case custom sector if clearly necessary.
8. confidence must be HIGH, MEDIUM, or LOW.
9. analyst_brief must be a 3-sentence investor-facing note grounded only in the policy text and sector impacts.
10. Respond with JSON only. No markdown, no prose outside JSON.

Required JSON schema:
{{
  "summary": "<2 sentences max>",
  "ministry": "<issuer>",
  "key_change": "<single most important change>",
  "policy_type": "<RATE_CHANGE | REGULATION | SUBSIDY | TAX | BAN | APPROVAL | LIQUIDITY | MONETARY_POLICY | OTHER>",
  "confidence": "<HIGH | MEDIUM | LOW>",
  "overall_confidence_score": <float 0 to 1>,
  "overall_reasoning": "<1-2 sentences>",
  "analyst_brief": "<exactly 3 sentences>",
  "sector_impacts": [
    {{
      "sector": "<supported sector or concise snake_case custom sector>",
      "confidence_score": <float 0 to 1>,
      "impact_direction": "<POSITIVE | NEGATIVE | NEUTRAL>",
      "impact_strength": "<HIGH | MEDIUM | LOW>",
      "impact_strength_score": <float 0 to 1>,
      "reasoning": "<why the sector is affected>",
      "evidence": "<short phrase from the policy text>",
      "is_supported_sector": <true or false>
    }}
  ]
}}

POLICY TEXT:
{policy_text}"""


def render_single_call_prompt(policy_text: str) -> str:
    sector_guide = "\n".join(
        f'- "{sector}": {description}'
        for sector, description in SUPPORTED_SECTOR_HINTS.items()
    )
    return SINGLE_CALL_PROMPT_TEMPLATE.format(
        sector_guide=sector_guide,
        policy_text=policy_text,
    )


def _normalize_policy_response(raw_response: dict) -> dict:
    loader = _get_universe_loader()
    raw_impacts = raw_response.get("sector_impacts", [])
    deduped: dict[str, dict] = {}

    for item in raw_impacts:
        raw_sector = _normalize_sector_name(item.get("sector", ""))
        if not raw_sector:
            continue

        resolved_sector = loader.resolve_sector_key(raw_sector) or raw_sector
        impact_strength = str(item.get("impact_strength", "LOW")).upper()
        normalized = {
            "sector": resolved_sector,
            "confidence_score": _coerce_float(item.get("confidence_score"), 0.0),
            "impact_direction": str(item.get("impact_direction", "NEUTRAL")).upper(),
            "impact_strength": impact_strength if impact_strength in IMPACT_STRENGTH_SCORES else "LOW",
            "impact_strength_score": _coerce_float(
                item.get("impact_strength_score"),
                IMPACT_STRENGTH_SCORES.get(impact_strength, 0.35),
            ),
            "reasoning": str(item.get("reasoning", "")).strip(),
            "evidence": str(item.get("evidence", "")).strip(),
            "is_supported_sector": resolved_sector in SUPPORTED_SECTORS,
        }

        existing = deduped.get(resolved_sector)
        if existing is None or normalized["confidence_score"] > existing["confidence_score"]:
            deduped[resolved_sector] = normalized

    ranked_impacts = sorted(
        deduped.values(),
        key=lambda impact: (impact["confidence_score"], impact["impact_strength_score"]),
        reverse=True,
    )[:3]

    if ranked_impacts:
        average_confidence = sum(item["confidence_score"] for item in ranked_impacts) / len(ranked_impacts)
        overall_confidence = _coerce_float(
            raw_response.get("overall_confidence_score"),
            average_confidence,
        )
        overall_reasoning = str(raw_response.get("overall_reasoning", "")).strip()
        if not overall_reasoning:
            overall_reasoning = " ".join(item["reasoning"] for item in ranked_impacts if item["reasoning"]).strip()
    else:
        overall_confidence = 0.0
        overall_reasoning = "No sector could be classified confidently from the policy text."

    normalized = {
        "summary": str(raw_response.get("summary", "")).strip(),
        "ministry": str(raw_response.get("ministry", "")).strip(),
        "key_change": str(raw_response.get("key_change", "")).strip(),
        "policy_type": str(raw_response.get("policy_type", "OTHER")).upper(),
        "analyst_brief": str(raw_response.get("analyst_brief", "")).strip(),
        "sectors": [item["sector"] for item in ranked_impacts],
        "confidence": _confidence_label(overall_confidence),
        "confidence_score": round(overall_confidence, 2),
        "reasoning": overall_reasoning,
        "sector_details": [
            {
                **item,
                "confidence_score": round(item["confidence_score"], 2),
                "impact_strength_score": round(item["impact_strength_score"], 2),
            }
            for item in ranked_impacts
        ],
    }

    PolicyAnalysisResult.model_validate(normalized)
    return normalized


def analyze_policy(policy_text: str, llm: Any | None = None) -> dict:
    if not policy_text or not policy_text.strip():
        return {
            "summary": "",
            "ministry": "",
            "key_change": "",
            "policy_type": "OTHER",
            "analyst_brief": "",
            "sectors": [],
            "confidence": "LOW",
            "confidence_score": 0.0,
            "reasoning": "No policy text was provided.",
            "sector_details": [],
        }

    try:
        client = llm or _get_llm()
        prompt = render_single_call_prompt(policy_text)
        if hasattr(client, "invoke"):
            raw_response = client.invoke(prompt)
        elif callable(client):
            raw_response = client(prompt)
        else:
            raise TypeError("Policy analysis client must be callable or implement invoke().")
        return _normalize_policy_response(_extract_json_object(raw_response))
    except Exception:
        return {
            "summary": "",
            "ministry": "",
            "key_change": "",
            "policy_type": "OTHER",
            "analyst_brief": "",
            "sectors": [],
            "confidence": "LOW",
            "confidence_score": 0.0,
            "reasoning": "Policy analysis was unavailable because the model response could not be validated.",
            "sector_details": [],
        }


def map_sectors(policy_text: str, llm: Any | None = None) -> dict:
    analyzed = analyze_policy(policy_text, llm=llm)
    return {
        "sectors": analyzed.get("sectors", []),
        "confidence": analyzed.get("confidence", "LOW"),
        "confidence_score": analyzed.get("confidence_score", 0.0),
        "reasoning": analyzed.get("reasoning", ""),
        "sector_details": analyzed.get("sector_details", []),
    }


def resolve_exposure(ticker: str, stock_data: dict) -> tuple[int, dict | None]:
    manual_exposure = stock_data.get("exposure", 1)
    return get_exposure_score(ticker=ticker, fallback=manual_exposure)


def _resolve_sector_display_name(sector: str) -> str:
    loader = _get_universe_loader()
    resolved = loader.resolve_sector_key(sector) or sector
    definition = loader.definitions.get(resolved)
    return definition.display_name if definition else resolved.replace("_", " ").title()


def _build_stock_tasks(policy_analysis: dict, force_refresh_universe: bool = False) -> tuple[list[dict], dict[str, dict]]:
    loader = _get_universe_loader()
    sector_details = policy_analysis.get("sector_details", [])
    sectors = []
    sector_lookup = {}
    for detail in sector_details:
        resolved = loader.resolve_sector_key(detail.get("sector", "")) or _normalize_sector_name(detail.get("sector", ""))
        if not resolved:
            continue
        normalized_detail = {**detail, "sector": resolved}
        sector_lookup[resolved] = normalized_detail
        if normalized_detail.get("is_supported_sector") and resolved not in sectors:
            sectors.append(resolved)

    if not sectors:
        sectors = ["broad_market"]

    universes, _ = loader.load_for_sectors(sectors, force_refresh=force_refresh_universe)
    merged: dict[str, dict] = {}

    for sector in sectors:
        sector_detail = sector_lookup.get(
            sector,
            {
                "sector": sector,
                "confidence_score": 0.45,
                "impact_direction": "NEUTRAL",
                "impact_strength": "LOW",
                "impact_strength_score": 0.35,
                "reasoning": "Fallback broad market universe.",
                "is_supported_sector": True,
            },
        )
        for constituent in universes.get(sector, []):
            existing = merged.get(constituent.ticker)
            if existing is None:
                existing = {
                    "ticker": constituent.ticker,
                    "name": constituent.name,
                    "type": constituent.stock_type,
                    "base_exposure": constituent.exposure,
                    "rate_sensitivity": constituent.rate_sensitivity,
                    "matched_sectors": [],
                    "matched_sector_labels": [],
                    "source_indices": [],
                    "sector_impacts": [],
                }
                merged[constituent.ticker] = existing

            if sector not in existing["matched_sectors"]:
                existing["matched_sectors"].append(sector)
                existing["matched_sector_labels"].append(_resolve_sector_display_name(sector))
            if constituent.source_index_name not in existing["source_indices"]:
                existing["source_indices"].append(constituent.source_index_name)

            existing["base_exposure"] = max(existing["base_exposure"], constituent.exposure)
            existing["rate_sensitivity"] = max(existing["rate_sensitivity"], constituent.rate_sensitivity)
            existing["sector_impacts"].append(sector_detail)

    return list(merged.values()), sector_lookup


def _rate_transmission_multiplier(policy_type: str, rate_sensitivity: int) -> float:
    if policy_type not in POLICY_TYPE_RATE_SENSITIVE:
        return 1.0
    return 0.85 + (min(max(rate_sensitivity, 1), 3) * 0.15)


def _policy_measure_text(policy_analysis: dict) -> str:
    return " ".join(
        str(policy_analysis.get(field, "")).strip()
        for field in ("summary", "key_change", "reasoning")
        if str(policy_analysis.get(field, "")).strip()
    )


def _extract_basis_points(text: str, pattern: str) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return 0

    amount = int(match.group("bps"))
    direction = match.group("direction").lower()
    if direction in {"cut", "reduced", "reduction", "decreased", "lowered", "eased"}:
        return -amount
    return amount


def _extract_liquidity_signal(text: str) -> float:
    normalized = text.lower()
    positive_markers = (
        "liquidity infusion",
        "inject liquidity",
        "liquidity support",
        "accommodative stance",
        "durable liquidity",
        "open market purchase",
        "omo purchase",
    )
    negative_markers = (
        "liquidity absorption",
        "absorb liquidity",
        "withdraw liquidity",
        "tightening stance",
        "variable rate reverse repo",
        "omo sale",
    )

    score = 0.0
    if any(marker in normalized for marker in positive_markers):
        score += 1.0
    if any(marker in normalized for marker in negative_markers):
        score -= 1.0
    return max(-1.0, min(1.0, score))


def extract_monetary_policy_shocks(policy_analysis: dict) -> dict:
    text = _policy_measure_text(policy_analysis)
    repo_bps = _extract_basis_points(
        text,
        r"repo rate[^.]{0,80}?(?P<direction>cut|hike|hiked|raised|increase|increased|reduced|reduction|decreased|lowered|eased)[^.]{0,40}?(?P<bps>\d+)\s*basis points",
    )
    if repo_bps == 0:
        repo_bps = _extract_basis_points(
            text,
            r"(?P<bps>\d+)\s*basis points[^.]{0,50}?(?P<direction>cut|hike|hiked|raised|increase|increased|reduced|reduction|decreased|lowered|eased)[^.]{0,50}?repo rate",
        )

    crr_bps = _extract_basis_points(
        text,
        r"\bcrr\b[^.]{0,80}?(?P<direction>cut|hike|hiked|raised|increase|increased|reduced|reduction|decreased|lowered)[^.]{0,40}?(?P<bps>\d+)\s*basis points",
    )
    if crr_bps == 0:
        crr_bps = _extract_basis_points(
            text,
            r"(?P<bps>\d+)\s*basis points[^.]{0,50}?(?P<direction>cut|hike|hiked|raised|increase|increased|reduced|reduction|decreased|lowered)[^.]{0,50}?\bcrr\b",
        )

    return {
        "repo_bps": repo_bps,
        "crr_bps": crr_bps,
        "liquidity_signal": _extract_liquidity_signal(text),
        "is_rbi_policy": (
            "rbi" in text.lower()
            or "reserve bank of india" in text.lower()
            or str(policy_analysis.get("policy_type", "")).upper() in POLICY_TYPE_RATE_SENSITIVE
        ),
    }


def _sector_policy_bucket(sector: str) -> str | None:
    normalized = _normalize_sector_name(sector)
    if normalized in MONETARY_POLICY_SECTOR_BETAS:
        return normalized
    if normalized in {"bank", "banks", "banking", "financials", "finance"}:
        return "banking"
    if normalized in {"nbfc", "nbfcs", "housing_finance", "consumer_finance"}:
        return "nbfc"
    return None


def _monetary_policy_multiplier(policy_analysis: dict, sector: str, rate_sensitivity: int) -> tuple[float, dict]:
    shocks = extract_monetary_policy_shocks(policy_analysis)
    bucket = _sector_policy_bucket(sector)
    if not shocks["is_rbi_policy"] or bucket is None:
        return 1.0, {
            "repo_bps": shocks["repo_bps"],
            "crr_bps": shocks["crr_bps"],
            "liquidity_signal": shocks["liquidity_signal"],
            "policy_bucket": bucket,
            "multiplier": 1.0,
            "repo_component": 0.0,
            "crr_component": 0.0,
            "liquidity_component": 0.0,
            "policy_shock": 0.0,
        }

    sensitivity_scale = RATE_SENSITIVITY_SCALE[min(max(int(rate_sensitivity), 1), 3)]
    betas = MONETARY_POLICY_SECTOR_BETAS[bucket]
    repo_component = (shocks["repo_bps"] / 25.0) * betas["repo"] * sensitivity_scale
    crr_component = (shocks["crr_bps"] / 25.0) * betas["crr"] * sensitivity_scale
    liquidity_component = shocks["liquidity_signal"] * betas["liquidity"] * sensitivity_scale
    policy_shock = repo_component + crr_component + liquidity_component
    multiplier = max(0.4, min(1.75, 1.0 + policy_shock))

    return multiplier, {
        "repo_bps": shocks["repo_bps"],
        "crr_bps": shocks["crr_bps"],
        "liquidity_signal": shocks["liquidity_signal"],
        "policy_bucket": bucket,
        "multiplier": round(multiplier, 3),
        "repo_component": round(repo_component, 3),
        "crr_component": round(crr_component, 3),
        "liquidity_component": round(liquidity_component, 3),
        "policy_shock": round(policy_shock, 3),
    }


def _sector_rank_weight(rank_index: int) -> float:
    return SECTOR_RANK_WEIGHTS[min(rank_index, len(SECTOR_RANK_WEIGHTS) - 1)]


def calculate_score(task: dict, policy_analysis: dict, sector_rank_map: dict[str, int] | None = None) -> dict:
    sector_rank_map = sector_rank_map or {}
    policy_type = str(policy_analysis.get("policy_type", "OTHER")).upper()
    try:
        exposure_score, exposure_details = resolve_exposure(task["ticker"], task)
    except Exception:
        exposure_score = int(task.get("base_exposure", 1))
        exposure_details = None

    exposure_factor = max(1, min(exposure_score, 5)) / 5
    universe_factor = max(1, min(int(task.get("base_exposure", 1)), 5)) / 5
    rate_multiplier = _rate_transmission_multiplier(policy_type, int(task.get("rate_sensitivity", 1)))

    weighted_score = 0.0
    top_sector = task["matched_sectors"][0] if task["matched_sectors"] else "broad_market"
    top_sector_magnitude = -1.0
    representative = None
    policy_overlay = None

    for impact in task["sector_impacts"]:
        direction_score = DIRECTION_SCORES.get(str(impact.get("impact_direction", "NEUTRAL")).upper(), 0)
        rank_weight = _sector_rank_weight(sector_rank_map.get(impact.get("sector"), 0))
        sector_alignment_score = _coerce_float(impact.get("confidence_score"), 0.0) * rank_weight
        transmission_factor = _coerce_float(
            impact.get("impact_strength_score"),
            IMPACT_STRENGTH_SCORES.get(str(impact.get("impact_strength", "LOW")).upper(), 0.35),
        )
        policy_multiplier, overlay_components = _monetary_policy_multiplier(
            policy_analysis,
            str(impact.get("sector", "")),
            int(task.get("rate_sensitivity", 1)),
        )
        sector_component = direction_score * sector_alignment_score * transmission_factor * rate_multiplier * policy_multiplier
        magnitude = abs(sector_component)
        if magnitude > top_sector_magnitude:
            top_sector_magnitude = magnitude
            top_sector = impact["sector"]
            representative = impact
            policy_overlay = overlay_components
        weighted_score += sector_component

    composite_exposure = (0.7 * universe_factor) + (0.3 * exposure_factor)
    final_score = round(weighted_score * composite_exposure * 10, 2)
    primary_impact = representative or {}
    direction = str(primary_impact.get("impact_direction", "NEUTRAL")).upper()
    label = (
        "Strong Positive" if final_score >= 6 else
        "Moderate Positive" if final_score >= 2 else
        "Neutral" if final_score > -2 else
        "Moderate Negative" if final_score > -6 else
        "Strong Negative"
    )

    return {
        "ticker": task["ticker"],
        "name": task["name"],
        "sector": top_sector,
        "matched_sectors": task["matched_sectors"],
        "source_indices": task["source_indices"],
        "direction": direction,
        "score": final_score,
        "label": label,
        "reason": str(primary_impact.get("reasoning", "")).strip() or "Deterministic sector-based ranking.",
        "components": {
            "direction_score": DIRECTION_SCORES.get(direction, 0),
            "sector_alignment_score": round(
                _coerce_float(primary_impact.get("confidence_score"), 0.0)
                * _sector_rank_weight(sector_rank_map.get(top_sector, 0)),
                2,
            ),
            "transmission_factor": round(
                _coerce_float(
                    primary_impact.get("impact_strength_score"),
                    IMPACT_STRENGTH_SCORES.get(str(primary_impact.get("impact_strength", "LOW")).upper(), 0.35),
                )
                * rate_multiplier,
                2,
            ),
            "exposure": exposure_score,
            "universe_weight_score": round(universe_factor, 2),
            "rate_sensitivity": task["rate_sensitivity"],
            "monetary_policy_multiplier": round(1.0 if not policy_overlay else policy_overlay["multiplier"], 2),
            "policy_measures": policy_overlay or {
                "repo_bps": 0,
                "crr_bps": 0,
                "liquidity_signal": 0.0,
                "policy_bucket": None,
                "multiplier": 1.0,
                "repo_component": 0.0,
                "crr_component": 0.0,
                "liquidity_component": 0.0,
                "policy_shock": 0.0,
            },
        },
        "exposure_details": exposure_details,
    }


def score_all_stocks(policy_analysis: dict, force_refresh_universe: bool = False) -> list[dict]:
    tasks, sector_lookup = _build_stock_tasks(policy_analysis, force_refresh_universe=force_refresh_universe)
    results = []
    sector_rank_map = {
        detail.get("sector"): index
        for index, detail in enumerate(policy_analysis.get("sector_details", []))
    }

    for task in tasks:
        scored = calculate_score(task, policy_analysis, sector_rank_map=sector_rank_map)
        if scored["score"] == 0:
            continue
        if not scored.get("reason"):
            primary = sector_lookup.get(scored["sector"], {})
            scored["reason"] = str(primary.get("reasoning", "")).strip() or scored["reason"]
        results.append(scored)

    results.sort(key=lambda item: (abs(item["score"]), item["score"]), reverse=True)
    return results


def estimate_pipeline_improvement(policy_analysis: dict) -> dict:
    loader = _get_universe_loader()
    sectors = []
    for sector in policy_analysis.get("sectors", []):
        resolved = loader.resolve_sector_key(sector)
        if resolved and resolved not in sectors:
            sectors.append(resolved)

    if not sectors:
        sectors = ["broad_market"]

    stock_count = 0
    for sector in sectors:
        constituents, _ = loader.load_sector(sector)
        stock_count += len(constituents)

    old_gemini_calls = stock_count + OLD_PIPELINE_BASE_CALLS
    new_gemini_calls = 1

    old_latency_ms = (OLD_PIPELINE_BASE_CALLS + max(1, math.ceil(stock_count / OLD_PIPELINE_CONCURRENCY))) * ESTIMATED_GEMINI_CALL_MS
    new_latency_ms = ESTIMATED_GEMINI_CALL_MS

    return {
        "assumptions": {
            "old_pipeline_calls": "1 parser + 1 sector classifier + N stock-level Gemini calls + 1 report writer",
            "new_pipeline_calls": "1 policy analysis Gemini call + deterministic stock ranking and report generation",
            "old_stock_call_concurrency": OLD_PIPELINE_CONCURRENCY,
            "estimated_gemini_call_ms": ESTIMATED_GEMINI_CALL_MS,
            "affected_stock_count": stock_count,
        },
        "old": {
            "gemini_calls": old_gemini_calls,
            "estimated_relative_cost_units": old_gemini_calls,
            "estimated_latency_ms": old_latency_ms,
        },
        "new": {
            "gemini_calls": new_gemini_calls,
            "estimated_relative_cost_units": new_gemini_calls,
            "estimated_latency_ms": new_latency_ms,
        },
        "improvement": {
            "llm_call_reduction_pct": round(((old_gemini_calls - new_gemini_calls) / old_gemini_calls) * 100, 2),
            "cost_reduction_pct": round(((old_gemini_calls - new_gemini_calls) / old_gemini_calls) * 100, 2),
            "latency_reduction_pct": round(((old_latency_ms - new_latency_ms) / old_latency_ms) * 100, 2),
        },
    }


FORMULA_TEXT = """
Directness replacement:
sector_alignment_score = sector_confidence_score * sector_rank_weight

Sentiment replacement:
direction_score = +1 for POSITIVE, -1 for NEGATIVE, 0 for NEUTRAL

Monetary-policy overlay for RBI-linked announcements:
repo_component = (repo_bps / 25) * sector_repo_beta * rate_sensitivity_scale
crr_component = (crr_bps / 25) * sector_crr_beta * rate_sensitivity_scale
liquidity_component = liquidity_signal * sector_liquidity_beta * rate_sensitivity_scale
monetary_policy_multiplier = clamp(1 + repo_component + crr_component + liquidity_component, 0.4, 1.75)

Transmission replacement:
transmission_factor = impact_strength_score * rate_transmission_multiplier(policy_type, rate_sensitivity) * monetary_policy_multiplier

Deterministic stock score:
weighted_sector_component = direction_score * sector_alignment_score * transmission_factor
composite_exposure = 0.70 * universe_weight_score + 0.30 * normalized_company_exposure
final_score = 10 * sum(weighted_sector_component across matched sectors) * composite_exposure
""".strip()
