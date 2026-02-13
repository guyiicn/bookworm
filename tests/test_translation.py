"""Tests for translation engine."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from bookworm.config import AppConfig, TranslationProviderConfig
from bookworm.library.database import Database
from bookworm.translation.engine import TranslationEngine


@pytest.fixture
def engine(tmp_path: Path) -> TranslationEngine:
    config = AppConfig(data_dir=tmp_path / "data", config_dir=tmp_path / "config")
    config.providers["openai"] = TranslationProviderConfig(
        name="openai",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )
    config.translate_provider = "openai"
    db = Database(tmp_path / "test.db")
    return TranslationEngine(config, db)


@pytest.fixture
def engine_no_key(tmp_path: Path) -> TranslationEngine:
    config = AppConfig(data_dir=tmp_path / "data", config_dir=tmp_path / "config")
    config.providers["openai"] = TranslationProviderConfig(
        name="openai",
        api_key="",
        base_url="",
        model="",
    )
    config.translate_provider = "openai"
    db = Database(tmp_path / "test.db")
    return TranslationEngine(config, db)


@pytest.fixture
def engine_ollama(tmp_path: Path) -> TranslationEngine:
    config = AppConfig(data_dir=tmp_path / "data", config_dir=tmp_path / "config")
    config.providers["ollama"] = TranslationProviderConfig(
        name="ollama",
        api_key="",
        base_url="http://localhost:11434/v1",
        model="qwen2.5:7b",
    )
    config.translate_provider = "ollama"
    db = Database(tmp_path / "test.db")
    return TranslationEngine(config, db)


class TestTranslationEngine:
    def test_is_configured(self, engine: TranslationEngine):
        assert engine.is_configured is True

    def test_not_configured_no_key(self, engine_no_key: TranslationEngine):
        assert engine_no_key.is_configured is False

    def test_ollama_configured_without_key(self, engine_ollama: TranslationEngine):
        assert engine_ollama.is_configured is True

    def test_target_lang(self, engine: TranslationEngine):
        assert engine.target_lang == "zh-CN"

    def test_provider(self, engine: TranslationEngine):
        p = engine.provider
        assert p is not None
        assert p.name == "openai"
        assert p.api_key == "sk-test"

    @pytest.mark.asyncio
    async def test_empty_text_batch(self, engine: TranslationEngine):
        results = await engine.translate_batch([""])
        assert results == [""]

    def test_is_translated(self, engine: TranslationEngine):
        assert engine.is_translated("") is True
        assert engine.is_translated("Hello") is False
        h = engine._make_hash("Hello", "zh-CN")
        engine._db.cache_translation(h, "Hello", "你好", "zh-CN", "openai")
        assert engine.is_translated("Hello") is True

    def test_get_cached(self, engine: TranslationEngine):
        assert engine.get_cached("Hello") is None
        h = engine._make_hash("Hello", "zh-CN")
        engine._db.cache_translation(h, "Hello", "你好", "zh-CN", "openai")
        assert engine.get_cached("Hello") == "你好"

    def test_count_translated(self, engine: TranslationEngine):
        h = engine._make_hash("Hello", "zh-CN")
        engine._db.cache_translation(h, "Hello", "你好", "zh-CN", "openai")
        assert engine.count_translated(["Hello", "World", ""]) == 2

    @pytest.mark.asyncio
    async def test_cache_hit(self, engine: TranslationEngine):
        text = "Hello world"
        text_hash = engine._make_hash(text, "zh-CN")
        engine._db.cache_translation(text_hash, text, "你好世界", "zh-CN", "openai")

        results = await engine.translate_batch([text])
        assert results[0] == "你好世界"

    @pytest.mark.asyncio
    async def test_translate_batch_calls_api_and_caches(
        self, engine: TranslationEngine
    ):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock(return_value=None)
        mock_response.json = Mock(
            return_value={
                "choices": [{"message": {"content": "你好"}}],
            }
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            results = await engine.translate_batch(["Hello"])
            assert results[0] == "你好"

            text_hash = engine._make_hash("Hello", "zh-CN")
            cached = engine._db.get_cached_translation(text_hash)
            assert cached == "你好"

    @pytest.mark.asyncio
    async def test_translate_batch_mixed_cache(self, engine: TranslationEngine):
        h = engine._make_hash("Hello", "zh-CN")
        engine._db.cache_translation(h, "Hello", "你好", "zh-CN", "openai")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock(return_value=None)
        mock_response.json = Mock(
            return_value={
                "choices": [{"message": {"content": "世界"}}],
            }
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            results = await engine.translate_batch(["Hello", "World"])
            assert results[0] == "你好"
            assert results[1] == "世界"

    def test_cancel_and_reset(self, engine: TranslationEngine):
        assert engine._cancel is False
        engine.cancel()
        assert engine._cancel is True
        engine.reset_cancel()
        assert engine._cancel is False

    def test_make_hash_deterministic(self, engine: TranslationEngine):
        h1 = engine._make_hash("text", "zh-CN")
        h2 = engine._make_hash("text", "zh-CN")
        assert h1 == h2

    def test_make_hash_different_langs(self, engine: TranslationEngine):
        h1 = engine._make_hash("text", "zh-CN")
        h2 = engine._make_hash("text", "en")
        assert h1 != h2
