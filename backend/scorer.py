import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def load_json(filename: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

SECTOR_KEYWORDS = load_json("sector_keywords.json")
STOCK_UNIVERSE = load_json("stock_universe.json")

def map_sectors(policy_text: str) -> dict:
    text_lower = policy_text.lower()
    matches_per_sector = {}
    keyword_matches = {}
    
    for sector, data in SECTOR_KEYWORDS.items():
        matched_kws = [kw for kw in data["keywords"] if kw in text_lower]
        if matched_kws:
            matches_per_sector[sector] = len(matched_kws)
            keyword_matches[sector] = matched_kws
            
    # Sort sectors by match count desc
    sorted_sectors = sorted(matches_per_sector.keys(), key=lambda s: matches_per_sector[s], reverse=True)
    
    max_matches = max(matches_per_sector.values()) if matches_per_sector else 0
    if max_matches >= 3:
        confidence = "HIGH"
    elif max_matches >= 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
        
    return {
        "sectors": sorted_sectors,
        "confidence": confidence,
        "keyword_matches": keyword_matches
    }

def get_llm_scores(policy_text: str, ticker: str, sector: str, stock_data: dict) -> dict:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    prompt = PromptTemplate.from_template("""You are a senior financial analyst at a top Indian investment bank.

POLICY TEXT:
{policy_text}

STOCK TO EVALUATE:
Ticker: {ticker}
Company: {stock_name}
Sector: {sector}
Type: {stock_type}

Your task: Evaluate the impact of this policy on this specific stock.

Respond ONLY with a JSON object. No explanation before or after. No markdown. Raw JSON only:
{{
  "directness": <integer 1-3>,
  "sentiment": <"POSITIVE" | "NEGATIVE" | "NEUTRAL">,
  "horizon": <"SHORT" | "MEDIUM" | "LONG">,
  "reason": "<one sentence, max 20 words, specific to this stock>"
}}

Scoring guide:
- directness 3: policy explicitly targets this sector
- directness 2: sector is clearly affected but not primary target  
- directness 1: indirect ripple effect only
- sentiment POSITIVE: policy benefits this stock's revenue or valuation
- sentiment NEGATIVE: policy hurts this stock's revenue or valuation
- sentiment NEUTRAL: policy has no meaningful impact
- horizon SHORT: market repricing within days
- horizon MEDIUM: earnings impact in 1-2 quarters
- horizon LONG: structural change over years""")

    parser = JsonOutputParser()
    chain = prompt | llm | parser
    
    for attempt in range(2):
        try:
            res = chain.invoke({
                "policy_text": policy_text,
                "ticker": ticker,
                "stock_name": stock_data['name'],
                "sector": sector,
                "stock_type": stock_data['type']
            })
            return res
        except Exception as e:
            if attempt == 1:
                return {
                    "directness": 1, 
                    "sentiment": "NEUTRAL", 
                    "horizon": "LONG", 
                    "reason": "Unable to assess impact", 
                    "error": True
                }

def calculate_score(directness: int, exposure: int, horizon: str, sentiment: str) -> dict:
    URGENCY = {"SHORT": 1.0, "MEDIUM": 0.5, "LONG": 0.0}
    SENTIMENT_MAP = {"POSITIVE": 1, "NEGATIVE": -1, "NEUTRAL": 0}
    
    urgency_val = URGENCY.get(horizon, 0.0)
    sent_val = SENTIMENT_MAP.get(sentiment, 0)
    
    raw = directness * exposure * (1 + 0.5 * urgency_val)
    final = round(raw * sent_val, 1)
    
    if final > 8:
        label = "Strong Positive"
    elif final > 4:
        label = "Moderate Positive"
    elif final > -4:
        label = "Neutral"
    elif final > -8:
        label = "Moderate Negative"
    else:
        label = "Strong Negative"
        
    return {
        "score": final,
        "label": label,
        "raw_components": {
            "directness": directness,
            "exposure": exposure,
            "horizon": horizon,
            "sentiment": sentiment
        }
    }

import concurrent.futures

def score_all_stocks(policy_text: str, sectors: list[str]) -> list[dict]:
    results = []
    
    # Collect all tasks
    tasks = []
    for sector in sectors:
        universe = STOCK_UNIVERSE.get(sector, {})
        for ticker, data in universe.items():
            tasks.append((ticker, sector, data))
            
    # Process tasks concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        future_to_stock = {
            executor.submit(get_llm_scores, policy_text, ticker, sector, data): (ticker, sector, data)
            for ticker, sector, data in tasks
        }
        
        # Gather results as they complete
        for future in concurrent.futures.as_completed(future_to_stock):
            ticker, sector, data = future_to_stock[future]
            try:
                llm_res = future.result()
            except Exception as e:
                # Fallback on error
                llm_res = {
                    "directness": 1, 
                    "sentiment": "NEUTRAL", 
                    "horizon": "LONG", 
                    "reason": "API Error: " + str(e), 
                    "error": True
                }
                
            directness = llm_res.get("directness", 1)
            sentiment = llm_res.get("sentiment", "NEUTRAL")
            horizon = llm_res.get("horizon", "LONG")
            reason = llm_res.get("reason", "")
            
            exposure = data.get("exposure", 1)
            rate_sensitivity = data.get("rate_sensitivity", 1)
            
            score_res = calculate_score(directness, exposure, horizon, sentiment)
            
            # Filter out NEUTRAL stocks with score 0
            if score_res["score"] == 0 and sentiment == "NEUTRAL":
                continue
                
            results.append({
                "ticker": ticker,
                "name": data["name"],
                "sector": sector,
                "direction": sentiment,
                "score": score_res["score"],
                "label": score_res["label"],
                "horizon": horizon,
                "reason": reason,
                "components": {
                    "directness": directness,
                    "exposure": exposure,
                    "rate_sensitivity": rate_sensitivity,
                    "horizon": horizon
                }
            })
            
    results.sort(key=lambda x: abs(x["score"]), reverse=True)
    return results
