"""Live test: Multi-platform crawl (CCGP + ZBYTB)"""
import sys
import json
import logging

sys.path.insert(0, "D:/CADAI")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from src.crawler.crawler_module import CrawlerModule

config = {
    "crawler": {
        "target_platforms": [
            {
                "url": "http://www.ccgp.gov.cn/cggg/zygg/gkzb/",
                "name": "中国政府采购网",
                "parser": "CCGPParser",
            },
            {
                "url": "https://www.zbytb.com/zbgg/",
                "name": "中国采招网",
                "parser": "ZBYTBParser",
            },
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
print(f"Multi-Platform Crawl Summary")
print(f"{'='*60}")
print(f"  Total announcements: {len(result['announcements'])}")
print(f"  Incomplete: {result['incomplete_count']}")
print(f"  Skipped platforms: {len(result['skipped_platforms'])}")
print(f"  Elapsed: {result['total_elapsed']:.2f}s")

if result['skipped_platforms']:
    print(f"\n  Skipped:")
    for s in result['skipped_platforms']:
        print(f"    - {s['name']}: {s['reason'][:60]}")

print(f"\n{'='*60}")
print("Announcements:")
print("="*60)
for i, ann in enumerate(result["announcements"]):
    status = "COMPLETE" if ann["is_complete"] else "INCOMPLETE"
    budget_str = f"{ann['budget_amount']:,.0f}" if ann['budget_amount'] else "N/A"
    print(f"\n[{i+1}] [{ann['source_platform']}] {ann['title'][:60]}")
    print(f"    Budget: {budget_str} | Deadline: {ann['deadline'] or 'N/A'} | {status}")

# Save
with open("D:/CADAI/output/multi_platform_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nSaved to D:/CADAI/output/multi_platform_result.json")
