"""招投标智能辅助系统 - 异常层次结构"""


class BiddingAssistantError(Exception):
    """基础异常类"""


class ConfigError(BiddingAssistantError):
    """配置相关错误"""


class ConfigFileNotFoundError(ConfigError):
    pass


class ConfigValidationError(ConfigError):
    def __init__(self, missing_keys: list[str]):
        self.missing_keys = missing_keys
        super().__init__(f"Missing required configuration keys: {', '.join(missing_keys)}")


class CrawlerError(BiddingAssistantError):
    """爬虫模块错误"""


class PlatformBlockedError(CrawlerError):
    def __init__(self, platform: str, reason: str):
        self.platform = platform
        self.reason = reason
        super().__init__(f"Platform '{platform}' blocked: {reason}")


class DXFError(BiddingAssistantError):
    """DXF解析错误"""


class DXFFormatError(DXFError):
    pass


class DXFEmptyError(DXFError):
    pass


class RAGError(BiddingAssistantError):
    """RAG生成错误"""


class LLMAPIError(RAGError):
    pass


class VectorStoreError(RAGError):
    pass


class UnsupportedFormatError(RAGError):
    pass


class SimulationError(BiddingAssistantError):
    """模拟错误"""


class InsufficientDataError(SimulationError):
    pass


class SimulationTimeoutError(SimulationError):
    def __init__(self, partial_result: dict):
        self.partial_result = partial_result
        super().__init__("Simulation timed out, partial results available")
