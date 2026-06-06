import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime
import json
import os

RSS_SOURCES = {
    "RBI": "https://news.google.com/rss/search?q=RBI+policy&hl=en-IN&gl=IN&ceid=IN:en",
    "SEBI": "https://news.google.com/rss/search?q=SEBI+circular+OR+policy&hl=en-IN&gl=IN&ceid=IN:en",
    "Govt": "https://news.google.com/rss/search?q=India+finance+ministry+policy&hl=en-IN&gl=IN&ceid=IN:en"
}

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return text[:1000]

async def fetch_feed(session: aiohttp.ClientSession, source: str, url: str) -> list[dict]:
    items = []
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                feed = feedparser.parse(content)
                for entry in feed.entries:
                    link = entry.get("link", "")
                    title = clean_html(entry.get("title", ""))
                    summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
                    
                    # Some feeds might not have a proper date, fallback to now
                    date_str = entry.get("published", "") or entry.get("updated", "")
                    
                    if not link or not title:
                        continue
                        
                    item_id = hashlib.md5(link.encode('utf-8')).hexdigest()
                    
                    items.append({
                        "id": item_id,
                        "title": title,
                        "summary": summary,
                        "date": date_str,
                        "link": link,
                        "source": source
                    })
    except Exception as e:
        print(f"Error fetching {source}: {e}")
    return items

async def fetch_all_feeds() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        tasks = []
        for source, url in RSS_SOURCES.items():
            tasks.append(fetch_feed(session, source, url))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_items = []
        for res in results:
            if isinstance(res, list):
                all_items.extend(res)
        return all_items

def get_fallback_feed() -> list[dict]:
    fallback_path = os.path.join(os.path.dirname(__file__), "fallback_data", "sample_feed.json")
    try:
        with open(fallback_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load fallback feed: {e}")
        return []

def fetch_policies() -> list[dict]:
    # Run async fetcher in a synchronous wrapper
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    items = loop.run_until_complete(fetch_all_feeds())
    
    if not items:
        items = get_fallback_feed()
        
    # Deduplicate by link
    seen_links = set()
    unique_items = []
    for item in items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique_items.append(item)
            
    # Sort by date descending (assuming string sort works well enough for ISO, or we try to parse it)
    # feedparser gives varied date formats. A safer bet is just string fallback, but let's try to parse if possible.
    from datetime import datetime, timezone

    def parse_date(date_string):
        try:
            # typical format: "Wed, 31 Dec 2025 08:00:00 GMT"
            dt = datetime.strptime(date_string, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.replace(tzinfo=timezone.utc)
        except:
            return datetime.min.replace(tzinfo=timezone.utc)
            
    try:
        unique_items.sort(key=lambda x: parse_date(x.get("date", "")), reverse=True)
    except Exception as e:
        print(f"Sorting error: {e}")
        
    return unique_items[:15]

if __name__ == "__main__":
    policies = fetch_policies()
    print(f"Fetched {len(policies)} policies.")
    for p in policies[:2]:
        print(p)
