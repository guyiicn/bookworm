"""Plain text parser."""

from __future__ import annotations

import re
from pathlib import Path

from bookworm.library.models import Book, BookContent, Chapter

from .base import BaseParser


class TxtParser(BaseParser):
    SUPPORTED_EXTENSIONS = (".txt", ".text")

    def parse(self, file_path: Path) -> BookContent:
        text = file_path.read_text(encoding="utf-8", errors="replace")

        meta = Book(
            id=Book.make_id(str(file_path)),
            file_path=str(file_path),
            title=file_path.stem,
            author="Unknown",
            format="txt",
            file_size=file_path.stat().st_size,
        )

        # Try to detect chapter breaks
        chapters: list[Chapter] = []
        toc: list[tuple[int, str]] = []

        # Common chapter patterns
        chapter_pattern = re.compile(
            r"(?m)^(?:Chapter|CHAPTER|第.{1,10}[章节回]|Part|PART)\s*.{0,100}$"
        )

        parts = chapter_pattern.split(text)
        titles = chapter_pattern.findall(text)

        if len(titles) >= 2:
            # Has chapter structure
            # Handle text before first chapter
            preamble = self._text_to_paragraphs(parts[0])
            if preamble:
                ch = Chapter(index=0, title="Preamble", paragraphs=preamble)
                chapters.append(ch)
                toc.append((0, "Preamble"))

            for i, (title, content) in enumerate(zip(titles, parts[1:])):
                paras = self._text_to_paragraphs(content)
                if paras:
                    ch = Chapter(
                        index=len(chapters), title=title.strip(), paragraphs=paras
                    )
                    chapters.append(ch)
                    toc.append((ch.index, title.strip()))
        else:
            # No chapter structure: split into chunks
            all_paras = self._text_to_paragraphs(text)
            chunk_size = 50  # paragraphs per chunk
            for i in range(0, max(1, len(all_paras)), chunk_size):
                chunk = all_paras[i : i + chunk_size]
                if chunk:
                    ch_title = f"Section {len(chapters) + 1}"
                    ch = Chapter(index=len(chapters), title=ch_title, paragraphs=chunk)
                    chapters.append(ch)
                    toc.append((ch.index, ch_title))

        meta.total_chapters = len(chapters)
        return BookContent(metadata=meta, chapters=chapters, toc=toc)

    def _text_to_paragraphs(self, text: str) -> list[str]:
        paragraphs: list[str] = []
        for para in re.split(r"\n\s*\n", text):
            cleaned = re.sub(r"\s+", " ", para).strip()
            if cleaned:
                paragraphs.append(cleaned)
        return paragraphs
