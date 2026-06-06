from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json
import os
from dotenv import load_dotenv

import fetcher
import agent

load_dotenv()

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

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

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
    result = agent.run_pipeline(request.policy_text, request.source_url)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    report_id = result["report_id"]
    reports_cache[report_id] = result
    return result

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
