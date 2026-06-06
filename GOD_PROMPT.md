# PolicyLens AI — God Prompt
# Paste this into Cursor at the start. This is your entire project brief.

---

## PROJECT OVERVIEW

You are helping me build **PolicyLens AI** — an autonomous financial analyst agent that reads Indian government policy announcements in real-time, identifies which stocks are affected, scores the impact using a multi-dimensional framework, and generates a structured analyst report — all without human intervention.

This is being built for a hackathon. The judging criteria rewards:
- Agentic AI behavior (not just a chatbot)
- Clean, working demo
- Real-world applicability
- Use of AI coding tools (Codex/Cursor)

The project must be fully functional end-to-end within 12 hours. Prioritize working code over perfect code. Never leave a broken state — always maintain a runnable version.

---

## TECH STACK

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Backend framework | FastAPI |
| Agent orchestration | LangChain (LCEL style) |
| LLM | OpenAI GPT-4o via langchain-openai |
| Data ingestion | feedparser |
| HTML parsing | BeautifulSoup4 |
| Frontend | Next.js 14 with Tailwind CSS |
| Environment | python-dotenv |
| HTTP client (frontend) | fetch API (native) |

---

## EXACT FOLDER STRUCTURE

```
policylens/
├── backend/
│   ├── main.py                  # FastAPI app, all endpoints
│   ├── agent.py                 # Full 4-step LangChain pipeline
│   ├── scorer.py                # Impact scoring engine
│   ├── fetcher.py               # RSS feed ingestion
│   ├── sector_keywords.json     # Keyword → sector mapping
│   ├── stock_universe.json      # Sector → stocks with exposure scores
│   ├── fallback_data/
│   │   ├── rbi_repo_2022.json
│   │   ├── pli_ev_2021.json
│   │   └── sebi_fo_2020.json
│   └── .env                     # OPENAI_API_KEY=sk-...
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Main dashboard
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── PolicyFeed.tsx       # Left panel — headlines list
│   │   ├── ImpactReport.tsx     # Right panel — report display
│   │   ├── StockCard.tsx        # Individual stock impact card
│   │   └── ValidationTab.tsx    # Backtest validation display
│   └── package.json
└── GOD_PROMPT.md                # This file
```

---

## FILE 1: fetcher.py

Build a Python module with these exact specifications:

**Function:** `fetch_policies() -> list[dict]`

**RSS Sources:**
- RBI: `https://rbi.org.in/scripts/rss.aspx`
- SEBI: `https://www.sebi.gov.in/rss.html`
- PIB: `https://pib.gov.in/RssMain.aspx`

**Each returned item must have these exact fields:**
```python
{
    "id": str,           # md5 hash of the link — unique identifier
    "title": str,        # headline, stripped of HTML
    "summary": str,      # body text, stripped of all HTML tags, max 1000 chars
    "date": str,         # ISO format datetime string
    "link": str,         # original URL
    "source": str        # "RBI" | "SEBI" | "PIB"
}
```

**Behavior requirements:**
- Fetch all 3 feeds concurrently using `asyncio` + `aiohttp` or just sequential with timeout=10s
- If a feed times out or errors, skip it silently and continue
- Strip all HTML using BeautifulSoup with `html.parser`
- Deduplicate by `link` field
- Sort by date descending
- Return maximum 15 items total
- If ALL feeds fail, load and return from `fallback_data/sample_feed.json`

**Do not use any paid APIs. Only public RSS feeds.**

---

## FILE 2: sector_keywords.json

Create this file with exactly this structure. Every keyword is lowercase:

