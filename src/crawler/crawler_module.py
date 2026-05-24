"""爬虫主逻辑模块

使用 Scrapling StealthyFetcher 绕过反爬保护，
从配置的招标平台抓取公告结构化数据。
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from src.pipeline.orchestrator import BaseModule
from src.crawler.anti_crawl import AntiCrawlEngine

logger = logging.getLogger(__name__)

# Required fields for a complete announcement
REQUIRED_FIELDS = ["title", "publish_date", "deadline", "project_category", "budget_amount"]


@dataclass
class BidAnnouncement:
    """招标公告数据结构"""
    title: str  # max 200 chars, truncated
    publish_date: str  # ISO 8601
    deadline: Optional[str]  # nullable
    project_category: str
    budget_amount: Optional[float]  # CNY, nullable
    attachment_links: list[str]
    source_platform: str
    announcement_id: str
    is_complete: bool = True
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class CrawlResult:
    """爬取结果汇总"""
    announcements: list[BidAnnouncement] = field(default_factory=list)
    incomplete_count: int = 0
    skipped_platforms: list[dict] = field(default_factory=list)  # [{name, reason}]
    total_elapsed: float = 0.0


class CrawlerModule(BaseModule):
    """爬虫模块 - 使用 Scrapling StealthyFetcher 抓取招标信息"""

    @property
    def name(self) -> str:
        return "Crawler"

    def validate_input(self, input_data: dict) -> bool:
        return True

    def execute(self, input_data: dict, config: dict) -> dict:
        """执行爬取任务（同步入口，内部运行asyncio）"""
        start_time = time.time()

        crawler_config = config.get("crawler", {})
        platforms = crawler_config.get("target_platforms", [])

        result = CrawlResult()

        for platform in platforms:
            platform_name = platform.get("name", "unknown")
            try:
                announcements = self._crawl_platform_sync(platform, crawler_config)
                result.announcements.extend(announcements)
            except Exception as e:
                logger.error("Platform '%s' failed: %s", platform_name, str(e))
                result.skipped_platforms.append({
                    "name": platform_name,
                    "reason": str(e),
                })

        result.incomplete_count = sum(
            1 for a in result.announcements if not a.is_complete
        )
        result.total_elapsed = time.time() - start_time

        logger.info(
            "Crawl completed: %d announcements, %d incomplete, %d skipped, %.2fs",
            len(result.announcements),
            result.incomplete_count,
            len(result.skipped_platforms),
            result.total_elapsed,
        )

        return self._serialize_result(result)

    def _crawl_platform_sync(self, platform: dict, crawler_config: dict) -> list[BidAnnouncement]:
        """同步包装，调用异步抓取逻辑"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create a new loop in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._crawl_platform_async(platform, crawler_config))
                    return future.result()
            else:
                return loop.run_until_complete(self._crawl_platform_async(platform, crawler_config))
        except RuntimeError:
            return asyncio.run(self._crawl_platform_async(platform, crawler_config))

    async def _crawl_platform_async(self, platform: dict, crawler_config: dict) -> list[BidAnnouncement]:
        """使用 Scrapling StealthyFetcher 抓取平台"""
        from scrapling import StealthyFetcher

        platform_name = platform.get("name", "unknown")
        platform_url = platform.get("url", "")
        parser_name = platform.get("parser", "")
        timeout = crawler_config.get("connection_timeout", 120) * 1000  # ms
        wait_ms = crawler_config.get("page_wait", 5000)
        max_details = crawler_config.get("max_details_per_platform", 20)

        logger.info("Crawling platform '%s' at %s", platform_name, platform_url)

        # Step 1: Fetch listing page
        response = await StealthyFetcher.async_fetch(
            platform_url,
            headless=True,
            solve_cloudflare=True,
            network_idle=True,
            timeout=timeout,
            wait=wait_ms,
        )

        if response.status != 200:
            raise Exception(f"Listing page returned status {response.status}")

        # Step 2: Parse listing using appropriate parser
        parser = self._get_parser(parser_name)
        listings = parser.parse_listing(response)
        logger.info("Found %d listings on '%s'", len(listings), platform_name)

        # Step 3: Fetch details for each announcement (up to max_details)
        announcements = []
        for listing in listings[:max_details]:
            try:
                ann = await self._fetch_and_parse_detail(
                    listing, parser, platform_name, timeout, wait_ms
                )
                announcements.append(ann)
            except Exception as e:
                logger.warning("Failed to fetch detail for '%s': %s", listing.get("title", "")[:50], e)
                # Still create announcement from listing info alone
                ann = self._create_from_listing_only(listing, platform_name)
                announcements.append(ann)

        return announcements

    async def _fetch_and_parse_detail(
        self, listing: dict, parser, platform_name: str, timeout: int, wait_ms: int
    ) -> BidAnnouncement:
        """抓取并解析单条公告详情"""
        from scrapling import StealthyFetcher

        detail_url = listing["url"]
        logger.debug("Fetching detail: %s", detail_url)

        response = await StealthyFetcher.async_fetch(
            detail_url,
            headless=True,
            solve_cloudflare=True,
            network_idle=True,
            timeout=timeout,
            wait=wait_ms,
        )

        if response.status != 200:
            raise Exception(f"Detail page returned status {response.status}")

        raw_data = parser.parse_detail(response)
        # Ensure title from listing if parser didn't get it
        if not raw_data.get("title"):
            raw_data["title"] = listing.get("title", "")

        return self._validate_and_create_announcement(raw_data, platform_name)

    def _create_from_listing_only(self, listing: dict, platform_name: str) -> BidAnnouncement:
        """从列表信息创建不完整公告"""
        raw = {
            "title": listing.get("title", ""),
            "publish_date": "",
            "deadline": None,
            "project_category": "",
            "budget_amount": None,
            "attachment_links": [],
            "announcement_id": "",
        }
        return self._validate_and_create_announcement(raw, platform_name)

    def _get_parser(self, parser_name: str):
        """获取平台解析器实例"""
        from src.crawler.platform_parsers.ccgp_parser import CCGPParser
        from src.crawler.platform_parsers.zbytb_parser import ZBYTBParser

        parsers = {
            "CCGPParser": CCGPParser(),
            "ccgp": CCGPParser(),
            "ZBYTBParser": ZBYTBParser(),
            "zbytb": ZBYTBParser(),
        }
        parser = parsers.get(parser_name)
        if parser is None:
            # Default to CCGP parser
            logger.warning("Unknown parser '%s', falling back to CCGPParser", parser_name)
            return CCGPParser()
        return parser

    def _validate_and_create_announcement(
        self, raw_data: dict, platform_name: str
    ) -> BidAnnouncement:
        """验证原始数据并创建公告对象，标记不完整记录"""
        missing_fields = []

        for field_name in REQUIRED_FIELDS:
            value = raw_data.get(field_name)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing_fields.append(field_name)

        title = raw_data.get("title", "") or ""
        if len(title) > 200:
            title = title[:200]

        is_complete = len(missing_fields) == 0

        if not is_complete:
            logger.warning(
                "Incomplete announcement from '%s' (id=%s): missing: %s",
                platform_name,
                raw_data.get("announcement_id", "unknown"),
                ", ".join(missing_fields),
            )

        return BidAnnouncement(
            title=title,
            publish_date=raw_data.get("publish_date", ""),
            deadline=raw_data.get("deadline"),
            project_category=raw_data.get("project_category", ""),
            budget_amount=raw_data.get("budget_amount"),
            attachment_links=raw_data.get("attachment_links", []),
            source_platform=platform_name,
            announcement_id=raw_data.get("announcement_id", ""),
            is_complete=is_complete,
            missing_fields=missing_fields,
        )

    def _serialize_result(self, result: CrawlResult) -> dict:
        """将 CrawlResult 序列化为可JSON化的字典"""
        return {
            "announcements": [asdict(a) for a in result.announcements],
            "incomplete_count": result.incomplete_count,
            "skipped_platforms": result.skipped_platforms,
            "total_elapsed": result.total_elapsed,
        }
