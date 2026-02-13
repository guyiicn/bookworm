"""Bookworm - CLI Ebook Reader."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from textual.app import App

from bookworm.config import AppConfig, load_config
from bookworm.library.database import Database
from bookworm.library.models import Book
from bookworm.translation.engine import TranslationEngine
from bookworm.ui.screens.library_screen import LibraryScreen
from bookworm.ui.screens.reader_screen import ReaderScreen
from bookworm.ui.themes import APP_CSS


class BookwormApp(App):
    """A CLI ebook reader with library management and translation."""

    TITLE = "Bookworm"
    CSS = APP_CSS

    def __init__(
        self, config: AppConfig | None = None, open_file: str | None = None
    ) -> None:
        super().__init__()
        self.config = config or load_config()
        self.db = Database(self.config.db_path)
        self.translator = TranslationEngine(self.config, self.db)
        self._open_file = open_file

    def on_mount(self) -> None:
        if self._open_file:
            self._import_file(self._open_file)
        self.push_screen(LibraryScreen())

    def _import_file(self, file_path_str: str) -> None:
        import time

        from bookworm.parsers.base import get_parser

        file_path = Path(file_path_str).expanduser().resolve()
        if not file_path.exists():
            self.notify(f"File not found: {file_path}", severity="error")
            return

        if self.db.get_book_by_path(str(file_path)):
            return

        try:
            parser = get_parser(file_path)
            content = parser.parse(file_path)
            book = content.metadata
            book.added_at = time.time()
            self.db.add_book(book)
        except Exception as e:
            self.notify(f"Error importing: {e}", severity="error")

    def open_book(self, book: Book) -> None:
        """Open a book in the reader. Called from LibraryScreen."""
        self.push_screen(ReaderScreen(book))

    async def action_quit(self) -> None:
        await self.translator.close()
        self.db.close()
        self.exit()


def _setup_logging(config: AppConfig) -> None:
    handler = logging.FileHandler(config.log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger("bookworm")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


def main() -> None:
    config = load_config()
    _setup_logging(config)

    open_file: str | None = None
    if len(sys.argv) > 1:
        open_file = sys.argv[1]

    app = BookwormApp(config=config, open_file=open_file)
    app.run()


if __name__ == "__main__":
    main()