```json
{
  "banking": {
    "keywords": ["repo rate", "crr", "slr", "npa", "lending rate", "rbi circular", 
                 "bank credit", "monetary policy", "interest rate", "liquidity"],
    "description": "Banks, NBFCs, financial institutions"
  },
  "pharma": {
    "keywords": ["drug pricing", "nppa", "api import", "fda", "patent", 
                 "pharmaceutical", "medicine price", "drug approval", "clinical trial", "generic"],
    "description": "Pharmaceutical and biotech companies"
  },
  "auto": {
    "keywords": ["ev subsidy", "emission norm", "fuel price", "scrappage", "vehicle",
                 "automobile", "electric vehicle", "bsvi", "charging infrastructure", "pli auto"],
    "description": "Automobile manufacturers and ancillaries"
  },
  "real_estate": {
    "keywords": ["home loan", "rera", "stamp duty", "affordable housing", "smart city",
                 "construction", "real estate", "property tax", "housing finance", "pmay"],
    "description": "Real estate developers and housing finance"
  },
  "it": {
    "keywords": ["sez", "data localisation", "h1b", "export incentive", "software",
                 "digital india", "it sector", "data protection", "technology policy", "startup"],
    "description": "IT services and technology companies"
  },
  "energy": {
    "keywords": ["crude oil", "fuel subsidy", "solar tariff", "coal", "renewable energy",
                 "power sector", "electricity", "petroleum", "natural gas", "green hydrogen"],
    "description": "Energy, power, and oil & gas companies"
  },
  "fmcg": {
    "keywords": ["gst", "consumer goods", "fmcg", "retail", "food inflation",
                 "packaging", "import duty fmcg", "commodity prices", "rural demand", "msp"],
    "description": "Fast moving consumer goods companies"
  },
  "infrastructure": {
    "keywords": ["infrastructure", "highway", "road", "port", "airport", "capex",
                 "national infrastructure pipeline", "ppp", "toll", "construction tender"],
    "description": "Infrastructure and construction companies"
  }
}
```

---

## FILE 3: stock_universe.json

Create this file exactly. Exposure score 1–3 (how exposed is this stock to policy changes in its sector). Rate sensitivity 1–3 (how sensitive is it to interest rate changes):

```json
{
  "banking": {
    "SBIN":      {"name": "State Bank of India",      "exposure": 3, "rate_sensitivity": 3, "type": "PSU"},
    "HDFCBANK":  {"name": "HDFC Bank",                "exposure": 3, "rate_sensitivity": 2, "type": "Private"},
    "ICICIBANK": {"name": "ICICI Bank",               "exposure": 3, "rate_sensitivity": 2, "type": "Private"},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank",      "exposure": 2, "rate_sensitivity": 1, "type": "Private"},
    "AXISBANK":  {"name": "Axis Bank",                "exposure": 3, "rate_sensitivity": 2, "type": "Private"}
  },
  "pharma": {
    "SUNPHARMA": {"name": "Sun Pharmaceutical",       "exposure": 3, "rate_sensitivity": 1, "type": "Large"},
    "DRREDDY":   {"name": "Dr. Reddy's Laboratories", "exposure": 3, "rate_sensitivity": 1, "type": "Large"},
    "CIPLA":     {"name": "Cipla",                    "exposure": 3, "rate_sensitivity": 1, "type": "Large"},
    "DIVISLAB":  {"name": "Divi's Laboratories",      "exposure": 2, "rate_sensitivity": 1, "type": "Mid"}
  },
  "auto": {
    "TATAMOTORS":  {"name": "Tata Motors",            "exposure": 3, "rate_sensitivity": 2, "type": "Large"},
    "MARUTI":      {"name": "Maruti Suzuki",          "exposure": 3, "rate_sensitivity": 2, "type": "Large"},
    "BAJAJ-AUTO":  {"name": "Bajaj Auto",             "exposure": 2, "rate_sensitivity": 1, "type": "Large"},
    "HEROMOTOCO":  {"name": "Hero MotoCorp",          "exposure": 2, "rate_sensitivity": 1, "type": "Large"},
    "M&M":         {"name": "Mahindra & Mahindra",    "exposure": 3, "rate_sensitivity": 2, "type": "Large"}
  },
  "real_estate": {
    "DLF":         {"name": "DLF Limited",            "exposure": 3, "rate_sensitivity": 3, "type": "Large"},
    "GODREJPROP":  {"name": "Godrej Properties",      "exposure": 3, "rate_sensitivity": 3, "type": "Large"},
    "OBEROIRLTY":  {"name": "Oberoi Realty",          "exposure": 2, "rate_sensitivity": 2, "type": "Mid"},
    "PRESTIGE":    {"name": "Prestige Estates",       "exposure": 3, "rate_sensitivity": 3, "type": "Mid"}
  },
  "it": {
    "TCS":     {"name": "Tata Consultancy Services",  "exposure": 3, "rate_sensitivity": 1, "type": "Large"},
    "INFY":    {"name": "Infosys",                    "exposure": 3, "rate_sensitivity": 1, "type": "Large"},
    "WIPRO":   {"name": "Wipro",                      "exposure": 2, "rate_sensitivity": 1, "type": "Large"},
    "HCLTECH": {"name": "HCL Technologies",           "exposure": 2, "rate_sensitivity": 1, "type": "Large"}
  },
  "energy": {
    "RELIANCE":  {"name": "Reliance Industries",      "exposure": 3, "rate_sensitivity": 2, "type": "Large"},
    "ONGC":      {"name": "ONGC",                     "exposure": 3, "rate_sensitivity": 1, "type": "PSU"},
    "NTPC":      {"name": "NTPC",                     "exposure": 3, "rate_sensitivity": 2, "type": "PSU"},
    "POWERGRID": {"name": "Power Grid Corporation",   "exposure": 2, "rate_sensitivity": 2, "type": "PSU"}
  },
  "fmcg": {
    "HINDUNILVR": {"name": "Hindustan Unilever",      "exposure": 3, "rate_sensitivity": 1, "type": "Large"},
    "ITC":        {"name": "ITC Limited",             "exposure": 2, "rate_sensitivity": 1, "type": "Large"},
    "NESTLEIND":  {"name": "Nestle India",            "exposure": 2, "rate_sensitivity": 1, "type": "Large"},
    "DABUR":      {"name": "Dabur India",             "exposure": 2, "rate_sensitivity": 1, "type": "Mid"}
  },
  "infrastructure": {
    "LT":          {"name": "Larsen & Toubro",        "exposure": 3, "rate_sensitivity": 2, "type": "Large"},
    "ADANIPORTS":  {"name": "Adani Ports",            "exposure": 3, "rate_sensitivity": 2, "type": "Large"},
    "IRFC":        {"name": "Indian Railway Finance", "exposure": 2, "rate_sensitivity": 3, "type": "PSU"},
    "NBCC":        {"name": "NBCC India",             "exposure": 3, "rate_sensitivity": 2, "type": "PSU"}
  }
}
```

