import asyncio, sys
sys.path.insert(0, "D:/CADAI")
from scrapling import StealthyFetcher

async def main():
    resp = await StealthyFetcher.async_fetch(
        "https://www.zbytb.com/", headless=True, solve_cloudflare=True,
        network_idle=True, timeout=90000, wait=10000
    )
    print(f"Status: {resp.status}")
    links = resp.css("a")
    bids = []
    for link in links:
        href = link.attrib.get("href", "")
        text = (link.text or "").strip()
        if "/s-zb-" in href and text and len(text) > 10:
            bids.append({"title": text, "href": href})
    print(f"Bid links: {len(bids)}")
    for b in bids[:8]:
        print(f"  {b['title'][:70]}")

asyncio.run(main())
