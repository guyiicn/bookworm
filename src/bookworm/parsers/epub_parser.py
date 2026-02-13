"""EPUB parser using ebooklib."""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from bookworm.library.models import Book, BookContent, Chapter

from .base import BaseParser


class EpubParser(BaseParser):
    SUPPORTED_EXTENSIONS = (".epub",)

    def parse(self, file_path: Path) -> BookContent:
        book = epub.read_epub(str(file_path), options={"ignore_ncx": False})

        # Extract metadata
        title = self._get_meta(book, "title") or file_path.stem
        author = self._get_meta(book, "creator") or "Unknown"

        meta = Book(
            id=Book.make_id(str(file_path)),
            file_path=str(file_path),
            title=title,
            author=author,
            format="epub",
            file_size=file_path.stat().st_size,
        )

        # Extract chapters from spine
        chapters: list[Chapter] = []
        toc: list[tuple[int, str]] = []

        spine_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        # Use spine order
        spine_ids = [item_id for item_id, _ in book.spine]
        id_to_item = {item.get_id(): item for item in spine_items}

        ordered_items = []
        for sid in spine_ids:
            if sid in id_to_item:
                ordered_items.append(id_to_item[sid])
        # Fall back to all document items if spine is empty
        if not ordered_items:
            ordered_items = spine_items

        for idx, item in enumerate(ordered_items):
            content = item.get_content().decode("utf-8", errors="replace")
            paragraphs = self._html_to_paragraphs(content)
            if not paragraphs:
                continue

            # Try to extract chapter title from content
            ch_title = self._extract_title(content) or f"Chapter {len(chapters) + 1}"
            chapter = Chapter(
                index=len(chapters), title=ch_title, paragraphs=paragraphs
            )
            chapters.append(chapter)
            toc.append((chapter.index, ch_title))

        # Override TOC from book's table of contents if available
        book_toc = self._extract_toc(book, ordered_items)
        if book_toc:
            toc = book_toc

        meta.total_chapters = len(chapters)
        return BookContent(metadata=meta, chapters=chapters, toc=toc)

    _BLOCK_TAGS = frozenset(
        ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre"]
    )

    def _html_to_paragraphs(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup.find_all(["script", "style", "sup"]):
            tag.decompose()

        paragraphs: list[str] = []
        block_tags = soup.find_all(list(self._BLOCK_TAGS))

        if block_tags:
            for tag in block_tags:
                if tag.find(list(self._BLOCK_TAGS)):
                    continue
                text = tag.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    paragraphs.append(text)
        else:
            text = soup.get_text(separator="\n")
            for para in re.split(r"\n\s*\n", text):
                cleaned = re.sub(r"\s+", " ", para).strip()
                if cleaned:
                    paragraphs.append(cleaned)

        return paragraphs

    def _extract_title(self, html: str) -> str:
        """Try to extract a title from heading tags."""
        soup = BeautifulSoup(html, "lxml")
        for level in ["h1", "h2", "h3", "title"]:
            tag = soup.find(level)
            if tag:
                text = tag.get_text(strip=True)
                if text and len(text) < 200:
                    return text
        return ""

    def _extract_toc(
        self,
        book: epub.EpubBook,
        ordered_items: list[epub.EpubItem],
    ) -> list[tuple[int, str]]:
        """Extract TOC from epub's navigation."""
        toc_entries: list[tuple[int, str]] = []
        item_names = [item.get_name() for item in ordered_items]

        def _flatten_toc(toc_list: list, depth: int = 0) -> None:
            for entry in toc_list:
                if isinstance(entry, tuple):
                    # Section with sub-entries
                    _flatten_toc(list(entry), depth)
                elif isinstance(entry, epub.Link):
                    href = entry.href.split("#")[0] if entry.href else ""
                    title = entry.title or ""
                    if title:
                        # Find matching chapter index
                        for idx, name in enumerate(item_names):
                            if (
                                name == href
                                or href.endswith(name)
                                or name.endswith(href)
                            ):
                                toc_entries.append((idx, title))
                                break
                elif isinstance(entry, list):
                    _flatten_toc(entry, depth + 1)

        try:
            _flatten_toc(book.toc)
        except Exception:
            pass

        return toc_entries

    @staticmethod
    def _get_meta(book: epub.EpubBook, field: str) -> str:
        values = book.get_metadata("DC", field)
        if values:
            val = values[0]
            if isinstance(val, tuple):
                return str(val[0]) if val[0] else ""
            return str(val)
        return ""
