import asyncio
from scrapling import StealthyFetcher

async def main():
    url = "https://www.zbytb.com/zbgg/"
    print(f"Fetching listing: {url}")
    
    resp = await StealthyFetcher.async_fetch(
        url, headless=True, solve_cloudflare=True,
        network_idle=True, timeout=60000, wait=8000
    )
    print(f"Status: {resp.status}")
    
    # Get all links with their surrounding context
    links = resp.css("a")
    print(f"Total links: {len(links)}")
    
    # Look for list items that contain announcement info
    lis = resp.css("li")
    print(f"List items: {len(lis)}")
    for li in lis[:20]:
        text = (li.text or "").strip()
        if text and len(text) > 15:
            # Get the link inside this li
            inner_links = li.css("a")
            href = inner_links[0].attrib.get("href", "") if inner_links else ""
            print(f"  {text[:100]}")
            if href:
                print(f"    -> {href}")
            print()

    # Also check for date/region spans near links
    print("\n--- Looking for structured listing items ---")
    divs = resp.css("div")
    for div in divs:
        text = (div.text or "").strip()
        # Look for patterns like date + title
        if text and "2026" in text and len(text) > 20 and len(text) < 200:
            print(f"  {text[:150]}")

asyncio.run(main())