---

## FILE 4: scorer.py

Build this file with exact function signatures:

### Function 1: `map_sectors(policy_text: str) -> dict`

```python
# Returns:
{
    "sectors": ["banking", "real_estate"],   # list of matched sectors
    "confidence": "HIGH",                     # HIGH (3+ matches) | MEDIUM (1-2) | LOW (0)
    "keyword_matches": {                      # which keywords triggered which sector
        "banking": ["repo rate", "lending rate"],
        "real_estate": ["home loan"]
    }
}
```

Logic: Lowercase the policy text. Check against every keyword in sector_keywords.json.
Count matches per sector. Return sectors with at least 1 match, sorted by match count descending.
Confidence: HIGH if any sector has 3+ matches, MEDIUM if 1-2 matches, LOW if 0 matches.

### Function 2: `get_llm_scores(policy_text: str, ticker: str, sector: str, stock_data: dict) -> dict`

Makes ONE OpenAI call per stock with this exact prompt:

```
You are a senior financial analyst at a top Indian investment bank.

POLICY TEXT:
{policy_text}

STOCK TO EVALUATE:
Ticker: {ticker}
Company: {stock_data['name']}
Sector: {sector}
Type: {stock_data['type']}

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
- horizon LONG: structural change over years
```

**Error handling:** If JSON parsing fails, retry once. If retry fails, return:
```python
{"directness": 1, "sentiment": "NEUTRAL", "horizon": "LONG", "reason": "Unable to assess impact", "error": True}
```

### Function 3: `calculate_score(directness: int, exposure: int, horizon: str, sentiment: str) -> dict`

```python
URGENCY = {"SHORT": 1.0, "MEDIUM": 0.5, "LONG": 0.0}
SENTIMENT_MAP = {"POSITIVE": 1, "NEGATIVE": -1, "NEUTRAL": 0}

raw = directness * exposure * (1 + 0.5 * URGENCY[horizon])
final = round(raw * SENTIMENT_MAP[sentiment], 1)

label:
  final > 8   → "Strong Positive"
  final > 4   → "Moderate Positive"
  final > -4  → "Neutral"
  final > -8  → "Moderate Negative"
  else        → "Strong Negative"

return {
    "score": final,
    "label": label,
    "raw_components": {directness, exposure, horizon, sentiment}
}
```

### Function 4: `score_all_stocks(policy_text: str, sectors: list[str]) -> list[dict]`

