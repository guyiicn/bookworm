"""Tests for database operations."""

from __future__ import annotations

import time

import pytest

from bookworm.library.database import Database
from bookworm.library.models import Book, Bookmark, ReadingProgress


def _make_book(
    title: str = "Test Book", author: str = "Author", path: str = "/test.epub"
) -> Book:
    return Book(
        id=Book.make_id(path),
        file_path=path,
        title=title,
        author=author,
        format="epub",
        file_size=1024,
        total_chapters=5,
        added_at=time.time(),
    )


class TestBooksCRUD:
    def test_add_and_get(self, db: Database):
        book = _make_book()
        db.add_book(book)
        fetched = db.get_book(book.id)
        assert fetched is not None
        assert fetched.title == "Test Book"
        assert fetched.author == "Author"
        assert fetched.format == "epub"

    def test_get_nonexistent(self, db: Database):
        assert db.get_book("nonexistent") is None

    def test_get_by_path(self, db: Database):
        book = _make_book(path="/some/file.pdf")
        db.add_book(book)
        fetched = db.get_book_by_path("/some/file.pdf")
        assert fetched is not None
        assert fetched.title == "Test Book"

    def test_get_by_path_nonexistent(self, db: Database):
        assert db.get_book_by_path("/no/such/file") is None

    def test_remove(self, db: Database):
        book = _make_book()
        db.add_book(book)
        db.remove_book(book.id)
        assert db.get_book(book.id) is None

    def test_list_books_empty(self, db: Database):
        assert db.list_books() == []

    def test_list_books_ordered(self, db: Database):
        b1 = _make_book("Book A", path="/a.epub")
        b1.last_read_at = time.time() - 100
        db.add_book(b1)

        b2 = _make_book("Book B", path="/b.epub")
        b2.last_read_at = time.time()
        db.add_book(b2)

        books = db.list_books(order_by="last_read_at DESC")
        assert len(books) == 2
        assert books[0].title == "Book B"

    def test_list_books_by_title(self, db: Database):
        db.add_book(_make_book("Zebra", path="/z.epub"))
        db.add_book(_make_book("Alpha", path="/a.epub"))
        books = db.list_books(order_by="title ASC")
        assert books[0].title == "Alpha"
        assert books[1].title == "Zebra"

    def test_list_books_invalid_order(self, db: Database):
        db.add_book(_make_book())
        # Should fall back to default order
        books = db.list_books(order_by="DROP TABLE books;--")
        assert len(books) == 1

    def test_search_by_title(self, db: Database):
        db.add_book(_make_book("Python Cookbook", path="/py.epub"))
        db.add_book(_make_book("Rust Guide", path="/rs.epub"))
        results = db.search_books("Python")
        assert len(results) == 1
        assert results[0].title == "Python Cookbook"

    def test_search_by_author(self, db: Database):
        db.add_book(_make_book("Book A", author="John", path="/a.epub"))
        db.add_book(_make_book("Book B", author="Jane", path="/b.epub"))
        results = db.search_books("Jane")
        assert len(results) == 1
        assert results[0].author == "Jane"

    def test_search_no_results(self, db: Database):
        db.add_book(_make_book())
        assert db.search_books("nonexistent") == []

    def test_update_last_read(self, db: Database):
        book = _make_book()
        book.last_read_at = None
        db.add_book(book)
        db.update_last_read(book.id)
        fetched = db.get_book(book.id)
        assert fetched is not None
        assert fetched.last_read_at is not None

    def test_add_book_upsert(self, db: Database):
        book = _make_book(title="Original")
        db.add_book(book)
        book.title = "Updated"
        db.add_book(book)
        fetched = db.get_book(book.id)
        assert fetched is not None
        assert fetched.title == "Updated"


