import uuid
import time
from datetime import datetime
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableLambda

import scorer

def run_pipeline(policy_text: str, source_url: str = "manual_input") -> dict:
    start_time = time.time()
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        
        # Step 1: PolicyParser
        parser_prompt = PromptTemplate.from_template("""You are a policy analyst. Extract structured information from this government policy announcement.

POLICY TEXT:
{policy_text}

Respond ONLY with raw JSON, no markdown:
{{
  "summary": "<2 sentences max, plain English>",
  "ministry": "<which ministry/regulator issued this>",
  "key_change": "<the single most important thing that changed>",
  "policy_type": "<RATE_CHANGE | REGULATION | SUBSIDY | TAX | BAN | APPROVAL | OTHER>"
}}""")
        step1_chain = parser_prompt | llm | JsonOutputParser()
        parsed_policy = step1_chain.invoke({"policy_text": policy_text})
        
        # Step 2: SectorMapper (DETERMINISTIC)
        mapping_result = scorer.map_sectors(parsed_policy.get("key_change", ""))
        sectors = mapping_result.get("sectors", [])
        
        # Step 3: StockScorer
        stocks = scorer.score_all_stocks(policy_text, sectors)
        
        # Step 4: ReportWriter
        report_prompt = PromptTemplate.from_template("""You are a senior equity research analyst. Write a brief analyst note based on this data.

Policy: {policy_summary}
Ministry: {ministry}
Affected sectors: {sectors}
Top impacted stocks: {top_stocks_json}

Write a 3-sentence analyst brief that:
1. States what changed and which sectors are affected
2. Names the 2-3 most impacted stocks and why
3. Gives a one-line investment implication

Respond ONLY with a JSON object:
{{
  "analyst_brief": "<your 3-sentence brief here>"
}}""")
        top_stocks = stocks[:3] if stocks else []
        step4_chain = report_prompt | llm | JsonOutputParser()
        report_res = step4_chain.invoke({
            "policy_summary": parsed_policy.get("summary", ""),
            "ministry": parsed_policy.get("ministry", ""),
            "sectors": json.dumps(sectors),
            "top_stocks_json": json.dumps(top_stocks)
        })
        
        end_time = time.time()
        
        return {
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "source_url": source_url,
            "policy_summary": parsed_policy.get("summary", ""),
            "ministry": parsed_policy.get("ministry", ""),
            "key_change": parsed_policy.get("key_change", ""),
            "policy_type": parsed_policy.get("policy_type", ""),
            "sectors": sectors,
            "confidence": mapping_result.get("confidence", "LOW"),
            "keyword_matches": mapping_result.get("keyword_matches", {}),
            "stocks": stocks,
            "analyst_brief": report_res.get("analyst_brief", ""),
            "processing_time_ms": int((end_time - start_time) * 1000)
        }
        
    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat()
        }
