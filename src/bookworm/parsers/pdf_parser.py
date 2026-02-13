"""PDF parser using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from bookworm.library.models import Book, BookContent, Chapter

from .base import BaseParser


class PdfParser(BaseParser):
    SUPPORTED_EXTENSIONS = (".pdf",)

    def parse(self, file_path: Path) -> BookContent:
        doc = pymupdf.open(str(file_path))

        title = doc.metadata.get("title", "") or file_path.stem
        author = doc.metadata.get("author", "") or "Unknown"

        meta = Book(
            id=Book.make_id(str(file_path)),
            file_path=str(file_path),
            title=title,
            author=author,
            format="pdf",
            file_size=file_path.stat().st_size,
        )

        # Try to use PDF outline (bookmarks) for chapters
        toc_raw = doc.get_toc()  # list of [level, title, page]
        chapters: list[Chapter] = []
        toc: list[tuple[int, str]] = []

        if toc_raw:
            # Group pages by top-level TOC entries
            toc_entries = [(t[1], t[2] - 1) for t in toc_raw if t[0] <= 2]  # level 1-2
            for i, (ch_title, start_page) in enumerate(toc_entries):
                end_page = (
                    toc_entries[i + 1][1] if i + 1 < len(toc_entries) else len(doc)
                )
                paragraphs = self._extract_pages(doc, start_page, end_page)
                if paragraphs:
                    ch = Chapter(
                        index=len(chapters), title=ch_title, paragraphs=paragraphs
                    )
                    chapters.append(ch)
                    toc.append((ch.index, ch_title))
        else:
            # No TOC: treat every N pages as a chapter
            pages_per_chapter = max(1, min(20, len(doc) // 10))
            for start in range(0, len(doc), pages_per_chapter):
                end = min(start + pages_per_chapter, len(doc))
                paragraphs = self._extract_pages(doc, start, end)
                if paragraphs:
                    ch_title = f"Pages {start + 1}-{end}"
                    ch = Chapter(
                        index=len(chapters), title=ch_title, paragraphs=paragraphs
                    )
                    chapters.append(ch)
                    toc.append((ch.index, ch_title))

        doc.close()
        meta.total_chapters = len(chapters)
        return BookContent(metadata=meta, chapters=chapters, toc=toc)

    def _extract_pages(self, doc: pymupdf.Document, start: int, end: int) -> list[str]:
        """Extract text from a range of pages, split into paragraphs."""
        all_text = []
        for page_num in range(start, end):
            if page_num >= len(doc):
                break
            page = doc[page_num]
            blocks = page.get_text("blocks")
            page_height = page.rect.height

            for block in sorted(blocks, key=lambda b: b[1]):
                # block: (x0, y0, x1, y1, text, block_no, block_type)
                if block[6] != 0:  # skip image blocks
                    continue
                text = block[4].strip()
                if not text:
                    continue
                # Skip headers/footers (top 5% and bottom 5%)
                y_pos = block[1]
                if y_pos < page_height * 0.05 or y_pos > page_height * 0.95:
                    # Likely header or footer / page number
                    if len(text) < 80:
                        continue
                all_text.append(text)

        # Merge into paragraphs
        paragraphs: list[str] = []
        for text in all_text:
            cleaned = re.sub(r"\s+", " ", text).strip()
            if cleaned:
                paragraphs.append(cleaned)

        return paragraphs
