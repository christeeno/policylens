import asyncio
import aiohttp
import feedparser
import traceback

async def test():
    try:
        async with aiohttp.ClientSession() as session:
            print("Testing RBI...")
            async with session.get('https://rbi.org.in/scripts/rss.aspx', timeout=10) as res:
                content = await res.text()
                feed = feedparser.parse(content)
                print('RBI entries:', len(feed.entries))
            
            print("Testing SEBI...")
            async with session.get('https://www.sebi.gov.in/rss.html', timeout=10) as res2:
                content = await res2.text()
                feed = feedparser.parse(content)
                print('SEBI entries:', len(feed.entries))
                
            print("Testing PIB...")
            async with session.get('https://pib.gov.in/RssMain.aspx', timeout=10) as res3:
                content = await res3.text()
                feed = feedparser.parse(content)
                print('PIB entries:', len(feed.entries))
    except Exception as e:
        traceback.print_exc()

asyncio.run(test())