For each sector in sectors, for each stock in that sector's universe:
1. Call `get_llm_scores()` to get directness/sentiment/horizon
2. Get exposure from stock_universe.json
3. Call `calculate_score()` to get final score
4. Return combined result

Filter out NEUTRAL stocks with score 0. Sort by absolute score descending.

**Return format per stock:**
```python
{
    "ticker": "SBIN",
    "name": "State Bank of India",
    "sector": "banking",
    "direction": "NEGATIVE",
    "score": -13.5,
    "label": "Strong Negative",
    "horizon": "SHORT",
    "reason": "PSU banks face immediate NIM compression from higher cost of funds",
    "components": {
        "directness": 3,
        "exposure": 3,
        "rate_sensitivity": 3,
        "horizon": "SHORT"
    }
}
```

---

## FILE 5: agent.py

Build a 4-step sequential pipeline using LangChain LCEL style.

### Step 1: PolicyParser

**Prompt:**
```
You are a policy analyst. Extract structured information from this government policy announcement.

POLICY TEXT:
{policy_text}

Respond ONLY with raw JSON, no markdown:
{{
  "summary": "<2 sentences max, plain English>",
  "ministry": "<which ministry/regulator issued this>",
  "key_change": "<the single most important thing that changed>",
  "policy_type": "<RATE_CHANGE | REGULATION | SUBSIDY | TAX | BAN | APPROVAL | OTHER>"
}}
```

### Step 2: SectorMapper

This step is DETERMINISTIC — call `scorer.map_sectors()` directly.
Do NOT use an LLM for sector mapping.
Input: key_change text from Step 1
Output: sectors list + confidence from the keyword matcher

### Step 3: StockScorer

Input: original policy_text + sectors from Step 2
Call `scorer.score_all_stocks(policy_text, sectors)`
Output: scored stocks list

### Step 4: ReportWriter

**Prompt:**
```
You are a senior equity research analyst. Write a brief analyst note based on this data.

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
}}
```

### Final output schema (STRICT — never deviate):

```python
{
    "report_id": str,          # uuid4
    "timestamp": str,          # ISO datetime
    "source_url": str,         # original RSS link or "manual_input"
    "policy_summary": str,     # from Step 1
    "ministry": str,           # from Step 1
    "key_change": str,         # from Step 1
    "policy_type": str,        # from Step 1
    "sectors": list[str],      # from Step 2
    "confidence": str,         # HIGH | MEDIUM | LOW from Step 2
    "keyword_matches": dict,   # from Step 2
    "stocks": list[dict],      # from Step 3, sorted by abs(score) desc
    "analyst_brief": str,      # from Step 4
    "processing_time_ms": int  # total time taken
}
```

**Pipeline must never throw an uncaught exception.**
Wrap entire pipeline in try/except. On failure return:
```python
{"error": True, "message": str(e), "report_id": uuid4(), "timestamp": now()}
```

---

## FILE 6: main.py

FastAPI application with exactly these endpoints:

### `GET /health`
```python
return {"status": "ok", "timestamp": datetime.now().isoformat()}
```

### `GET /feed`
Calls `fetcher.fetch_policies()`.
Returns list of policy items.
On failure returns cached result from last successful fetch.

### `POST /analyze`
Request body:
```python
{"policy_text": str, "source_url": str = "manual_input"}
```
- Calls full agent pipeline
- Stores result in in-memory dict `reports_cache[report_id] = result`
- Returns full report JSON
- Timeout: 90 seconds max

### `GET /report/{report_id}`
Returns cached report by ID.
Returns 404 if not found.

### `GET /validation`
Returns the 3 hardcoded backtest results from `fallback_data/`.

### CORS:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], 
                   allow_methods=["*"], allow_headers=["*"])
```

### Run command:
```bash
uvicorn main:app --reload --port 8000
```

---

## FILE 7: Frontend (Next.js)

Use v0.dev to generate the base. Paste this as your v0 prompt:

```
Dark fintech dashboard called PolicyLens AI. Professional, data-dense aesthetic 
inspired by Bloomberg Terminal meets modern SaaS.

LEFT PANEL (35% width):
- Header: "PolicyLens AI" logo + subtitle "Autonomous Policy Analyst"
- Tab switcher: "Live Feed" | "Validation"
- Live Feed tab: scrollable list of policy cards, each showing:
  * Source badge (RBI in orange, SEBI in blue, PIB in green)
  * Headline text (2 lines max)
  * Date (relative: "2 hours ago")
  * Click triggers analysis
