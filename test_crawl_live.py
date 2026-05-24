"""Live test: run CrawlerModule against ccgp.gov.cn"""
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
            }
        ],
        "connection_timeout": 120,
        "request_timeout": 30,
        "page_wait": 5000,
        "max_details_per_platform": 3,  # Only 3 for testing
    }
}

module = CrawlerModule()
result = module.execute({}, config)

print(f"\n{'='*60}")
print(f"Crawl Result Summary:")
print(f"  Total announcements: {len(result['announcements'])}")
print(f"  Incomplete: {result['incomplete_count']}")
print(f"  Skipped platforms: {len(result['skipped_platforms'])}")
print(f"  Elapsed: {result['total_elapsed']:.2f}s")
print(f"{'='*60}")

for i, ann in enumerate(result["announcements"]):
    print(f"\n[{i+1}] {ann['title'][:70]}")
    print(f"    预算: {ann['budget_amount']}")
    print(f"    发布: {ann['publish_date']}")
    print(f"    截止: {ann['deadline']}")
    print(f"    完整: {ann['is_complete']}")
    if ann["missing_fields"]:
        print(f"    缺失: {ann['missing_fields']}")

# Save full result
with open("D:/CADAI/output/live_crawl_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nFull result saved to D:/CADAI/output/live_crawl_result.json")
