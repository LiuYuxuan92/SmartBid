import asyncio
from scrapling import StealthyFetcher, DynamicFetcher

async def main():
    url = "https://www.qianlima.com/zb/"
    
    # Strategy 1: StealthyFetcher with longer wait
    print("Strategy 1: StealthyFetcher with 15s wait")
    try:
        resp = await StealthyFetcher.async_fetch(
            url, headless=True, solve_cloudflare=True,
            network_idle=True, timeout=60000, wait=15000
        )
        print(f"  Status: {resp.status}")
        all_els = resp.css("*")
        print(f"  Total elements: {len(all_els)}")
        links = resp.css("a")
        print(f"  Links: {len(links)}")
        for link in links[:10]:
            href = link.attrib.get("href", "")
            text = (link.text or "").strip()
            if text:
                print(f"    [{text[:50]}] -> {href[:50]}")
        # Check title
        titles = resp.css("title")
        if titles:
            print(f"  Title: {(titles[0].text or '')}")
        # Check for captcha/verify elements
        verify = resp.css("input[type=text]") or resp.css(".captcha") or resp.css("#verify")
        if verify:
            print(f"  CAPTCHA/Verify elements found: {len(verify)}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Strategy 2: DynamicFetcher (non-stealth, might work differently)
    print("\nStrategy 2: DynamicFetcher with 10s wait")
    try:
        resp = await DynamicFetcher.async_fetch(
            url, headless=True, network_idle=True, timeout=60000, wait=10000
        )
        print(f"  Status: {resp.status}")
        links = resp.css("a")
        meaningful = [(l.text or "").strip() for l in links if (l.text or "").strip()]
        print(f"  Links with text: {len(meaningful)}")
        for t in meaningful[:10]:
            print(f"    - {t[:80]}")
        titles = resp.css("title")
        if titles:
            print(f"  Title: {(titles[0].text or '')}")
    except Exception as e:
        print(f"  Error: {e}")

asyncio.run(main())
