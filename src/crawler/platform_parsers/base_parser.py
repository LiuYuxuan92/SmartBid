"""平台解析器基类

定义各招标平台解析器的抽象接口，包括公告列表解析、
详情页解析和附件下载（50MB/20文件限制）。
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class BasePlatformParser(ABC):
    """各平台解析器的抽象基类"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台标识名"""
        ...

    @abstractmethod
    def parse_listing(self, html: str) -> list[dict]:
        """解析列表页，返回公告摘要列表 [{title, url, publish_date, ...}]"""
        ...

    @abstractmethod
    def parse_detail(self, html: str) -> dict:
        """解析详情页，返回完整公告数据字典"""
        ...


@dataclass
class AttachmentMetadata:
    """附件元数据"""
    source_platform: str
    announcement_id: str
    original_filename: str
    file_size_bytes: int
    download_timestamp: str  # ISO 8601


class AttachmentDownloader:
    """附件下载器，强制执行50MB/20文件限制并存储元数据"""

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_ATTACHMENTS_PER_ANNOUNCEMENT = 20

    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout

    def download(
        self,
        urls: list[str],
        output_dir: str,
        platform: str,
        announcement_id: str,
    ) -> list[AttachmentMetadata]:
        """Download attachments with limits enforced.

        Args:
            urls: List of attachment URLs to download.
            output_dir: Directory to save downloaded files.
            platform: Source platform identifier.
            announcement_id: Associated announcement ID.

        Returns:
            List of AttachmentMetadata for successfully downloaded files.
        """
        # Enforce max attachments per announcement
        if len(urls) > self.MAX_ATTACHMENTS_PER_ANNOUNCEMENT:
            logger.warning(
                "Announcement '%s' has %d attachments, truncating to %d",
                announcement_id,
                len(urls),
                self.MAX_ATTACHMENTS_PER_ANNOUNCEMENT,
            )
            urls = urls[: self.MAX_ATTACHMENTS_PER_ANNOUNCEMENT]

        os.makedirs(output_dir, exist_ok=True)
        results: list[AttachmentMetadata] = []

        for url in urls:
            try:
                metadata = self._download_single(
                    url=url,
                    output_dir=output_dir,
                    platform=platform,
                    announcement_id=announcement_id,
                )
                if metadata is not None:
                    results.append(metadata)
            except Exception as e:
                logger.warning(
                    "Failed to download attachment '%s' for announcement '%s': %s",
                    url,
                    announcement_id,
                    str(e),
                )

        return results

    def _download_single(
        self,
        url: str,
        output_dir: str,
        platform: str,
        announcement_id: str,
    ) -> Optional[AttachmentMetadata]:
        """Download a single attachment, respecting size limit.

        Returns:
            AttachmentMetadata on success, None if file exceeds size limit.
        """
        filename = self._extract_filename(url)

        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            # Use streaming to check size before full download
            with client.stream("GET", url) as response:
                response.raise_for_status()

                # Check Content-Length header first
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self.MAX_FILE_SIZE:
                    logger.warning(
                        "Attachment '%s' exceeds 50MB limit (Content-Length: %s bytes), skipping",
                        url,
                        content_length,
                    )
                    return None

                # Stream download with size check
                file_path = os.path.join(output_dir, filename)
                downloaded_bytes = 0

                with open(file_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > self.MAX_FILE_SIZE:
                            logger.warning(
                                "Attachment '%s' exceeded 50MB during download, aborting",
                                url,
                            )
                            f.close()
                            os.remove(file_path)
                            return None
                        f.write(chunk)

        # Create metadata
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = AttachmentMetadata(
            source_platform=platform,
            announcement_id=announcement_id,
            original_filename=filename,
            file_size_bytes=downloaded_bytes,
            download_timestamp=timestamp,
        )

        # Store metadata JSON alongside the file
        metadata_path = file_path + ".meta.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(asdict(metadata), f, ensure_ascii=False, indent=2)

        return metadata

    def _extract_filename(self, url: str) -> str:
        """Extract filename from URL, falling back to a generated name."""
        from urllib.parse import urlparse, unquote

        path = urlparse(url).path
        filename = unquote(os.path.basename(path))
        if not filename:
            filename = f"attachment_{hash(url) & 0xFFFFFFFF:08x}"
        return filename
