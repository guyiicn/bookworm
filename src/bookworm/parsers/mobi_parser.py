"""MOBI parser — converts to EPUB via Calibre, then parses."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from bookworm.library.models import Book, BookContent

from .base import BaseParser


class MobiParser(BaseParser):
    SUPPORTED_EXTENSIONS = (".mobi", ".azw", ".azw3")

    def parse(self, file_path: Path) -> BookContent:
        ebook_convert = shutil.which("ebook-convert")
        if not ebook_convert:
            raise RuntimeError(
                "Calibre's ebook-convert is required for MOBI/AZW files. "
                "Install it: https://calibre-ebook.com/download"
            )

        # Convert to epub in a temp dir
        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / "converted.epub"
            result = subprocess.run(
                [ebook_convert, str(file_path), str(epub_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ebook-convert failed: {result.stderr[:500]}")

            # Parse the converted EPUB
            from bookworm.parsers.epub_parser import EpubParser

            content = EpubParser().parse(epub_path)

        # Fix metadata to point to original file
        content.metadata = Book(
            id=Book.make_id(str(file_path)),
            file_path=str(file_path),
            title=content.metadata.title,
            author=content.metadata.author,
            format=file_path.suffix.lstrip("."),
            file_size=file_path.stat().st_size,
            total_chapters=content.metadata.total_chapters,
        )
        return content
