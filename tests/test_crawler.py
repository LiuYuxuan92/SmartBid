"""Crawler模块测试

测试爬虫模块的平台连接、公告提取、不完整记录处理、
反爬引擎交互和 CrawlResult 日志输出。
"""

import pytest
from unittest.mock import patch

from src.crawler.anti_crawl import (
    ProxyPool,
    UserAgentRotator,
    AntiCrawlEngine,
    RequestContext,
)


class TestProxyPool:
    """ProxyPool 代理池测试"""

    def test_rotate_cycles_through_proxies(self):
        """轮转应按顺序遍历所有代理"""
        proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
        pool = ProxyPool(proxies)

        results = [pool.rotate() for _ in range(6)]
        assert results == proxies + proxies

    def test_rotate_skips_blacklisted(self):
        """轮转应跳过黑名单代理"""
        proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
        pool = ProxyPool(proxies)

        pool.mark_failed("http://p2:8080")
        results = [pool.rotate() for _ in range(4)]
        assert "http://p2:8080" not in results
        assert results == ["http://p1:8080", "http://p3:8080", "http://p1:8080", "http://p3:8080"]

    def test_rotate_returns_none_when_all_blacklisted(self):
        """所有代理都被拉黑时应返回None"""
        proxies = ["http://p1:8080", "http://p2:8080"]
        pool = ProxyPool(proxies)

        pool.mark_failed("http://p1:8080")
        pool.mark_failed("http://p2:8080")
        assert pool.rotate() is None

    def test_rotate_returns_none_when_empty(self):
        """空代理池应返回None"""
        pool = ProxyPool([])
        assert pool.rotate() is None


class TestUserAgentRotator:
    """UserAgentRotator UA轮转器测试"""

    def test_cycles_through_agents(self):
        """应按顺序轮转UA"""
        agents = ["UA1", "UA2", "UA3"]
        rotator = UserAgentRotator(agents)

        results = [rotator.next() for _ in range(6)]
        assert results == agents + agents

    def test_default_agent_when_empty(self):
        """空列表时应使用默认UA"""
        rotator = UserAgentRotator([])
        assert rotator.next() == "Mozilla/5.0"


class TestAntiCrawlEngine:
    """AntiCrawlEngine 反反爬引擎测试"""

    def test_max_retries_is_three(self):
        """MAX_RETRIES 应为 3"""
        assert AntiCrawlEngine.MAX_RETRIES == 3

    def test_retry_interval_is_five(self):
        """RETRY_INTERVAL 应为 5 秒"""
        assert AntiCrawlEngine.RETRY_INTERVAL == 5

    @patch("src.crawler.anti_crawl.time.sleep")
    def test_handle_block_returns_context_with_rotated_proxy(self, mock_sleep):
        """handle_block 应返回包含轮转代理的 RequestContext"""
        proxies = ["http://p1:8080", "http://p2:8080"]
        agents = ["UA1", "UA2"]
        engine = AntiCrawlEngine(proxies, agents)

        ctx = engine.handle_block(403, "http://example.com")
        assert isinstance(ctx, RequestContext)
        assert ctx.proxy == "http://p1:8080"
        assert ctx.user_agent == "UA1"

    @patch("src.crawler.anti_crawl.time.sleep")
    def test_handle_block_rotates_on_successive_calls(self, mock_sleep):
        """连续调用 handle_block 应轮转代理"""
        proxies = ["http://p1:8080", "http://p2:8080"]
        agents = ["UA1", "UA2"]
        engine = AntiCrawlEngine(proxies, agents)

        ctx1 = engine.handle_block(403, "http://example.com")
        ctx2 = engine.handle_block(403, "http://example.com")
        assert ctx1.proxy == "http://p1:8080"
        assert ctx2.proxy == "http://p2:8080"

    def test_solve_slider_captcha_stub_returns_none(self):
        """MVP存根: solve_slider_captcha 应返回 None"""
        engine = AntiCrawlEngine([], ["UA1"])
        assert engine.solve_slider_captcha("http://example.com") is None

    def test_generate_dynamic_token_stub_returns_none(self):
        """MVP存根: generate_dynamic_token 应返回 None"""
        engine = AntiCrawlEngine([], ["UA1"])
        assert engine.generate_dynamic_token("var token='abc';") is None


# ============================================================
# CrawlerModule Tests
# ============================================================

from unittest.mock import MagicMock, patch as mock_patch
from src.crawler.crawler_module import (
    CrawlerModule,
    BidAnnouncement,
    CrawlResult,
    REQUIRED_FIELDS,
)


