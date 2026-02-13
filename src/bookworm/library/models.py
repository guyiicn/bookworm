"""Data models for the book library."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Book:
    id: str  # SHA256 of file path
    file_path: str
    title: str
    author: str = "Unknown"
    format: str = ""  # epub, pdf, docx, md, txt, mobi
    file_size: int = 0
    total_chapters: int = 0
    added_at: float = field(default_factory=time.time)
    last_read_at: Optional[float] = None

    @staticmethod
    def make_id(file_path: str) -> str:
        return hashlib.sha256(file_path.encode()).hexdigest()[:16]


@dataclass
class ReadingProgress:
    book_id: str
    chapter_index: int = 0
    scroll_offset: int = 0  # line offset within chapter
    progress_pct: float = 0.0  # 0.0 - 1.0
    updated_at: float = field(default_factory=time.time)


@dataclass
class Bookmark:
    id: str  # auto-generated
    book_id: str
    chapter_index: int
    scroll_offset: int
    label: str = ""
    created_at: float = field(default_factory=time.time)

    @staticmethod
    def make_id(book_id: str, chapter_index: int, scroll_offset: int) -> str:
        raw = f"{book_id}:{chapter_index}:{scroll_offset}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class Chapter:
    """Parsed chapter content."""

    index: int
    title: str
    paragraphs: list[str] = field(default_factory=list)  # plain text paragraphs


@dataclass
class BookContent:
    """Full parsed book structure."""

    metadata: Book
    chapters: list[Chapter] = field(default_factory=list)
    toc: list[tuple[int, str]] = field(default_factory=list)  # (chapter_index, title)