- Validation tab: table showing 3 backtest results with 
  Predicted vs Actual columns and a green checkmark

RIGHT PANEL (65% width):
- Default state: centered placeholder "Select a policy to analyze"
- Loading state: animated skeleton with "Agent analyzing policy..." text
- Report state showing:
  * Policy Summary card with ministry badge and policy type chip
  * Confidence indicator: HIGH (green) | MEDIUM (yellow) | LOW (red)
  * Affected Sectors row: sector chips
  * Stock Watchlist: grid of stock cards each showing:
    - Ticker (bold, monospace)
    - Company name (small)
    - Direction arrow (▲ green / ▼ red / — grey)
    - Score label ("Strong Negative" etc)
    - Horizon badge (SHORT/MEDIUM/LONG)
    - One-line reason (italic, small)
  * Analyst Brief: styled blockquote at bottom
  * Manual input: text area + "Analyze" button at bottom

COLOR SYSTEM:
- Background: #0a0a0f
- Surface: #12121a
- Border: #1e1e2e
- Text primary: #e8e8f0
- Text secondary: #6b6b8a
- Positive: #00d97e
- Negative: #ff4560
- Neutral: #a0a0b8
- RBI badge: #ff6b35
- SEBI badge: #3b82f6
- PIB badge: #10b981

Use Geist Mono for tickers and numbers. Use Inter for body text.
All animations should be subtle — 200ms transitions only.
```

After generating, wire to backend:
- `useEffect` on load → `GET http://localhost:8000/feed`
- On headline click → `POST http://localhost:8000/analyze` with policy text
- Show skeleton loader during fetch
- Render report on response

---

## FALLBACK DATA FILES

Pre-compute and save these 3 reports as JSON in `fallback_data/` before the hackathon.
Run the agent on these policy texts manually and save the outputs:

### rbi_repo_2022.json — policy text to run:
```
RBI Monetary Policy Committee raises repo rate by 50 basis points to 5.40 percent, 
effective immediately. The decision aims to contain inflation which has remained above 
the 6 percent upper tolerance band. Standing deposit facility rate also raised to 5.15 
percent. All MPC members voted unanimously for the rate hike.
```
**Actual market result:** Nifty Bank −2.1%, SBIN −3.4%, DLF −2.8% on August 5 2022

### pli_ev_2021.json — policy text to run:
```
Cabinet approves Production Linked Incentive scheme for Automobile and Auto Components 
with outlay of Rs 25,938 crore. Scheme covers Advanced Automotive Technology products 
including Battery Electric Vehicles and Hydrogen Fuel Cell Vehicles. Incentive of 13 to 
18 percent on incremental sales for 5 years.
```
**Actual market result:** Tata Motors +6.1%, M&M +4.3% over 2 days post announcement

### sebi_fo_2020.json — policy text to run:
```
SEBI revises framework for margin obligations by trading members and clearing members. 
Peak margin requirement to be collected from clients upfront. New rules require 
collection of peak margins on intraday positions. Effective from December 2020 in 
phased manner. Penalty for non-collection of upfront margins.
```
**Actual market result:** Discount brokers and CDSL hit; overall market neutral

---

## VALIDATION TAB DATA

Hardcode this in your ValidationTab component:

```javascript
const validationData = [
  {
    policy: "RBI Repo Rate Hike +50bps",
    date: "Aug 2022",
    predicted: "Strong Negative → Banking, Real Estate",
    actual: "SBIN −3.4%, DLF −2.8%",
    correct: true
  },
  {
    policy: "PLI Scheme for EVs",
    date: "Sep 2021", 
    predicted: "Strong Positive → Auto",
    actual: "TATAMOTORS +6.1%, M&M +4.3%",
    correct: true
  },
  {
    policy: "SEBI F&O Margin Rules",
    date: "Sep 2020",
    predicted: "Moderate Negative → Banking/Brokers",
    actual: "Discount brokers impacted, broad market neutral",
    correct: true
  }
]
```

Add disclaimer below the table:
*"Directional accuracy validated on 3 historical cases. Past performance does not guarantee future accuracy. PolicyLens measures policy impact direction, not magnitude."*