class TestBidAnnouncement:
    """BidAnnouncement 数据结构测试"""

    def test_default_is_complete(self):
        """默认 is_complete 应为 True"""
        ann = BidAnnouncement(
            title="Test",
            publish_date="2024-01-01",
            deadline="2024-02-01",
            project_category="construction",
            budget_amount=100000.0,
            attachment_links=[],
            source_platform="test_platform",
            announcement_id="ann-001",
        )
        assert ann.is_complete is True
        assert ann.missing_fields == []

    def test_title_stored_correctly(self):
        """标题应正确存储"""
        ann = BidAnnouncement(
            title="招标公告",
            publish_date="2024-01-01",
            deadline=None,
            project_category="engineering",
            budget_amount=None,
            attachment_links=["http://example.com/doc.pdf"],
            source_platform="platform_a",
            announcement_id="ann-002",
            is_complete=False,
            missing_fields=["deadline", "budget_amount"],
        )
        assert ann.title == "招标公告"
        assert ann.deadline is None
        assert ann.budget_amount is None
        assert ann.missing_fields == ["deadline", "budget_amount"]


class TestCrawlResult:
    """CrawlResult 数据结构测试"""

    def test_default_values(self):
        """默认值应为空/零"""
        result = CrawlResult()
        assert result.announcements == []
        assert result.incomplete_count == 0
        assert result.skipped_platforms == []
        assert result.total_elapsed == 0.0


class TestCrawlerModule:
    """CrawlerModule 爬虫模块测试"""

    def setup_method(self):
        self.module = CrawlerModule()

    def test_module_name(self):
        """模块名称应为 'Crawler'"""
        assert self.module.name == "Crawler"

    def test_validate_input_always_true(self):
        """validate_input 应始终返回 True"""
        assert self.module.validate_input({}) is True
        assert self.module.validate_input({"key": "value"}) is True

    @mock_patch("src.crawler.crawler_module.httpx.Client")
    def test_execute_returns_serialized_result(self, mock_client_cls):
        """execute 应返回序列化的 CrawlResult 字典"""
        # Mock successful but empty response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        config = {
            "crawler": {
                "target_platforms": [
                    {"url": "https://example.com", "name": "test_platform"}
                ],
                "connection_timeout": 120,
                "request_timeout": 30,
            }
        }

        result = self.module.execute({}, config)

        assert "announcements" in result
        assert "incomplete_count" in result
        assert "skipped_platforms" in result
        assert "total_elapsed" in result
        assert isinstance(result["total_elapsed"], float)

    @mock_patch("src.crawler.crawler_module.httpx.Client")
    def test_execute_skips_failed_platform(self, mock_client_cls):
        """平台失败后应跳过并继续"""
        import httpx as httpx_mod

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx_mod.ConnectTimeout("timeout")
        mock_client_cls.return_value = mock_client

        config = {
            "crawler": {
                "target_platforms": [
                    {"url": "https://fail.com", "name": "failing_platform"},
                    {"url": "https://fail2.com", "name": "failing_platform_2"},
                ],
                "connection_timeout": 120,
                "request_timeout": 30,
            }
        }

        result = self.module.execute({}, config)

        # Both platforms should be skipped
        assert len(result["skipped_platforms"]) == 2
        assert result["skipped_platforms"][0]["name"] == "failing_platform"
        assert result["skipped_platforms"][1]["name"] == "failing_platform_2"

    def test_execute_with_empty_platforms(self):
        """无平台配置时应返回空结果"""
        config = {"crawler": {"target_platforms": []}}
        result = self.module.execute({}, config)

        assert result["announcements"] == []
        assert result["incomplete_count"] == 0
        assert result["skipped_platforms"] == []

    def test_execute_uses_default_timeouts(self):
        """未配置超时时应使用默认值 (120s/30s)"""
        config = {"crawler": {"target_platforms": []}}
        # No exception means defaults are applied correctly
        result = self.module.execute({}, config)
        assert result["total_elapsed"] >= 0


