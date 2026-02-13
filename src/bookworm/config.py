"""Configuration management via .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


@dataclass
class TranslationProviderConfig:
    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass
class AppConfig:
    # Paths
    data_dir: Path = field(default_factory=lambda: _xdg_data_home() / "bookworm")
    config_dir: Path = field(default_factory=lambda: _xdg_config_home() / "bookworm")
    db_path: Path = field(init=False)

    # Translation
    translate_provider: str = "qwen"
    translate_target_lang: str = "zh-CN"
    providers: dict[str, TranslationProviderConfig] = field(default_factory=dict)

    # Reading defaults
    default_line_spacing: int = 1  # 0=compact, 1=normal, 2=wide, 3=extra-wide
    default_dual_page: bool = False

    log_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.db_path = self.data_dir / "bookworm.db"
        self.log_path = self.data_dir / "bookworm.log"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def get_active_provider(self) -> Optional[TranslationProviderConfig]:
        return self.providers.get(self.translate_provider)


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    """Load config from .env file. Searches CWD then config dir."""
    search_paths = [
        env_path,
        Path.cwd() / ".env",
        _xdg_config_home() / "bookworm" / ".env",
        Path.home() / ".env",
    ]
    for p in search_paths:
        if p and p.exists():
            load_dotenv(p)
            break

    defaults = AppConfig()
    config = AppConfig(
        translate_provider=os.getenv(
            "BOOKWORM_TRANSLATE_PROVIDER", defaults.translate_provider
        ),
        translate_target_lang=os.getenv(
            "BOOKWORM_TRANSLATE_TARGET_LANG", defaults.translate_target_lang
        ),
    )

    # Load all provider configs
    provider_defs = {
        "openai": (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "https://api.openai.com/v1",
            "gpt-4o-mini",
        ),
        "claude": (
            "CLAUDE_API_KEY",
            "CLAUDE_BASE_URL",
            "CLAUDE_MODEL",
            "https://api.anthropic.com/v1",
            "claude-sonnet-4-20250514",
        ),
        "qwen": (
            "QWEN_API_KEY",
            "QWEN_BASE_URL",
            "QWEN_MODEL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-plus",
        ),
        "glm": (
            "GLM_API_KEY",
            "GLM_BASE_URL",
            "GLM_MODEL",
            "https://open.bigmodel.cn/api/paas/v4",
            "glm-4-flash",
        ),
        "openrouter": (
            "OPENROUTER_API_KEY",
            "OPENROUTER_BASE_URL",
            "OPENROUTER_MODEL",
            "https://openrouter.ai/api/v1",
            "google/gemini-2.0-flash-001",
        ),
        "ollama": (
            "",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "http://localhost:11434/v1",
            "qwen2.5:7b",
        ),
    }

    for name, (
        key_env,
        url_env,
        model_env,
        default_url,
        default_model,
    ) in provider_defs.items():
        api_key = os.getenv(key_env, "") if key_env else ""
        base_url = os.getenv(url_env, default_url)
        model = os.getenv(model_env, default_model)
        config.providers[name] = TranslationProviderConfig(
            name=name,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    return config
