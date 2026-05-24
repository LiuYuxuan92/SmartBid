import asyncio
from scrapling import StealthyFetcher, Fetcher

async def main():
    # Zhejiang platform likely uses REST API
    # Try common API patterns
    apis = [
        "https://zfcg.czt.zj.gov.cn/luban/shop/search/zbgg?pageNo=1&pageSize=5",
    ]
    
    for url in apis:
        print(f"Trying: {url}")
        try:
            resp = await StealthyFetcher.async_fetch(url, headless=True, timeout=20000, wait=3000)
            print(f"  Status: {resp.status}")
            body_els = resp.css("body")
            if body_els:
                body_text = (body_els[0].text or "")
                print(f"  Body length: {len(body_text)}")
                print(f"  Body: {body_text[:500]}")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Also try direct HTTP request (no browser) with Fetcher
    print("\n--- Trying Fetcher (no browser) for API ---")
    try:
        resp = Fetcher.get("https://zfcg.czt.zj.gov.cn/luban/shop/search/zbgg?pageNo=1&pageSize=5")
        print(f"  Status: {resp.status}")
        body = resp.text or ""
        print(f"  Body length: {len(body)}")
        print(f"  Body: {body[:800]}")
    except Exception as e:
        print(f"  Error: {e}")

asyncio.run(main())
