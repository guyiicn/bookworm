"""Tests for configuration."""

from __future__ import annotations

from pathlib import Path

from bookworm.config import AppConfig, load_config


class TestAppConfig:
    def test_defaults(self, tmp_path: Path):
        config = AppConfig(data_dir=tmp_path / "data", config_dir=tmp_path / "config")
        assert config.translate_provider == "qwen"
        assert config.translate_target_lang == "zh-CN"
        assert config.default_line_spacing == 1
        assert config.default_dual_page is False
        assert config.db_path == tmp_path / "data" / "bookworm.db"

    def test_dirs_created(self, tmp_path: Path):
        data = tmp_path / "data"
        conf = tmp_path / "config"
        AppConfig(data_dir=data, config_dir=conf)
        assert data.exists()
        assert conf.exists()

    def test_get_active_provider(self, tmp_path: Path):
        config = AppConfig(data_dir=tmp_path / "d", config_dir=tmp_path / "c")
        config.providers = {"openai": object()}  # type: ignore[dict-item]
        config.translate_provider = "openai"
        assert config.get_active_provider() is not None

    def test_get_active_provider_missing(self, tmp_path: Path):
        config = AppConfig(data_dir=tmp_path / "d", config_dir=tmp_path / "c")
        config.translate_provider = "nonexistent"
        assert config.get_active_provider() is None


class TestLoadConfig:
    def test_load_from_env_file(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BOOKWORM_TRANSLATE_PROVIDER=glm\n"
            "BOOKWORM_TRANSLATE_TARGET_LANG=en\n"
            "GLM_API_KEY=test-key-123\n"
            "GLM_MODEL=glm-4\n"
        )
        config = load_config(env_path=env_file)
        assert config.translate_provider == "glm"
        assert config.translate_target_lang == "en"
        assert config.providers["glm"].api_key == "test-key-123"
        assert config.providers["glm"].model == "glm-4"

    def test_all_providers_loaded(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        config = load_config(env_path=env_file)
        expected = {"openai", "claude", "qwen", "glm", "openrouter", "ollama"}
        assert set(config.providers.keys()) == expected

    def test_ollama_no_api_key(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        config = load_config(env_path=env_file)
        assert config.providers["ollama"].api_key == ""
        assert "localhost" in config.providers["ollama"].base_url