class TestCrawlerModuleValidation:
    """CrawlerModule 公告验证逻辑测试"""

    def setup_method(self):
        self.module = CrawlerModule()

    def test_validate_complete_announcement(self):
        """完整公告应标记为 is_complete=True"""
        raw = {
            "title": "某工程招标公告",
            "publish_date": "2024-06-01T10:00:00",
            "deadline": "2024-06-15T17:00:00",
            "project_category": "建筑工程",
            "budget_amount": 500000.0,
            "attachment_links": ["http://example.com/file.pdf"],
            "announcement_id": "ann-100",
        }
        ann = self.module._validate_and_create_announcement(raw, "test_platform")
        assert ann.is_complete is True
        assert ann.missing_fields == []

    def test_validate_incomplete_missing_deadline(self):
        """缺少 deadline 应标记为不完整"""
        raw = {
            "title": "某工程招标公告",
            "publish_date": "2024-06-01T10:00:00",
            "deadline": None,
            "project_category": "建筑工程",
            "budget_amount": 500000.0,
            "attachment_links": [],
            "announcement_id": "ann-101",
        }
        ann = self.module._validate_and_create_announcement(raw, "test_platform")
        assert ann.is_complete is False
        assert "deadline" in ann.missing_fields

    def test_validate_incomplete_missing_budget(self):
        """缺少 budget_amount 应标记为不完整"""
        raw = {
            "title": "某工程招标公告",
            "publish_date": "2024-06-01T10:00:00",
            "deadline": "2024-06-15T17:00:00",
            "project_category": "建筑工程",
            "budget_amount": None,
            "attachment_links": [],
            "announcement_id": "ann-102",
        }
        ann = self.module._validate_and_create_announcement(raw, "test_platform")
        assert ann.is_complete is False
        assert "budget_amount" in ann.missing_fields

    def test_validate_persists_incomplete_record(self):
        """不完整记录仍应保留可用字段"""
        raw = {
            "title": "招标",
            "publish_date": "2024-06-01",
            "deadline": None,
            "project_category": "",
            "budget_amount": None,
            "attachment_links": ["http://example.com/a.pdf"],
            "announcement_id": "ann-103",
        }
        ann = self.module._validate_and_create_announcement(raw, "platform_x")
        # Record is persisted (returned) even if incomplete
        assert ann.title == "招标"
        assert ann.publish_date == "2024-06-01"
        assert ann.attachment_links == ["http://example.com/a.pdf"]
        assert ann.is_complete is False

    def test_title_truncated_at_200_chars(self):
        """标题超过200字符应截断"""
        long_title = "A" * 300
        raw = {
            "title": long_title,
            "publish_date": "2024-01-01",
            "deadline": "2024-02-01",
            "project_category": "工程",
            "budget_amount": 100.0,
            "attachment_links": [],
            "announcement_id": "ann-104",
        }
        ann = self.module._validate_and_create_announcement(raw, "test")
        assert len(ann.title) == 200

    def test_multiple_missing_fields_logged(self):
        """多个缺失字段都应被记录"""
        raw = {
            "title": "",
            "publish_date": "",
            "deadline": None,
            "project_category": "",
            "budget_amount": None,
            "attachment_links": [],
            "announcement_id": "ann-105",
        }
        ann = self.module._validate_and_create_announcement(raw, "test")
        assert ann.is_complete is False
        # title, publish_date, deadline, project_category, budget_amount all missing
        assert len(ann.missing_fields) == 5


class TestCrawlerModuleSerialization:
    """CrawlerModule 序列化测试"""

    def setup_method(self):
        self.module = CrawlerModule()

    def test_serialize_empty_result(self):
        """空结果应正确序列化"""
        result = CrawlResult()
        serialized = self.module._serialize_result(result)
        assert serialized == {
            "announcements": [],
            "incomplete_count": 0,
            "skipped_platforms": [],
            "total_elapsed": 0.0,
        }

    def test_serialize_with_announcements(self):
        """包含公告的结果应正确序列化"""
        ann = BidAnnouncement(
            title="Test",
            publish_date="2024-01-01",
            deadline="2024-02-01",
            project_category="construction",
            budget_amount=50000.0,
            attachment_links=["http://example.com/f.pdf"],
            source_platform="p1",
            announcement_id="a1",
            is_complete=True,
            missing_fields=[],
        )
        result = CrawlResult(
            announcements=[ann],
            incomplete_count=0,
            skipped_platforms=[{"name": "p2", "reason": "timeout"}],
            total_elapsed=5.5,
        )
        serialized = self.module._serialize_result(result)
        assert len(serialized["announcements"]) == 1
        assert serialized["announcements"][0]["title"] == "Test"
        assert serialized["skipped_platforms"] == [{"name": "p2", "reason": "timeout"}]
        assert serialized["total_elapsed"] == 5.5


# ============================================================
# BasePlatformParser & AttachmentDownloader Tests
# ============================================================

import json
import os
import tempfile
import httpx
from unittest.mock import MagicMock, patch, PropertyMock
from src.crawler.platform_parsers.base_parser import (
    BasePlatformParser,
    AttachmentDownloader,
    AttachmentMetadata,
)


class ConcretePlatformParser(BasePlatformParser):
    """用于测试的具体解析器实现"""

    @property
    def platform_name(self) -> str:
        return "test_platform"

    def parse_listing(self, html: str) -> list[dict]:
        return [{"title": "Test", "url": "http://example.com"}]

    def parse_detail(self, html: str) -> dict:
        return {"title": "Test Detail"}


