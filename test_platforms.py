"""Test which mainstream bidding platforms we can access with StealthyFetcher"""
import asyncio
import sys
sys.path.insert(0, "D:/CADAI")

from scrapling import StealthyFetcher, DynamicFetcher, Fetcher

PLATFORMS = [
    ("中国政府采购网", "http://www.ccgp.gov.cn/cggg/zygg/gkzb/"),
    ("全国公共资源交易平台", "http://deal.ggzy.gov.cn/"),
    ("中国招标投标公共服务平台", "https://www.cebpubservice.com/"),
    ("北京公共资源交易网", "https://ggzyfw.beijing.gov.cn/jyxx/jsgcZbgg"),
    ("上海公共资源交易平台", "https://www.shggzy.com/website/jyxx_list.html"),
    ("广东省公共资源交易平台", "https://gdggzy.org.cn/"),
    ("浙江省公共资源交易中心", "https://zfcg.czt.zj.gov.cn/"),
    ("比地招标网", "https://www.bidcenter.com.cn/"),
    ("中国采招网", "https://www.zbytb.com/"),
    ("千里马招标网", "https://www.qianlima.com/zb/"),
]

async def test_platform(name, url):
    try:
        response = await StealthyFetcher.async_fetch(
            url, headless=True, solve_cloudflare=True,
            network_idle=True, timeout=30000, wait=3000
        )
        # Count meaningful links
        links = response.css("a")
        meaningful = [l for l in links if (l.text or "").strip() and len((l.text or "").strip()) > 5]
        status = response.status
        has_content = len(meaningful) > 5
        return (name, url, status, len(meaningful), has_content, None)
    except Exception as e:
        return (name, url, 0, 0, False, str(e)[:80])

async def main():
    print(f"{'Platform':<30s} | {'Status':>6s} | {'Links':>5s} | {'Result'}")
    print("-" * 85)
    
    for name, url in PLATFORMS:
        result = await test_platform(name, url)
        name, url, status, links, has_content, error = result
        if error:
            print(f"{name:<30s} | {'ERR':>6s} | {0:>5d} | FAILED: {error[:40]}")
        elif has_content:
            print(f"{name:<30s} | {status:>6d} | {links:>5d} | OK - can scrape")
        else:
            print(f"{name:<30s} | {status:>6d} | {links:>5d} | BLOCKED/EMPTY")

asyncio.run(main())
