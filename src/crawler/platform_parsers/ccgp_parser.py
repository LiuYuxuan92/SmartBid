"""中国政府采购网 (ccgp.gov.cn) 平台解析器"""

import re
import logging
from typing import Optional

from src.crawler.platform_parsers.base_parser import BasePlatformParser

logger = logging.getLogger(__name__)


class CCGPParser(BasePlatformParser):
    """中国政府采购网解析器"""

    BASE_URL = "http://www.ccgp.gov.cn/cggg/zygg/gkzb/"

    @property
    def platform_name(self) -> str:
        return "ccgp.gov.cn"

    def parse_listing(self, response) -> list[dict]:
        """解析列表页，提取公告链接和标题。

        Args:
            response: Scrapling response object

        Returns:
            [{title, url}, ...]
        """
        links = response.css("a")
        announcements = []

        # Determine base URL from the actual response URL
        resp_url = str(getattr(response, "url", self.BASE_URL))
        # Strip trailing filename if any, keep directory
        if resp_url.endswith("/"):
            base = resp_url
        else:
            base = resp_url.rsplit("/", 1)[0] + "/"

        for link in links:
            href = link.attrib.get("href", "")
            text = (link.text or "").strip()

            # Match announcement links like ./202605/t20260524_26620359.htm
            if href.startswith("./20") and text and len(text) > 10:
                full_url = base + href[2:]
                announcements.append({"title": text, "url": full_url})

        logger.info("CCGP listing parsed: %d announcements found", len(announcements))
        return announcements

    def parse_detail(self, response) -> dict:
        """解析详情页，提取结构化公告数据。

        Args:
            response: Scrapling response object

        Returns:
            {title, publish_date, deadline, project_category, budget_amount,
             announcement_id, attachment_links, ...}
        """
        result = {}

        # Extract table data — CCGP uses label:value pairs in consecutive td cells
        # The pattern is: [label_td] [value_td] [label_td] [value_td] ...
        # But sometimes the first td IS the value of a previous row's last label
        tds = response.css("td")
        table_data = {}
        all_td_texts = [(td.text or "").strip() for td in tds]

        # Build key-value mapping from all td text
        # Strategy: look for known label patterns
        known_labels = [
            "采购项目名称", "品目", "采购单位", "行政区域", "公告时间",
            "获取招标文件时间", "招标文件售价", "获取招标文件的地点",
            "开标时间", "开标地点", "预算金额", "项目联系人", "项目联系电话",
            "采购单位地址", "采购单位联系方式", "代理机构名称",
            "代理机构地址", "代理机构联系方式",
        ]
        for i, text in enumerate(all_td_texts):
            if text in known_labels and i + 1 < len(all_td_texts):
                table_data[text] = all_td_texts[i + 1]

        # Extract paragraph content for additional info
        ps = response.css("p")
        content_parts = []
        for p in ps:
            t = (p.text or "").strip()
            if t and len(t) > 5:
                content_parts.append(t)
        full_content = "\n".join(content_parts)

        # Map to standard fields
        result["title"] = self._extract_title(table_data, response)
        result["publish_date"] = self._extract_publish_date(table_data)
        result["deadline"] = self._extract_deadline(table_data, full_content)
        result["project_category"] = self._extract_category(table_data, full_content)
        result["budget_amount"] = self._extract_budget(table_data, full_content)
        result["announcement_id"] = self._extract_project_id(full_content)
        result["attachment_links"] = self._extract_attachments(response)
        result["raw_table"] = table_data
        result["content_text"] = full_content[:5000]

        return result

    def _extract_title(self, table_data: dict, response) -> str:
        """提取项目名称"""
        # Try from <h2> or table
        h2_els = response.css("h2")
        for h2 in h2_els:
            text = (h2.text or "").strip()
            if text and "公告" in text:
                return text

        # Try from paragraph content
        for key, val in table_data.items():
            if "项目名称" in key or "采购项目名称" in key:
                return val
            # Sometimes the project name IS the key
            if "公告" in key:
                return key

        # First table key that looks like a project name
        for key in table_data:
            if len(key) > 10 and ("项目" in key or "工程" in key or "采购" in key):
                return key

        return ""

    def _extract_publish_date(self, table_data: dict) -> str:
        """提取公告时间"""
        val = table_data.get("公告时间", "")
        if val:
            return val.strip()
        return ""

    def _extract_deadline(self, table_data: dict, content: str) -> Optional[str]:
        """提取投标截止时间"""
        # Look for 提交投标文件截止时间
        match = re.search(r"提交投标文件截止时间[：:]?\s*(\d{4}年\d{2}月\d{2}日\s*\d{2}[点时]\d{2}分)", content)
        if match:
            return match.group(1)

        # From table: 开标时间
        for key, val in table_data.items():
            if "开标时间" in val or "开标时间" in key:
                date_str = key if re.search(r"\d{4}年", key) else val
                if re.search(r"\d{4}年", date_str):
                    return date_str.strip()
        return None

    def _extract_category(self, table_data: dict, content: str) -> str:
        """提取项目品目/类别"""
        for key, val in table_data.items():
            if val == "品目":
                return key
        # Try from content
        match = re.search(r"品目[：:]\s*(.+?)[\n]", content)
        if match:
            return match.group(1).strip()
        # Look for category keywords in content
        categories = ["工程", "货物", "服务"]
        for cat in categories:
            if cat in content[:500]:
                return cat
        return ""

    def _extract_budget(self, table_data: dict, content: str) -> Optional[float]:
        """提取预算金额（万元转元）"""
        budget_str = table_data.get("预算金额", "")

        # From content as fallback
        if not budget_str:
            match = re.search(r"预算金额[：:]?\s*[￥]?([\d,.]+)\s*万元", content)
            if match:
                budget_str = match.group(0)

        if not budget_str:
            return None

        # Parse amount — handle ￥412.000000万元（人民币）
        match = re.search(r"[￥]?([\d,.]+)\s*万元", budget_str)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                return float(amount_str) * 10000  # 万元 -> 元
            except ValueError:
                return None

        return None

    def _extract_project_id(self, content: str) -> str:
        """提取项目编号"""
        match = re.search(r"项目编号[：:]\s*([A-Za-z0-9\-_]+)", content)
        if match:
            return match.group(1)
        return ""

    def _extract_attachments(self, response) -> list[str]:
        """提取附件下载链接"""
        attachments = []
        links = response.css("a")
        for link in links:
            href = link.attrib.get("href", "")
            text = (link.text or "").strip()
            # Look for file download links
            if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".dxf"]):
                if href.startswith("//"):
                    href = "http:" + href
                elif href.startswith("/"):
                    href = "http://www.ccgp.gov.cn" + href
                attachments.append(href)
        return attachments
