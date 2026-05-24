"""中国采招网 (zbytb.com) 平台解析器"""

import re
import logging
from typing import Optional

from src.crawler.platform_parsers.base_parser import BasePlatformParser

logger = logging.getLogger(__name__)


class ZBYTBParser(BasePlatformParser):
    """中国采招网解析器
    
    采招网是商业招标信息聚合平台，列表页有丰富的公告链接，
    但详情页需要登录才能看全文。所以主要从列表页提取信息。
    """

    BASE_URL = "https://www.zbytb.com"

    @property
    def platform_name(self) -> str:
        return "zbytb.com"

    def parse_listing(self, response) -> list[dict]:
        """解析列表页，提取公告链接。

        采招网的公告链接格式: /s-zb-{id}.html
        """
        links = response.css("a")
        announcements = []

        for link in links:
            href = link.attrib.get("href", "")
            text = (link.text or "").strip()

            # Match bid announcement links
            if "/s-zb-" in href and text and len(text) > 10:
                if not href.startswith("http"):
                    full_url = self.BASE_URL + href
                else:
                    full_url = href
                announcements.append({"title": text, "url": full_url})

        logger.info("ZBYTB listing parsed: %d announcements found", len(announcements))
        return announcements

    def parse_detail(self, response) -> dict:
        """解析详情页。
        
        采招网详情页内容有限（需要登录看全文），
        主要从标题和可用元素中提取信息。
        """
        result = {}

        # Title from h1
        h1_els = response.css("h1")
        result["title"] = (h1_els[0].text or "").strip() if h1_els else ""

        # Try to extract info from spans and metadata
        spans = response.css("span")
        for span in spans:
            text = (span.text or "").strip()
            if "地区" in text:
                result["region"] = text.replace("地区：", "").replace("地区:", "").strip()
            elif "发布时间" in text or "发布日期" in text:
                date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", text)
                if date_match:
                    result["publish_date"] = date_match.group(1)

        # Extract from paragraphs
        ps = response.css("p")
        content_parts = []
        for p in ps:
            t = (p.text or "").strip()
            if t and len(t) > 5:
                content_parts.append(t)
        full_content = "\n".join(content_parts)

        # Try extracting budget from content
        budget_match = re.search(r"预算[金额]*[：:]\s*[￥]?([\d,.]+)\s*[万]?元", full_content)
        if budget_match:
            try:
                amount = float(budget_match.group(1).replace(",", ""))
                if "万" in budget_match.group(0):
                    amount *= 10000
                result["budget_amount"] = amount
            except ValueError:
                pass

        # Deadline
        deadline_match = re.search(r"截止[时间日期]*[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})", full_content)
        if deadline_match:
            result["deadline"] = deadline_match.group(1)

        # Category from title
        result["project_category"] = self._infer_category(result.get("title", ""))
        result["announcement_id"] = self._extract_id_from_url(response)
        result["attachment_links"] = []

        return result

    def _infer_category(self, title: str) -> str:
        """从标题推断项目类别"""
        if any(k in title for k in ["工程", "施工", "建设", "修缮", "改造"]):
            return "工程"
        elif any(k in title for k in ["采购", "购置", "设备", "货物"]):
            return "货物"
        elif any(k in title for k in ["服务", "咨询", "设计", "监理"]):
            return "服务"
        return "其他"

    def _extract_id_from_url(self, response) -> str:
        """从URL提取公告ID"""
        url = str(getattr(response, "url", ""))
        match = re.search(r"s-zb-(\d+)", url)
        return match.group(1) if match else ""
