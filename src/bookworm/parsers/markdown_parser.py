"""Markdown parser."""

from __future__ import annotations

import re
from pathlib import Path

from bookworm.library.models import Book, BookContent, Chapter

from .base import BaseParser


class MarkdownParser(BaseParser):
    SUPPORTED_EXTENSIONS = (".md", ".markdown")

    def parse(self, file_path: Path) -> BookContent:
        text = file_path.read_text(encoding="utf-8", errors="replace")

        meta = Book(
            id=Book.make_id(str(file_path)),
            file_path=str(file_path),
            title=file_path.stem,
            author="Unknown",
            format="md",
            file_size=file_path.stat().st_size,
        )

        # Split by headings (# or ##)
        chapters: list[Chapter] = []
        toc: list[tuple[int, str]] = []

        # Split on H1 or H2
        sections = re.split(r"(?m)^(#{1,2}\s+.+)$", text)

        current_title = file_path.stem
        current_paras: list[str] = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            heading_match = re.match(r"^#{1,2}\s+(.+)$", section)
            if heading_match:
                # Save previous
                if current_paras:
                    ch = Chapter(
                        index=len(chapters),
                        title=current_title,
                        paragraphs=current_paras,
                    )
                    chapters.append(ch)
                    toc.append((ch.index, current_title))
                current_title = heading_match.group(1).strip()
                current_paras = []
            else:
                # Process content: strip markdown formatting, split into paragraphs
                paras = self._md_to_paragraphs(section)
                current_paras.extend(paras)

        # Last section
        if current_paras:
            ch = Chapter(
                index=len(chapters), title=current_title, paragraphs=current_paras
            )
            chapters.append(ch)
            toc.append((ch.index, current_title))

        if not chapters:
            paras = self._md_to_paragraphs(text)
            if paras:
                chapters.append(
                    Chapter(index=0, title=file_path.stem, paragraphs=paras)
                )
                toc.append((0, file_path.stem))

        meta.total_chapters = len(chapters)
        return BookContent(metadata=meta, chapters=chapters, toc=toc)

    def _md_to_paragraphs(self, text: str) -> list[str]:
        """Convert markdown text to plain paragraphs."""
        # Strip common markdown formatting
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # images
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links → text
        text = re.sub(r"`{3}[\s\S]*?`{3}", "[code block]", text)  # code blocks
        text = re.sub(r"`([^`]+)`", r"\1", text)  # inline code
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
        text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)  # list markers
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)  # numbered lists
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)  # blockquotes
        text = re.sub(r"^#{3,6}\s+", "", text, flags=re.MULTILINE)  # sub-headings
        text = re.sub(r"^[-=]{3,}\s*$", "", text, flags=re.MULTILINE)  # hr

        paragraphs: list[str] = []
        for para in re.split(r"\n\s*\n", text):
            cleaned = re.sub(r"\s+", " ", para).strip()
            if cleaned and cleaned != "[code block]":
                paragraphs.append(cleaned)

        return paragraphs