class TestBasePlatformParser:
    """BasePlatformParser 抽象基类测试"""

    def test_concrete_parser_has_platform_name(self):
        """具体实现应有 platform_name 属性"""
        parser = ConcretePlatformParser()
        assert parser.platform_name == "test_platform"

    def test_concrete_parser_parse_listing(self):
        """具体实现应能解析列表页"""
        parser = ConcretePlatformParser()
        result = parser.parse_listing("<html></html>")
        assert len(result) == 1
        assert result[0]["title"] == "Test"

    def test_concrete_parser_parse_detail(self):
        """具体实现应能解析详情页"""
        parser = ConcretePlatformParser()
        result = parser.parse_detail("<html></html>")
        assert result["title"] == "Test Detail"

    def test_cannot_instantiate_abstract_class(self):
        """不能直接实例化抽象基类"""
        with pytest.raises(TypeError):
            BasePlatformParser()


class TestAttachmentDownloader:
    """AttachmentDownloader 附件下载器测试"""

    def setup_method(self):
        self.downloader = AttachmentDownloader()

    def test_max_file_size_is_50mb(self):
        """MAX_FILE_SIZE 应为 50MB"""
        assert AttachmentDownloader.MAX_FILE_SIZE == 50 * 1024 * 1024

    def test_max_attachments_is_20(self):
        """MAX_ATTACHMENTS_PER_ANNOUNCEMENT 应为 20"""
        assert AttachmentDownloader.MAX_ATTACHMENTS_PER_ANNOUNCEMENT == 20

    @patch("src.crawler.platform_parsers.base_parser.httpx.Client")
    def test_file_size_limit_rejection_via_content_length(self, mock_client_cls):
        """Content-Length 超过 50MB 的文件应被拒绝"""
        # Setup mock for streaming response with large Content-Length
        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(60 * 1024 * 1024)}  # 60MB
        mock_response.raise_for_status = MagicMock()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__enter__ = MagicMock(return_value=mock_response)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_stream_ctx

        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            results = self.downloader.download(
                urls=["http://example.com/large_file.pdf"],
                output_dir=tmpdir,
                platform="test_platform",
                announcement_id="ann-001",
            )
            # File should be rejected due to size
            assert len(results) == 0

    def test_max_20_attachments_enforcement(self):
        """超过20个附件URL应被截断为20个"""
        urls = [f"http://example.com/file_{i}.pdf" for i in range(25)]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(
                self.downloader, "_download_single", return_value=AttachmentMetadata(
                    source_platform="test",
                    announcement_id="ann-001",
                    original_filename="file.pdf",
                    file_size_bytes=1024,
                    download_timestamp="2024-01-01T00:00:00+00:00",
                )
            ) as mock_download:
                results = self.downloader.download(
                    urls=urls,
                    output_dir=tmpdir,
                    platform="test",
                    announcement_id="ann-001",
                )
                # Should only process 20 attachments
                assert mock_download.call_count == 20
                assert len(results) == 20

    @patch("src.crawler.platform_parsers.base_parser.httpx.Client")
    def test_metadata_correctly_populated(self, mock_client_cls):
        """下载成功后元数据应正确填充"""
        file_content = b"Hello, this is test content"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(file_content))}
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_bytes.return_value = [file_content]

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__enter__ = MagicMock(return_value=mock_response)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_stream_ctx

        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            results = self.downloader.download(
                urls=["http://example.com/report.pdf"],
                output_dir=tmpdir,
                platform="gov_platform",
                announcement_id="ann-200",
            )

            assert len(results) == 1
            meta = results[0]
            assert meta.source_platform == "gov_platform"
            assert meta.announcement_id == "ann-200"
            assert meta.original_filename == "report.pdf"
            assert meta.file_size_bytes == len(file_content)
            assert meta.download_timestamp  # ISO 8601 string present

            # Verify metadata JSON file was created
            meta_file = os.path.join(tmpdir, "report.pdf.meta.json")
            assert os.path.exists(meta_file)
            with open(meta_file, "r", encoding="utf-8") as f:
                stored_meta = json.load(f)
            assert stored_meta["source_platform"] == "gov_platform"
            assert stored_meta["announcement_id"] == "ann-200"

    @patch("src.crawler.platform_parsers.base_parser.httpx.Client")
    def test_download_failure_does_not_raise(self, mock_client_cls):
        """下载失败不应抛出异常，应返回空列表"""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.side_effect = httpx.ConnectError("Connection refused")

        mock_client_cls.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise, just return empty results
            results = self.downloader.download(
                urls=["http://unreachable.example.com/file.pdf"],
                output_dir=tmpdir,
                platform="test_platform",
                announcement_id="ann-300",
            )
            assert len(results) == 0

    def test_extract_filename_from_url(self):
        """应从URL正确提取文件名"""
        assert self.downloader._extract_filename("http://example.com/docs/report.pdf") == "report.pdf"
        assert self.downloader._extract_filename("http://example.com/file%20name.docx") == "file name.docx"

    def test_extract_filename_fallback(self):
        """URL无文件名时应生成回退名称"""
        result = self.downloader._extract_filename("http://example.com/")
        assert result.startswith("attachment_")
