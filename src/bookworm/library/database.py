"""SQLite database for library, reading progress, bookmarks, and translation cache."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import Book, Bookmark, ReadingProgress

_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author TEXT DEFAULT 'Unknown',
    format TEXT DEFAULT '',
    file_size INTEGER DEFAULT 0,
    total_chapters INTEGER DEFAULT 0,
    added_at REAL NOT NULL,
    last_read_at REAL
);

CREATE TABLE IF NOT EXISTS reading_progress (
    book_id TEXT PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    chapter_index INTEGER DEFAULT 0,
    scroll_offset INTEGER DEFAULT 0,
    progress_pct REAL DEFAULT 0.0,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter_index INTEGER NOT NULL,
    scroll_offset INTEGER NOT NULL,
    label TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS translation_cache (
    hash TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ── Books ──────────────────────────────────────────────

    def add_book(self, book: Book) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO books
               (id, file_path, title, author, format, file_size, total_chapters, added_at, last_read_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                book.id,
                book.file_path,
                book.title,
                book.author,
                book.format,
                book.file_size,
                book.total_chapters,
                book.added_at,
                book.last_read_at,
            ),
        )
        self._conn.commit()

    def remove_book(self, book_id: str) -> None:
        self._conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        self._conn.commit()

    def get_book(self, book_id: str) -> Optional[Book]:
        row = self._conn.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        return self._row_to_book(row) if row else None

    def get_book_by_path(self, file_path: str) -> Optional[Book]:
        row = self._conn.execute(
            "SELECT * FROM books WHERE file_path = ?", (file_path,)
        ).fetchone()
        return self._row_to_book(row) if row else None

    def list_books(self, order_by: str = "last_read_at DESC") -> list[Book]:
        allowed = {
            "last_read_at DESC",
            "last_read_at ASC",
            "title ASC",
            "title DESC",
            "added_at DESC",
            "added_at ASC",
            "author ASC",
            "author DESC",
        }
        if order_by not in allowed:
            order_by = "last_read_at DESC"
        rows = self._conn.execute(
            f"SELECT * FROM books ORDER BY {order_by} NULLS LAST"
        ).fetchall()
        return [self._row_to_book(r) for r in rows]

    def search_books(self, query: str) -> list[Book]:
        q = f"%{query}%"
        rows = self._conn.execute(
            "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY last_read_at DESC NULLS LAST",
            (q, q),
        ).fetchall()
        return [self._row_to_book(r) for r in rows]

    def update_last_read(self, book_id: str) -> None:
        self._conn.execute(
            "UPDATE books SET last_read_at = ? WHERE id = ?", (time.time(), book_id)
        )
        self._conn.commit()

    @staticmethod
    def _row_to_book(row: sqlite3.Row) -> Book:
        return Book(
            id=row["id"],
            file_path=row["file_path"],
            title=row["title"],
            author=row["author"],
            format=row["format"],
            file_size=row["file_size"],
            total_chapters=row["total_chapters"],
            added_at=row["added_at"],
            last_read_at=row["last_read_at"],
        )

    # ── Reading Progress ───────────────────────────────────

    def save_progress(self, progress: ReadingProgress) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO reading_progress
               (book_id, chapter_index, scroll_offset, progress_pct, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                progress.book_id,
                progress.chapter_index,
                progress.scroll_offset,
                progress.progress_pct,
                progress.updated_at,
            ),
        )
        self._conn.commit()

    def get_progress(self, book_id: str) -> Optional[ReadingProgress]:
        row = self._conn.execute(
            "SELECT * FROM reading_progress WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        if not row:
            return None
        return ReadingProgress(
            book_id=row["book_id"],
            chapter_index=row["chapter_index"],
            scroll_offset=row["scroll_offset"],
            progress_pct=row["progress_pct"],
            updated_at=row["updated_at"],
        )

    # ── Bookmarks ──────────────────────────────────────────

    def add_bookmark(self, bm: Bookmark) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO bookmarks
               (id, book_id, chapter_index, scroll_offset, label, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                bm.id,
                bm.book_id,
                bm.chapter_index,
                bm.scroll_offset,
                bm.label,
                bm.created_at,
            ),
        )
        self._conn.commit()

    def remove_bookmark(self, bookmark_id: str) -> None:
        self._conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        self._conn.commit()

    def list_bookmarks(self, book_id: str) -> list[Bookmark]:
        rows = self._conn.execute(
            "SELECT * FROM bookmarks WHERE book_id = ? ORDER BY chapter_index, scroll_offset",
            (book_id,),
        ).fetchall()
        return [
            Bookmark(
                id=r["id"],
                book_id=r["book_id"],
                chapter_index=r["chapter_index"],
                scroll_offset=r["scroll_offset"],
                label=r["label"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Translation Cache ──────────────────────────────────

    def get_cached_translation(self, text_hash: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT translated_text FROM translation_cache WHERE hash = ?",
            (text_hash,),
        ).fetchone()
        return row["translated_text"] if row else None

    def cache_translation(
        self,
        text_hash: str,
        source_text: str,
        translated_text: str,
        target_lang: str,
        provider: str,
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO translation_cache
               (hash, source_text, translated_text, target_lang, provider, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                text_hash,
                source_text,
                translated_text,
                target_lang,
                provider,
                time.time(),
            ),
        )
        self._conn.commit()
