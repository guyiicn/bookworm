"""Base parser interface for all ebook formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from bookworm.library.models import BookContent


class BaseParser(ABC):
    """Abstract base for format-specific parsers."""

    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, file_path: Path) -> BookContent:
        """Parse a file and return structured book content."""

    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        return file_path.suffix.lower() in cls.SUPPORTED_EXTENSIONS


def get_parser(file_path: Path) -> BaseParser:
    """Return the appropriate parser for a file."""
    from bookworm.parsers.docx_parser import DocxParser
    from bookworm.parsers.epub_parser import EpubParser
    from bookworm.parsers.markdown_parser import MarkdownParser
    from bookworm.parsers.mobi_parser import MobiParser
    from bookworm.parsers.pdf_parser import PdfParser
    from bookworm.parsers.txt_parser import TxtParser

    parsers: list[type[BaseParser]] = [
        EpubParser,
        PdfParser,
        DocxParser,
        MarkdownParser,
        TxtParser,
        MobiParser,
    ]
    for parser_cls in parsers:
        if parser_cls.can_handle(file_path):
            return parser_cls()

    supported = []
    for p in parsers:
        supported.extend(p.SUPPORTED_EXTENSIONS)
    raise ValueError(
        f"Unsupported format: {file_path.suffix}. Supported: {', '.join(supported)}"
    )