class TestReadingProgress:
    def test_save_and_get(self, db: Database):
        book = _make_book()
        db.add_book(book)
        progress = ReadingProgress(
            book_id=book.id,
            chapter_index=2,
            scroll_offset=50,
            progress_pct=0.4,
            updated_at=time.time(),
        )
        db.save_progress(progress)
        fetched = db.get_progress(book.id)
        assert fetched is not None
        assert fetched.chapter_index == 2
        assert fetched.scroll_offset == 50
        assert abs(fetched.progress_pct - 0.4) < 0.001

    def test_get_no_progress(self, db: Database):
        assert db.get_progress("nonexistent") is None

    def test_update_progress(self, db: Database):
        book = _make_book()
        db.add_book(book)
        p1 = ReadingProgress(book_id=book.id, chapter_index=0, updated_at=time.time())
        db.save_progress(p1)
        p2 = ReadingProgress(
            book_id=book.id, chapter_index=3, progress_pct=0.6, updated_at=time.time()
        )
        db.save_progress(p2)
        fetched = db.get_progress(book.id)
        assert fetched is not None
        assert fetched.chapter_index == 3

    def test_cascade_delete(self, db: Database):
        book = _make_book()
        db.add_book(book)
        db.save_progress(ReadingProgress(book_id=book.id, updated_at=time.time()))
        db.remove_book(book.id)
        assert db.get_progress(book.id) is None


class TestBookmarks:
    def test_add_and_list(self, db: Database):
        book = _make_book()
        db.add_book(book)
        bm = Bookmark(
            id=Bookmark.make_id(book.id, 0, 10),
            book_id=book.id,
            chapter_index=0,
            scroll_offset=10,
            label="My Bookmark",
            created_at=time.time(),
        )
        db.add_bookmark(bm)
        bookmarks = db.list_bookmarks(book.id)
        assert len(bookmarks) == 1
        assert bookmarks[0].label == "My Bookmark"
        assert bookmarks[0].chapter_index == 0

    def test_remove_bookmark(self, db: Database):
        book = _make_book()
        db.add_book(book)
        bm = Bookmark(
            id="bm1",
            book_id=book.id,
            chapter_index=0,
            scroll_offset=0,
            created_at=time.time(),
        )
        db.add_bookmark(bm)
        db.remove_bookmark("bm1")
        assert db.list_bookmarks(book.id) == []

    def test_list_empty(self, db: Database):
        assert db.list_bookmarks("nonexistent") == []

    def test_multiple_bookmarks_ordered(self, db: Database):
        book = _make_book()
        db.add_book(book)
        for ch in range(3):
            bm = Bookmark(
                id=f"bm{ch}",
                book_id=book.id,
                chapter_index=ch,
                scroll_offset=0,
                created_at=time.time(),
            )
            db.add_bookmark(bm)
        bookmarks = db.list_bookmarks(book.id)
        assert len(bookmarks) == 3
        assert bookmarks[0].chapter_index == 0
        assert bookmarks[2].chapter_index == 2

    def test_cascade_delete(self, db: Database):
        book = _make_book()
        db.add_book(book)
        db.add_bookmark(
            Bookmark(
                id="bm1",
                book_id=book.id,
                chapter_index=0,
                scroll_offset=0,
                created_at=time.time(),
            )
        )
        db.remove_book(book.id)
        assert db.list_bookmarks(book.id) == []


class TestTranslationCache:
    def test_cache_and_get(self, db: Database):
        db.cache_translation(
            text_hash="abc123",
            source_text="Hello",
            translated_text="你好",
            target_lang="zh-CN",
            provider="openai",
        )
        result = db.get_cached_translation("abc123")
        assert result == "你好"

    def test_cache_miss(self, db: Database):
        assert db.get_cached_translation("nonexistent") is None

    def test_cache_upsert(self, db: Database):
        db.cache_translation("h1", "Hi", "你好v1", "zh-CN", "openai")
        db.cache_translation("h1", "Hi", "你好v2", "zh-CN", "openai")
        assert db.get_cached_translation("h1") == "你好v2"
