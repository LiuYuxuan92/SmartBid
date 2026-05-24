"""Tests for exception hierarchy."""
import pytest
from src.exceptions import (
    BiddingAssistantError,
    ConfigError,
    ConfigFileNotFoundError,
    ConfigValidationError,
    CrawlerError,
    PlatformBlockedError,
    DXFError,
    DXFFormatError,
    DXFEmptyError,
    RAGError,
    LLMAPIError,
    VectorStoreError,
    UnsupportedFormatError,
    SimulationError,
    InsufficientDataError,
    SimulationTimeoutError,
)


class TestExceptionHierarchy:
    """Verify all exceptions inherit from BiddingAssistantError."""

    def test_config_errors_inherit_from_base(self):
        assert issubclass(ConfigError, BiddingAssistantError)
        assert issubclass(ConfigFileNotFoundError, ConfigError)
        assert issubclass(ConfigValidationError, ConfigError)

    def test_crawler_errors_inherit_from_base(self):
        assert issubclass(CrawlerError, BiddingAssistantError)
        assert issubclass(PlatformBlockedError, CrawlerError)

    def test_dxf_errors_inherit_from_base(self):
        assert issubclass(DXFError, BiddingAssistantError)
        assert issubclass(DXFFormatError, DXFError)
        assert issubclass(DXFEmptyError, DXFError)

    def test_rag_errors_inherit_from_base(self):
        assert issubclass(RAGError, BiddingAssistantError)
        assert issubclass(LLMAPIError, RAGError)
        assert issubclass(VectorStoreError, RAGError)
        assert issubclass(UnsupportedFormatError, RAGError)

    def test_simulation_errors_inherit_from_base(self):
        assert issubclass(SimulationError, BiddingAssistantError)
        assert issubclass(InsufficientDataError, SimulationError)
        assert issubclass(SimulationTimeoutError, SimulationError)


class TestConfigValidationError:
    def test_stores_missing_keys(self):
        err = ConfigValidationError(["llm_api_key", "target_platforms"])
        assert err.missing_keys == ["llm_api_key", "target_platforms"]
        assert "llm_api_key" in str(err)
        assert "target_platforms" in str(err)


class TestPlatformBlockedError:
    def test_stores_platform_and_reason(self):
        err = PlatformBlockedError("beijing-exchange", "IP banned")
        assert err.platform == "beijing-exchange"
        assert err.reason == "IP banned"
        assert "beijing-exchange" in str(err)
        assert "IP banned" in str(err)


class TestSimulationTimeoutError:
    def test_stores_partial_result(self):
        partial = {"iterations_completed": 5000, "is_partial": True}
        err = SimulationTimeoutError(partial)
        assert err.partial_result == partial
        assert "timed out" in str(err)
