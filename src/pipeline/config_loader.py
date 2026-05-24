"""配置加载与验证模块

负责从 config.yaml 加载配置，验证必需键（llm_api_key, target_platforms），
合并默认值，并在缺失可选键时记录 warning。
"""

import logging
from pathlib import Path

import yaml

from src.exceptions import ConfigFileNotFoundError, ConfigValidationError

logger = logging.getLogger(__name__)


class ConfigLoader:
    """加载、验证并合并默认值的配置加载器"""

    REQUIRED_KEYS = ["llm_api_key", "target_platforms"]
    DEFAULT_CONFIG_PATH = "D:/CADAI/config.yaml"

    DEFAULTS = {
        "crawler": {
            "proxies": [],
            "user_agents": ["Mozilla/5.0"],
            "crawl_delay": [1, 3],
            "retry_limit": 3,
            "connection_timeout": 120,
            "request_timeout": 30,
        },
        "dxf_parser": {
            "unit_scale": 1.0,
            "quota_db_path": "data/quota_db.json",
        },
        "rag": {
            "llm_api_url": "https://api.openai.com/v1",
            "llm_model": "gpt-4",
            "embedding_model": "text-embedding-ada-002",
            "chunk_size": 800,
            "chunk_overlap": 50,
            "similarity_threshold": 0.6,
            "max_retries": 3,
            "request_timeout": 60,
        },
        "monte_carlo": {
            "iterations": 10000,
            "win_probability_threshold": 0.6,
            "execution_timeout": 120,
        },
        "pipeline": {
            "output_base": "D:/CADAI/output",
            "module_timeout": 300,
        },
    }

    def __init__(self, config_path: str | None = None):
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)

    def load(self) -> dict:
        """读取YAML配置文件，验证必需键，合并默认值。

        Raises:
            ConfigFileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML格式错误（直接传播）
            ConfigValidationError: 必需键缺失或为空
        """
        if not self.config_path.exists():
            raise ConfigFileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            config = {}

        self._validate_required_keys(config)
        config = self._merge_defaults(config)
        return config

    def _validate_required_keys(self, config: dict) -> None:
        """检查 llm_api_key 和 target_platforms 是否存在且非空。

        Raises:
            ConfigValidationError: 必需键缺失或为空
        """
        missing = []

        # Check llm_api_key in rag section
        rag_section = config.get("rag", {})
        if not rag_section or not rag_section.get("llm_api_key"):
            missing.append("llm_api_key")

        # Check target_platforms in crawler section
        crawler_section = config.get("crawler", {})
        if not crawler_section or not crawler_section.get("target_platforms"):
            missing.append("target_platforms")

        if missing:
            raise ConfigValidationError(missing)

    def _merge_defaults(self, config: dict) -> dict:
        """对未提供的可选键合并默认值，并记录 warning。"""
        for section_key, section_defaults in self.DEFAULTS.items():
            if section_key not in config:
                config[section_key] = {}

            for key, default_value in section_defaults.items():
                if key not in config[section_key]:
                    config[section_key][key] = default_value
                    logger.warning(
                        "Config key '%s.%s' not set, applying default: %s",
                        section_key,
                        key,
                        default_value,
                    )

        return config
