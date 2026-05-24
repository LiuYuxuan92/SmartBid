import asyncio
from scrapling import StealthyFetcher

async def explore(name, url):
    print(f"\n{'='*60}")
    print(f"{name}: {url}")
    print("="*60)
    
    resp = await StealthyFetcher.async_fetch(
        url, headless=True, solve_cloudflare=True,
        network_idle=True, timeout=45000, wait=5000
    )
    print(f"Status: {resp.status}")
    
    # Get links that look like bid announcements
    links = resp.css("a")
    bid_links = []
    for link in links:
        href = link.attrib.get("href", "")
        text = (link.text or "").strip()
        if text and len(text) > 10 and any(k in text for k in ["招标", "公告", "采购", "工程", "项目"]):
            bid_links.append({"text": text[:80], "href": href[:120]})
    
    print(f"Bid-related links: {len(bid_links)}")
    for item in bid_links[:15]:
        print(f"  [{item['text']}]")
        print(f"    -> {item['href']}")
    
    # Also show some structural info
    print(f"\n  All links: {len(links)}")
    tables = resp.css("table")
    print(f"  Tables: {len(tables)}")
    lists = resp.css("ul, ol")
    print(f"  Lists: {len(lists)}")
    divs_with_class = resp.css("div[class]")
    print(f"  Divs: {len(divs_with_class)}")

async def main():
    await explore("比地招标网", "https://www.bidcenter.com.cn/newschannel-0-1.html")
    await explore("中国采招网", "https://www.zbytb.com/zbgg/")

asyncio.run(main())
