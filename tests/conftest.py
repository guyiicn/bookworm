"""Shared fixtures for tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bookworm.config import AppConfig
from bookworm.library.database import Database


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
    )
