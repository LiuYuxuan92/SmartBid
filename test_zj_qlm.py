"""Deep test: Zhejiang + Qianlima with different strategies"""
import asyncio
import sys
sys.path.insert(0, "D:/CADAI")
from scrapling import StealthyFetcher, DynamicFetcher

async def test_zhejiang():
    print("="*60)
    print("浙江省公共资源交易中心")
    print("="*60)
    
    # Try different URLs - the main page might be SPA, try their API or listing page
    urls = [
        "https://zfcg.czt.zj.gov.cn/luban/shop/zbgg",
        "https://zfcg.czt.zj.gov.cn/innerUsed_noticeDetails/index.html",
        "https://zfcg.czt.zj.gov.cn/",
    ]
    
    for url in urls:
        print(f"\n  Trying: {url}")
        try:
            response = await StealthyFetcher.async_fetch(
                url, headless=True, solve_cloudflare=True,
                network_idle=True, timeout=30000, wait=8000
            )
            print(f"  Status: {response.status}")
            links = response.css("a")
            meaningful = [(l.text or "").strip() for l in links if (l.text or "").strip() and len((l.text or "").strip()) > 5]
            print(f"  Links with text: {len(meaningful)}")
            if meaningful:
                for t in meaningful[:10]:
                    print(f"    - {t[:80]}")
            
            # Try finding any list items or table rows
            items = response.css("li")
            if items:
                li_texts = [(i.text or "").strip() for i in items if (i.text or "").strip() and len((i.text or "").strip()) > 10]
                print(f"  List items: {len(li_texts)}")
                for t in li_texts[:5]:
                    print(f"    - {t[:80]}")
            
            # Check for common SPA indicators
            divs = response.css("div[class]")
            print(f"  Divs with class: {len(divs)}")
            
            if response.status == 200 and len(meaningful) < 5:
                print("  >>> Likely SPA - content loaded via JS API calls")
            elif response.status == 200 and len(meaningful) >= 5:
                print("  >>> SUCCESS - page content accessible!")
                break
        except Exception as e:
            print(f"  Error: {str(e)[:100]}")

async def test_qianlima():
    print(f"\n{'='*60}")
    print("千里马招标网")
    print("="*60)
    
    urls = [
        "https://www.qianlima.com/zb/",
        "https://www.qianlima.com/zb/area_0_0_1.html",
        "https://www.qianlima.com/",
    ]
    
    for url in urls:
        print(f"\n  Trying: {url}")
        try:
            response = await StealthyFetcher.async_fetch(
                url, headless=True, solve_cloudflare=True,
                network_idle=True, timeout=45000, wait=8000
            )
            print(f"  Status: {response.status}")
            
            links = response.css("a")
            meaningful = [(l.text or "").strip() for l in links if (l.text or "").strip() and len((l.text or "").strip()) > 8]
            print(f"  Links with text: {len(meaningful)}")
            if meaningful:
                for t in meaningful[:15]:
                    print(f"    - {t[:80]}")
            
            # Check for bid announcement patterns
            bid_links = [t for t in meaningful if any(k in t for k in ["招标", "公告", "采购", "工程"])]
            print(f"  Bid-related links: {len(bid_links)}")
            if bid_links:
                for t in bid_links[:10]:
                    print(f"    >>> {t[:80]}")
                print("  >>> SUCCESS - bid data accessible!")
                break
            
            if response.status == 200 and not meaningful:
                print("  >>> Content empty - anti-bot active or SPA")
        except Exception as e:
            print(f"  Error: {str(e)[:100]}")

async def main():
    await test_zhejiang()
    await test_qianlima()

asyncio.run(main())
