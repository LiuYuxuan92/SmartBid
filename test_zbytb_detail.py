import asyncio
from scrapling import StealthyFetcher

async def main():
    # Fetch a detail page from zbytb.com
    url = "https://www.zbytb.com/s-zb-66369697.html"
    print(f"Fetching: {url}")
    
    resp = await StealthyFetcher.async_fetch(
        url, headless=True, solve_cloudflare=True,
        network_idle=True, timeout=45000, wait=5000
    )
    print(f"Status: {resp.status}")
    
    # Title
    h1 = resp.css("h1")
    if h1:
        print(f"Title: {(h1[0].text or '').strip()}")
    
    # Find key info
    spans = resp.css("span")
    for s in spans:
        text = (s.text or "").strip()
        if any(k in text for k in ["预算", "金额", "发布", "截止", "地区", "类型", "行业"]):
            print(f"  Span: {text[:100]}")
    
    # Paragraphs in content area
    content_divs = resp.css(".content") or resp.css(".detail") or resp.css(".article") or resp.css(".news-detail")
    if content_divs:
        print(f"\nContent div found, text length: {len(content_divs[0].text or '')}")
        print((content_divs[0].text or "")[:1000])
    else:
        # Try all p tags
        ps = resp.css("p")
        print(f"\nParagraphs: {len(ps)}")
        for p in ps[:15]:
            text = (p.text or "").strip()
            if text and len(text) > 10:
                print(f"  {text[:120]}")
    
    # Look for tables
    tds = resp.css("td")
    if tds:
        print(f"\nTable cells: {len(tds)}")
        for td in tds[:20]:
            text = (td.text or "").strip()
            if text:
                print(f"  | {text[:80]}")

asyncio.run(main())
