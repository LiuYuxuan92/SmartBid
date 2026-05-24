"""ConfigLoader 单元测试"""

import logging
import tempfile
from pathlib import Path

import pytest
import yaml

from src.exceptions import ConfigFileNotFoundError, ConfigValidationError
from src.pipeline.config_loader import ConfigLoader


@pytest.fixture
def valid_config_content():
    return {
        "crawler": {
            "target_platforms": [
                {"url": "https://example.com", "name": "test", "parser": "BaseParser"}
            ]
        },
        "rag": {"llm_api_key": "test-key-123"},
    }


@pytest.fixture
def config_file(tmp_path, valid_config_content):
    """Create a temporary valid config file."""
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(valid_config_content), encoding="utf-8")
    return path


class TestConfigLoaderLoad:
    def test_load_valid_config(self, config_file):
        loader = ConfigLoader(str(config_file))
        config = loader.load()
        assert config["rag"]["llm_api_key"] == "test-key-123"
        assert len(config["crawler"]["target_platforms"]) == 1

    def test_raises_config_file_not_found(self, tmp_path):
        loader = ConfigLoader(str(tmp_path / "nonexistent.yaml"))
        with pytest.raises(ConfigFileNotFoundError):
            loader.load()

    def test_raises_yaml_error_on_malformed(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("key: [invalid yaml\n  broken:", encoding="utf-8")
        loader = ConfigLoader(str(bad_file))
        with pytest.raises(yaml.YAMLError):
            loader.load()

    def test_raises_validation_error_missing_api_key(self, tmp_path):
        content = {
            "crawler": {
                "target_platforms": [{"url": "https://x.com", "name": "x", "parser": "B"}]
            },
            "rag": {},
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(content), encoding="utf-8")
        loader = ConfigLoader(str(path))
        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load()
        assert "llm_api_key" in exc_info.value.missing_keys

    def test_raises_validation_error_missing_target_platforms(self, tmp_path):
        content = {"rag": {"llm_api_key": "key"}, "crawler": {}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(content), encoding="utf-8")
        loader = ConfigLoader(str(path))
        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load()
        assert "target_platforms" in exc_info.value.missing_keys

    def test_raises_validation_error_empty_api_key(self, tmp_path):
        content = {
            "crawler": {
                "target_platforms": [{"url": "https://x.com", "name": "x", "parser": "B"}]
            },
            "rag": {"llm_api_key": ""},
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(content), encoding="utf-8")
        loader = ConfigLoader(str(path))
        with pytest.raises(ConfigValidationError):
            loader.load()


class TestMergeDefaults:
    def test_merges_missing_optional_keys(self, config_file):
        loader = ConfigLoader(str(config_file))
        config = loader.load()
        # Should have defaults merged in
        assert config["monte_carlo"]["iterations"] == 10000
        assert config["pipeline"]["output_base"] == "D:/CADAI/output"
        assert config["rag"]["llm_model"] == "gpt-4"
        assert config["crawler"]["retry_limit"] == 3

    def test_does_not_override_existing_keys(self, tmp_path):
        content = {
            "crawler": {
                "target_platforms": [{"url": "https://x.com", "name": "x", "parser": "B"}],
                "retry_limit": 5,
            },
            "rag": {"llm_api_key": "key", "llm_model": "gpt-3.5-turbo"},
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(content), encoding="utf-8")
        loader = ConfigLoader(str(path))
        config = loader.load()
        assert config["crawler"]["retry_limit"] == 5
        assert config["rag"]["llm_model"] == "gpt-3.5-turbo"

    def test_logs_warning_for_applied_defaults(self, config_file, caplog):
        loader = ConfigLoader(str(config_file))
        with caplog.at_level(logging.WARNING):
            loader.load()
        # Should have logged warnings about applied defaults
        assert "applying default" in caplog.text.lower() or "not set" in caplog.text.lower()


class TestDefaultConfigPath:
    def test_default_path_is_set(self):
        assert ConfigLoader.DEFAULT_CONFIG_PATH == "D:/CADAI/config.yaml"

    def test_uses_default_path_when_none(self):
        loader = ConfigLoader()
        assert loader.config_path == Path("D:/CADAI/config.yaml")
