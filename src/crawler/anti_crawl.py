"""反反爬引擎 - 代理轮转、CAPTCHA处理、动态Token生成"""

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """请求上下文，包含代理和UA信息"""
    proxy: Optional[str] = None
    user_agent: str = ""
    cookies: Optional[dict] = None
    token: Optional[str] = None


class ProxyPool:
    """代理IP池，支持轮转和黑名单"""

    def __init__(self, proxies: list[str]):
        self.proxies = list(proxies)
        self.current_index = 0
        self.blacklist: set[str] = set()

    def rotate(self) -> Optional[str]:
        """轮转到下一个可用代理（跳过黑名单）"""
        if not self.proxies:
            return None
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_index % len(self.proxies)]
            self.current_index += 1
            if proxy not in self.blacklist:
                return proxy
            attempts += 1
        return None  # All proxies blacklisted

    def mark_failed(self, proxy: str) -> None:
        """将代理加入黑名单"""
        self.blacklist.add(proxy)


class UserAgentRotator:
    """UA轮转器"""

    def __init__(self, user_agents: list[str]):
        self.user_agents = user_agents or ["Mozilla/5.0"]
        self.current_index = 0

    def next(self) -> str:
        """获取下一个UA"""
        ua = self.user_agents[self.current_index % len(self.user_agents)]
        self.current_index += 1
        return ua


class AntiCrawlEngine:
    """反反爬引擎，处理IP封锁、验证码和动态Token"""

    MAX_RETRIES = 3
    RETRY_INTERVAL = 5  # seconds

    def __init__(self, proxies: list[str], user_agents: list[str]):
        self.proxy_pool = ProxyPool(proxies)
        self.ua_rotator = UserAgentRotator(user_agents)

    def handle_block(self, response_code: int, url: str) -> Optional[RequestContext]:
        """处理反爬阻断，返回新的RequestContext或None（所有重试用尽）

        策略: IP轮转 → 重试，最多3次，间隔5秒
        对于403或超时，轮转代理重试
        """
        for attempt in range(self.MAX_RETRIES):
            logger.warning(
                "Anti-crawl block detected (code=%s, url=%s), retry %d/%d",
                response_code, url, attempt + 1, self.MAX_RETRIES
            )

            proxy = self.proxy_pool.rotate()
            ua = self.ua_rotator.next()

            if proxy is None and not self.proxy_pool.proxies:
                # No proxies configured, just rotate UA
                pass

            context = RequestContext(proxy=proxy, user_agent=ua)

            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self.RETRY_INTERVAL)

            return context  # Return new context for caller to retry

        return None  # All retries exhausted

    def solve_slider_captcha(self, page_url: str) -> Optional[str]:
        """使用Playwright解决滑块验证码（MVP存根）

        Returns:
            session cookie string if solved, None if failed
        """
        logger.info("Attempting slider CAPTCHA resolution for: %s", page_url)
        # MVP stub - actual Playwright implementation deferred
        # In production: launch headless browser, detect slider, simulate drag
        return None

    def generate_dynamic_token(self, js_source: str) -> Optional[str]:
        """分析JS逆向生成动态Token（MVP存根）

        Args:
            js_source: JavaScript source code containing token generation logic

        Returns:
            Generated token string if successful, None if failed
        """
        logger.info("Attempting dynamic token generation from JS source (%d bytes)", len(js_source))
        # MVP stub - actual JS reverse engineering deferred
        # In production: parse JS AST, identify token algo, replicate in Python
        return None
