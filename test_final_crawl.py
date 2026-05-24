"""Final test: CCGP central + local announcements"""
import sys, json, logging
sys.path.insert(0, "D:/CADAI")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from src.crawler.crawler_module import CrawlerModule

config = {
    "crawler": {
        "target_platforms": [
            {"url": "http://www.ccgp.gov.cn/cggg/zygg/gkzb/", "name": "政采网-中央", "parser": "CCGPParser"},
            {"url": "http://www.ccgp.gov.cn/cggg/dfgg/gkzb/", "name": "政采网-地方", "parser": "CCGPParser"},
        ],
        "connection_timeout": 120,
        "request_timeout": 30,
        "page_wait": 5000,
        "max_details_per_platform": 3,
    }
}

module = CrawlerModule()
result = module.execute({}, config)

print(f"\n{'='*60}")
print(f"CCGP双板块 (中央+地方) 抓取结果")
print(f"{'='*60}")
print(f"  公告总数: {len(result['announcements'])}")
print(f"  不完整: {result['incomplete_count']}")
print(f"  跳过平台: {len(result['skipped_platforms'])}")
print(f"  耗时: {result['total_elapsed']:.1f}s")

for i, ann in enumerate(result["announcements"]):
    budget = f"{ann['budget_amount']/10000:.1f}万" if ann['budget_amount'] else "N/A"
    print(f"\n[{i+1}] [{ann['source_platform']}]")
    print(f"    {ann['title'][:65]}")
    print(f"    预算:{budget} | 截止:{ann['deadline'] or 'N/A'}")

with open("D:/CADAI/output/final_crawl.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nSaved to D:/CADAI/output/final_crawl.json")
