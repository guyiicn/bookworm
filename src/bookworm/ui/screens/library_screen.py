from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

if TYPE_CHECKING:
    from bookworm.app import BookwormApp

SORT_OPTIONS = [
    ("last_read_at DESC", "Last Read"),
    ("title ASC", "Title A-Z"),
    ("author ASC", "Author A-Z"),
    ("added_at DESC", "Recently Added"),
]

BOOK_EXTENSIONS = {
    ".epub",
    ".mobi",
    ".pdf",
    ".docx",
    ".md",
    ".txt",
}


class BookDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return sorted(
            [p for p in paths if p.is_dir() or p.suffix.lower() in BOOK_EXTENSIONS],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )


class FilePickerScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    FilePickerScreen {
        align: center middle;
    }
    #file-picker-dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #file-picker-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #file-tree {
        height: 1fr;
        margin-bottom: 1;
    }
    #file-picker-buttons {
        align: center middle;
        height: 3;
    }
    #file-picker-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(self, start_path: str = "~") -> None:
        super().__init__()
        self._start = str(Path(start_path).expanduser().resolve())

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-dialog"):
            yield Label("Select a book file", id="file-picker-title")
            yield BookDirectoryTree(self._start, id="file-tree")
            with Horizontal(id="file-picker-buttons"):
                yield Button("Cancel [Esc]", variant="default", id="fp-cancel")

    def on_mount(self) -> None:
        self.query_one("#file-tree", BookDirectoryTree).focus()

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(str(event.path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fp-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmDeleteScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }
    #confirm-delete-dialog {
        width: 60;
        height: 9;
        background: $surface;
        border: solid $error;
        padding: 1 2;
    }
    #confirm-delete-msg {
        text-align: center;
        margin: 1 0;
    }
    #confirm-delete-buttons {
        align: center middle;
        height: 3;
    }
    #confirm-delete-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(self, book_title: str) -> None:
        super().__init__()
        self._book_title = book_title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-delete-dialog"):
            yield Label(
                f'Delete "{self._book_title}" from library?',
                id="confirm-delete-msg",
            )
            with Horizontal(id="confirm-delete-buttons"):
                yield Button("Delete (y)", variant="error", id="cd-yes")
                yield Button("Cancel (n)", variant="default", id="cd-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "cd-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class LibraryScreen(Screen):
    BINDINGS = [
        Binding("A", "add_book", "Add", priority=True),
        Binding("D", "delete_book", "Delete", priority=True),
        Binding("s", "cycle_sort", "Sort"),
        Binding("S", "toggle_search", "Search"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._sort_index = 0
        self._searching = False

    @property
    def bw(self) -> BookwormApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("", id="library-header")
        with Horizontal(id="search-bar"):
            yield Input(placeholder="Search books... (Esc to close)", id="search-input")
        yield DataTable(id="book-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#book-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Title", "Author", "Format", "Progress", "Last Read")
        self._refresh_books()
        table.focus()

    def on_screen_resume(self) -> None:
        self._refresh_books()
        if not self._searching:
            self.query_one("#book-table", DataTable).focus()

    def _refresh_books(self, search_query: str = "") -> None:
        table = self.query_one("#book-table", DataTable)
        table.clear()

        if search_query:
            books = self.bw.db.search_books(search_query)
        else:
            sort_key = SORT_OPTIONS[self._sort_index][0]
            books = self.bw.db.list_books(order_by=sort_key)

        for book in books:
            progress = self.bw.db.get_progress(book.id)
            pct = f"{progress.progress_pct:.0%}" if progress else "0%"
            last_read = ""
            if book.last_read_at:
                last_read = datetime.fromtimestamp(book.last_read_at).strftime(
                    "%Y-%m-%d"
                )
            table.add_row(
                book.title,
                book.author,
                book.format.upper(),
                pct,
                last_read,
                key=book.id,
            )

        sort_label = SORT_OPTIONS[self._sort_index][1]
        count = len(books)
        self.query_one("#library-header", Static).update(
            f" Bookworm Library  ({count} books)  Sort: {sort_label}"
        )

    # ── Search ──────────────────────────────────

    def action_toggle_search(self) -> None:
        if self._searching:
            self._hide_search()
        else:
            self._searching = True
            self.query_one("#search-bar").styles.display = "block"
            inp = self.query_one("#search-input", Input)
            inp.value = ""
            inp.focus()

    def _hide_search(self) -> None:
        self._searching = False
        self.query_one("#search-bar").styles.display = "none"
        self.query_one("#search-input", Input).value = ""
        self._refresh_books()
        self.query_one("#book-table", DataTable).focus()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._refresh_books(search_query=event.value)

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#book-table", DataTable).focus()

    def on_key(self, event) -> None:
        if self._searching and event.key == "escape":
            self._hide_search()
            event.stop()
            event.prevent_default()

    # ── Add Book ────────────────────────────────

    def action_add_book(self) -> None:
        self.app.push_screen(FilePickerScreen("~"), callback=self._on_file_picked)

    def _on_file_picked(self, result: str | None) -> None:
        if result:
            self._do_add_book(result)

    @work(thread=True)
    def _do_add_book(self, path_str: str) -> None:
        from bookworm.parsers.base import get_parser

        file_path = Path(path_str).expanduser().resolve()
        if not file_path.exists():
            self.app.call_from_thread(
                self.notify, f"File not found: {file_path}", severity="error"
            )
            return

        try:
            parser = get_parser(file_path)
            content = parser.parse(file_path)
            book = content.metadata
            book.added_at = time.time()
            self.app.call_from_thread(self._finish_add_book, book)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error adding book: {e}", severity="error"
            )

    def _finish_add_book(self, book) -> None:
        self.bw.db.add_book(book)
        self._refresh_books()
        self.notify(f"Added: {book.title}")

    # ── Delete Book ─────────────────────────────

    def action_delete_book(self) -> None:
        table = self.query_one("#book-table", DataTable)
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        book = self.bw.db.get_book(str(row_key))
        if not book:
            return
        self.app.push_screen(
            ConfirmDeleteScreen(book.title),
            callback=lambda confirmed: self._on_delete_confirmed(confirmed, book.id),
        )

    def _on_delete_confirmed(self, confirmed: bool | None, book_id: str) -> None:
        if not confirmed:
            return
            book = self.bw.db.get_book(book_id)
            title = book.title if book else book_id
            self.bw.db.remove_book(book_id)
            self._refresh_books()
            self.notify(f"Removed: {title}")

    # ── Open / Sort / Quit ──────────────────────

    @on(DataTable.RowSelected, "#book-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        book = self.bw.db.get_book(str(event.row_key.value))
        if book:
            file_path = Path(book.file_path)
            if not file_path.exists():
                self.notify(f"File not found: {file_path}", severity="error")
                return
            self.bw.open_book(book)

    def action_cycle_sort(self) -> None:
        self._sort_index = (self._sort_index + 1) % len(SORT_OPTIONS)
        search_val = self.query_one("#search-input", Input).value
        self._refresh_books(search_query=search_val)

    def action_quit_app(self) -> None:
        self.app.exit()
