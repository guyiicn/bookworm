"""Tests for data models."""

from bookworm.library.models import (
    Book,
    Bookmark,
    Chapter,
    BookContent,
    ReadingProgress,
)


class TestBook:
    def test_make_id_deterministic(self):
        id1 = Book.make_id("/path/to/book.epub")
        id2 = Book.make_id("/path/to/book.epub")
        assert id1 == id2

    def test_make_id_different_paths(self):
        id1 = Book.make_id("/path/a.epub")
        id2 = Book.make_id("/path/b.epub")
        assert id1 != id2

    def test_make_id_length(self):
        book_id = Book.make_id("/some/path.epub")
        assert len(book_id) == 16

    def test_book_defaults(self):
        book = Book(id="abc", file_path="/f.epub", title="Test")
        assert book.author == "Unknown"
        assert book.format == ""
        assert book.file_size == 0
        assert book.last_read_at is None


class TestBookmark:
    def test_make_id_deterministic(self):
        id1 = Bookmark.make_id("book1", 0, 100)
        id2 = Bookmark.make_id("book1", 0, 100)
        assert id1 == id2

    def test_make_id_different_positions(self):
        id1 = Bookmark.make_id("book1", 0, 100)
        id2 = Bookmark.make_id("book1", 1, 100)
        assert id1 != id2

    def test_make_id_length(self):
        bm_id = Bookmark.make_id("book1", 0, 0)
        assert len(bm_id) == 12


class TestChapter:
    def test_empty_paragraphs_default(self):
        ch = Chapter(index=0, title="Test")
        assert ch.paragraphs == []

    def test_with_paragraphs(self):
        ch = Chapter(index=1, title="Ch 1", paragraphs=["p1", "p2"])
        assert len(ch.paragraphs) == 2


class TestBookContent:
    def test_empty_defaults(self):
        book = Book(id="x", file_path="/f", title="T")
        content = BookContent(metadata=book)
        assert content.chapters == []
        assert content.toc == []
