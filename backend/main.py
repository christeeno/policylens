from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json
import os
from dotenv import load_dotenv

import fetcher
import agent
from exposure_engine import get_exposure_score, load_json as load_backend_json, refresh_exposure_scores
from stocks_service import StockDataError, StockDataUnavailableError, StockNotFoundError, fetch_stock_history

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(title="PolicyLens AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory caches
reports_cache = {}
last_feed_cache = []

class AnalyzeRequest(BaseModel):
    policy_text: str
    source_url: str = "manual_input"
    source_type: str = ""
    publisher: str = ""
    article_class: str = ""
    classification_confidence: float | None = None
    classification_reasoning: str = ""


class ExposureRefreshRequest(BaseModel):
    fundamentals_file: str = "company_fundamentals.json"
    output_file: str = "exposure_scores.json"

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/stocks/{ticker}/history")
def get_stock_history(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
):
    try:
        return fetch_stock_history(
            ticker=ticker,
            period=period,
            interval=interval,
            start=start,
            end=end,
        )
    except StockNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StockDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except StockDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected stock data error: {exc}")

@app.get("/feed")
def get_feed():
    global last_feed_cache
    try:
        items = fetcher.fetch_policies()
        if items:
            last_feed_cache = items
            return items
        else:
            return last_feed_cache
    except Exception as e:
        if last_feed_cache:
            return last_feed_cache
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
def analyze_policy(request: AnalyzeRequest):
    result = agent.run_pipeline(
        request.policy_text,
        request.source_url,
        source_type=request.source_type,
        publisher=request.publisher,
        article_class=request.article_class,
        classification_confidence=request.classification_confidence,
        classification_reasoning=request.classification_reasoning,
    )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    report_id = result["report_id"]
    reports_cache[report_id] = result
    return result


@app.post("/exposure/refresh")
def refresh_exposure(request: ExposureRefreshRequest):
    try:
        return refresh_exposure_scores(
            fundamentals_file=request.fundamentals_file,
            output_file=request.output_file,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/exposure/{ticker}")
def get_exposure(ticker: str):
    score, details = get_exposure_score(ticker.upper())
    if details is None:
        raise HTTPException(status_code=404, detail=f"Exposure score not found for ticker {ticker.upper()}")

    return {
        "ticker": ticker.upper(),
        "score_1_to_5": score,
        "details": details,
    }


@app.get("/exposure")
def list_exposure_scores():
    try:
        return load_backend_json("exposure_scores.json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Exposure scores file has not been generated yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/report/{report_id}")
def get_report(report_id: str):
    if report_id in reports_cache:
        return reports_cache[report_id]
    raise HTTPException(status_code=404, detail="Report not found")

@app.get("/validation")
def get_validation():
    base_dir = os.path.dirname(__file__)
    fallback_dir = os.path.join(base_dir, "fallback_data")
    
    results = []
    for filename in ["rbi_repo_2022.json", "pli_ev_2021.json", "sebi_fo_2020.json"]:
        filepath = os.path.join(fallback_dir, filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
        except Exception:
            pass
            
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
