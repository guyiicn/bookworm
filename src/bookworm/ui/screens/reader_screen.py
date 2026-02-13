from __future__ import annotations

import asyncio
import textwrap
import time
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, ListItem, ListView, Static

from bookworm.library.models import (
    Book,
    BookContent,
    Bookmark,
    Chapter,
    ReadingProgress,
)
from bookworm.parsers.base import get_parser

if TYPE_CHECKING:
    from bookworm.app import BookwormApp


def _display_width(text: str) -> int:
    """Return display width accounting for CJK double-width characters."""
    return sum(
        2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1 for ch in text
    )


def _wrap_cjk(text: str, width: int) -> list[str]:
    """Wrap text to display width, handling CJK double-width characters."""
    if not text.strip():
        return [""]
    # Fast path: pure ASCII — use textwrap for proper word breaking
    if text.isascii():
        return textwrap.wrap(text, width=width) or [""]
    # CJK / mixed path: wrap by display width
    lines: list[str] = []
    current: list[str] = []
    current_w = 0
    for ch in text:
        cw = 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
        if current_w + cw > width and current:
            lines.append("".join(current))
            current = []
            current_w = 0
            if ch == " ":
                continue  # skip leading space on new line
        current.append(ch)
        current_w += cw
    if current:
        lines.append("".join(current))
    return lines or [""]


def _pad_to_width(text: str, width: int) -> str:
    """Pad text with spaces to reach target display width."""
    dw = _display_width(text)
    return text + " " * max(0, width - dw)


class ReaderScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("left", "prev_page", "\u2190"),
        Binding("right", "next_page", "\u2192"),
        Binding("space", "next_page", "Next", show=False),
        Binding("comma", "prev_chapter", "<Ch"),
        Binding("full_stop", "next_chapter", "Ch>"),
        Binding("t", "toggle_toc", "TOC"),
        Binding("m", "add_bookmark", "Mark"),
        Binding("B", "toggle_bookmarks", "Marks"),
        Binding("T", "toggle_translate", "Trans"),
        Binding("E", "export_bilingual", "Export"),
        Binding("=", "increase_spacing", "+Sp"),
        Binding("minus", "decrease_spacing", "-Sp"),
        Binding("D", "toggle_dual", "Dual"),
    ]

    def __init__(self, book: Book) -> None:
        super().__init__()
        self._book = book
        self._content: BookContent | None = None
        self._pages: list[list[str]] = []
        self._page_para_ranges: list[tuple[int, int]] = []
        self._chapter_idx = 0
        self._page_idx = 0
        self._dual_mode = False
        self._line_spacing = 1
        self._loaded = False
        self._translate_mode = False

    @property
    def bw(self) -> BookwormApp:
        return self.app  # type: ignore[return-value]

    @property
    def current_chapter(self) -> Chapter | None:
        if self._content and 0 <= self._chapter_idx < len(self._content.chapters):
            return self._content.chapters[self._chapter_idx]
        return None

    def _all_paragraphs(self) -> list[str]:
        if not self._content:
            return []
        result: list[str] = []
        for ch in self._content.chapters:
            result.extend(ch.paragraphs)
        return result

    def _total_paragraph_count(self) -> int:
        if not self._content:
            return 0
        return sum(len(ch.paragraphs) for ch in self._content.chapters)

    def _translated_count(self) -> int:
        if not self._content:
            return 0
        return self.bw.translator.count_translated(self._all_paragraphs())

    def compose(self) -> ComposeResult:
        yield Static("", id="reader-header")
        with Horizontal(id="reader-body"):
            with Vertical(id="toc-sidebar"):
                yield Static("Table of Contents", id="toc-title")
                yield ListView(id="toc-list")
            yield Static("Loading...", id="content-text")
            with Vertical(id="bookmark-sidebar"):
                yield Static("Bookmarks", id="bookmark-title")
                yield ListView(id="bookmark-list")
        yield Footer()

    def on_mount(self) -> None:
        self._line_spacing = self.bw.config.default_line_spacing
        self._dual_mode = self.bw.config.default_dual_page
        self._load_book()

    @work(thread=True)
    def _load_book(self) -> None:
        file_path = Path(self._book.file_path)
        try:
            parser = get_parser(file_path)
            content = parser.parse(file_path)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Error loading book: {e}", severity="error"
            )
            return

        self._content = content
        self.app.call_from_thread(self._after_load)

    def _after_load(self) -> None:
        """Restore reading progress and render. Must run on main thread (DB + UI)."""
        if not self._content:
            return

        progress = self.bw.db.get_progress(self._book.id)
        if progress:
            self._chapter_idx = min(
                progress.chapter_index, len(self._content.chapters) - 1
            )
            self._page_idx = progress.scroll_offset
        else:
            self._chapter_idx = 0
            self._page_idx = 0

        self.bw.db.update_last_read(self._book.id)
        self._populate_toc()
        self._loaded = True
        self._reflow_and_render()

    # ── Pagination Engine ──────────────────────────

    def _reflow_and_render(self) -> None:
        if not self._loaded or not self._content:
            return
        self._reflow()
        self._page_idx = max(0, min(self._page_idx, len(self._pages) - 1))
        if self._dual_mode and self._page_idx % 2 != 0:
            self._page_idx = max(0, self._page_idx - 1)
        self._render_page()
        self._update_header()

    def _get_content_dimensions(self) -> tuple[int, int]:
        try:
            widget = self.query_one("#content-text", Static)
            w = widget.size.width - 4
            h = widget.size.height
            if w < 10 or h < 3:
                return 72, 20
            return w, h
        except Exception:
            return 72, 20

    def _reflow(self) -> None:
        chapter = self.current_chapter
        if not chapter:
            self._pages = [["(empty)"]]
            self._page_para_ranges = [(0, 0)]
            return

        content_w, content_h = self._get_content_dimensions()

        if self._dual_mode:
            page_width = max(20, (content_w - 3) // 2)
        else:
            page_width = max(20, content_w)

        page_height = max(3, content_h)
        all_lines, line_to_para = self._wrap_chapter(chapter, page_width)

        self._pages = []
        self._page_para_ranges = []
        for i in range(0, len(all_lines), page_height):
            page_lines = all_lines[i : i + page_height]
            self._pages.append(page_lines)
            start_line = i
            end_line = min(i + page_height - 1, len(line_to_para) - 1)
            if start_line < len(line_to_para) and end_line >= 0:
                self._page_para_ranges.append(
                    (line_to_para[start_line], line_to_para[max(0, end_line)])
                )
            else:
                self._page_para_ranges.append((0, 0))

        if not self._pages:
            self._pages = [["(empty)"]]
            self._page_para_ranges = [(0, 0)]

    def _wrap_chapter(
        self, chapter: Chapter, width: int
    ) -> tuple[list[str], list[int]]:
        lines: list[str] = []
        line_to_para: list[int] = []
        translator = self.bw.translator

        for i, para in enumerate(chapter.paragraphs):
            wrapped = _wrap_cjk(para, width)
            lines.extend(wrapped)
            line_to_para.extend([i] * len(wrapped))

            if self._translate_mode:
                cached = translator.get_cached(para)
                if cached:
                    trans_wrapped = _wrap_cjk(f"  ▸ {cached}", width)
                    lines.extend(trans_wrapped)
                    line_to_para.extend([i] * len(trans_wrapped))

            if i < len(chapter.paragraphs) - 1:
                spacing_lines = [""] * self._line_spacing
                lines.extend(spacing_lines)
                line_to_para.extend([i] * self._line_spacing)

        return lines, line_to_para

    def _render_page(self) -> None:
        if not self._pages:
            return

        content_w, content_h = self._get_content_dimensions()
        content_widget = self.query_one("#content-text", Static)

        if self._dual_mode:
            page_width = max(20, (content_w - 3) // 2)

            left_page = (
                self._pages[self._page_idx] if self._page_idx < len(self._pages) else []
            )
            right_idx = self._page_idx + 1
            right_page = self._pages[right_idx] if right_idx < len(self._pages) else []

            combined: list[str] = []
            for j in range(content_h):
                left = left_page[j] if j < len(left_page) else ""
                right = right_page[j] if j < len(right_page) else ""
                combined.append(f"{_pad_to_width(left, page_width)} \u2502 {right}")

            content_widget.update("\n".join(combined))
        else:
            page = (
                self._pages[self._page_idx]
                if self._page_idx < len(self._pages)
                else [""]
            )
            padded = list(page) + [""] * max(0, content_h - len(page))
            content_widget.update("\n".join(padded))

    def _update_header(self) -> None:
        if not self._content:
            return

        chapter = self.current_chapter
        ch_name = chapter.title if chapter else "?"
        total_ch = len(self._content.chapters)
        ch_num = self._chapter_idx + 1
        total_pages = len(self._pages)

        if self._dual_mode:
            page_display = (
                f"{self._page_idx + 1}-"
                f"{min(self._page_idx + 2, total_pages)}/{total_pages}"
            )
        else:
            page_display = f"{self._page_idx + 1}/{total_pages}"

        pct = (self._chapter_idx / total_ch) if total_ch > 0 else 0.0
        if total_pages > 0:
            pct += (self._page_idx + 1) / total_pages / total_ch

        spacing_label = ["Compact", "Normal", "Wide", "X-Wide"][self._line_spacing]
        parts = [
            f" {self._book.title}",
            f"Ch {ch_num}/{total_ch}: {ch_name}",
            f"P {page_display}",
            f"{pct:.0%}",
            spacing_label,
        ]

        if self._dual_mode:
            parts.append("DUAL")

        if self._translate_mode:
            total_p = self._total_paragraph_count()
            done_p = self._translated_count()
            parts.append(
                f"Trans {done_p}/{total_p} ({done_p * 100 // max(1, total_p)}%)"
            )

        header = "  \u2502  ".join(parts)
        self.query_one("#reader-header", Static).update(header)

    # ── Page Navigation ────────────────────────────

    def action_next_page(self) -> None:
        step = 2 if self._dual_mode else 1
        new_idx = self._page_idx + step
        if new_idx < len(self._pages):
            self._page_idx = new_idx
            self._render_page()
            self._update_header()
            self._save_progress()
            if self._translate_mode:
                self._translate_current_and_prefetch()
        elif self._content and self._chapter_idx < len(self._content.chapters) - 1:
            self._chapter_idx += 1
            self._page_idx = 0
            self._reflow_and_render()
            self._save_progress()
            if self._translate_mode:
                self._translate_current_and_prefetch()

    def action_prev_page(self) -> None:
        step = 2 if self._dual_mode else 1
        new_idx = self._page_idx - step
        if new_idx >= 0:
            self._page_idx = new_idx
            self._render_page()
            self._update_header()
            self._save_progress()
        elif self._chapter_idx > 0:
            self._chapter_idx -= 1
            self._reflow()
            last = max(0, len(self._pages) - 1)
            if self._dual_mode and last % 2 != 0:
                last = max(0, last - 1)
            self._page_idx = last
            self._render_page()
            self._update_header()
            self._save_progress()

    def action_next_chapter(self) -> None:
        if self._content and self._chapter_idx < len(self._content.chapters) - 1:
            self._chapter_idx += 1
            self._page_idx = 0
            self._reflow_and_render()
            self._save_progress()
            if self._translate_mode:
                self._translate_current_and_prefetch()

    def action_prev_chapter(self) -> None:
        if self._chapter_idx > 0:
            self._chapter_idx -= 1
            self._page_idx = 0
            self._reflow_and_render()
            self._save_progress()

    def _save_progress(self) -> None:
        if not self._content:
            return

        total_ch = len(self._content.chapters)
        total_pages = len(self._pages)
        page_pct = (self._page_idx + 1) / total_pages if total_pages > 0 else 0.0
        ch_pct = (self._chapter_idx + page_pct) / total_ch if total_ch > 0 else 0.0

        progress = ReadingProgress(
            book_id=self._book.id,
            chapter_index=self._chapter_idx,
            scroll_offset=self._page_idx,
            progress_pct=ch_pct,
            updated_at=time.time(),
        )
        self.bw.db.save_progress(progress)

    # ── TOC & Bookmarks ───────────────────────────

    def _populate_toc(self) -> None:
        if not self._content:
            return
        toc_list = self.query_one("#toc-list", ListView)
        toc_list.clear()
        for ch_idx, ch_title in self._content.toc:
            item = ListItem(Static(ch_title), classes="toc-item")
            item.data = ch_idx  # type: ignore[attr-defined]
            toc_list.append(item)

    def action_toggle_toc(self) -> None:
        sidebar = self.query_one("#toc-sidebar")
        sidebar.toggle_class("visible")
        if sidebar.has_class("visible"):
            self._reflow_and_render()

    def action_toggle_bookmarks(self) -> None:
        sidebar = self.query_one("#bookmark-sidebar")
        sidebar.toggle_class("visible")
        if sidebar.has_class("visible"):
            self._refresh_bookmarks()
            self._reflow_and_render()

    def _refresh_bookmarks(self) -> None:
        bm_list = self.query_one("#bookmark-list", ListView)
        bm_list.clear()
        bookmarks = self.bw.db.list_bookmarks(self._book.id)
        for bm in bookmarks:
            label = bm.label or f"Ch {bm.chapter_index + 1}, P{bm.scroll_offset + 1}"
            item = ListItem(Static(label), classes="bookmark-item")
            item.data = bm  # type: ignore[attr-defined]
            bm_list.append(item)

    @on(ListView.Selected, "#toc-list")
    def on_toc_selected(self, event: ListView.Selected) -> None:
        ch_idx = getattr(event.item, "data", None)
        if ch_idx is not None:
            self._chapter_idx = ch_idx
            self._page_idx = 0
            self._reflow_and_render()
            self._save_progress()

    @on(ListView.Selected, "#bookmark-list")
    def on_bookmark_selected(self, event: ListView.Selected) -> None:
        bm: Bookmark | None = getattr(event.item, "data", None)
        if bm is not None:
            self._chapter_idx = bm.chapter_index
            self._page_idx = bm.scroll_offset
            self._reflow_and_render()
            self._save_progress()

    def action_add_bookmark(self) -> None:
        bm = Bookmark(
            id=Bookmark.make_id(self._book.id, self._chapter_idx, self._page_idx),
            book_id=self._book.id,
            chapter_index=self._chapter_idx,
            scroll_offset=self._page_idx,
            label="",
            created_at=time.time(),
        )
        self.bw.db.add_bookmark(bm)
        self._update_header()
        chapter = self.current_chapter
        ch_name = chapter.title if chapter else f"Ch {self._chapter_idx + 1}"
        self.notify(f"Bookmark: {ch_name} P{self._page_idx + 1}")

    # ── Translation Mode ──────────────────────────

    def _check_translator(self) -> bool:
        if not self.bw.translator.is_configured:
            p = self.bw.translator.provider
            name = p.name if p else self.bw.config.translate_provider
            self.notify(
                f"Provider [{name}] not configured. Set API key in .env",
                severity="error",
            )
            return False
        return True

    def action_toggle_translate(self) -> None:
        if not self._check_translator():
            return

        if self._translate_mode:
            self._translate_mode = False
            self.bw.translator.cancel()
            self._reflow_and_render()
            self.notify("Translation mode OFF")
            return

        self._translate_mode = True
        self.notify("Translation mode ON")

        has_gap = self._has_untranslated_before_current()
        if has_gap:
            self._chapter_idx = 0
            self._page_idx = 0
            self._reflow_and_render()
            self._save_progress()
            self.notify("Jumped to start \u2014 untranslated content ahead")

        self.bw.translator.reset_cancel()
        self._translate_current_and_prefetch()

    def _has_untranslated_before_current(self) -> bool:
        if not self._content:
            return False
        translator = self.bw.translator
        for ci in range(self._chapter_idx):
            for para in self._content.chapters[ci].paragraphs:
                if not translator.is_translated(para):
                    return True
        ch = self._content.chapters[self._chapter_idx]
        current_para_end = 0
        if self._page_idx < len(self._page_para_ranges):
            current_para_end = self._page_para_ranges[self._page_idx][0]
        for pi in range(current_para_end):
            if not translator.is_translated(ch.paragraphs[pi]):
                return True
        return False

    def _get_page_paragraphs(self, page_idx: int) -> list[str]:
        chapter = self.current_chapter
        if not chapter or page_idx >= len(self._page_para_ranges):
            return []
        start, end = self._page_para_ranges[page_idx]
        return chapter.paragraphs[start : end + 1]

    def _translate_current_and_prefetch(self) -> None:
        if not self._translate_mode:
            return
        self._do_translate_pages()

    @work(thread=False, exclusive=True)
    async def _do_translate_pages(self) -> None:
        try:
            pages_to_translate = [self._page_idx]
            for offset in range(1, 3):
                nxt = self._page_idx + offset
                if nxt < len(self._pages):
                    pages_to_translate.append(nxt)

            tasks = []
            for pidx in pages_to_translate:
                paras = self._get_page_paragraphs(pidx)
                if paras:
                    tasks.append(self.bw.translator.translate_batch(paras))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        self.notify(f"Translation error: {r}", severity="error")

            self._reflow_and_render()
        except asyncio.CancelledError:
            pass

    def action_export_bilingual(self) -> None:
        if not self._content:
            return

        total = self._total_paragraph_count()
        done = self._translated_count()

        if done < total:
            self.notify(
                f"Translation incomplete: {done}/{total} ({done * 100 // max(1, total)}%)",
                severity="warning",
            )
            return

        self._do_export()

    def _do_export(self) -> None:
        if not self._content:
            return

        translator = self.bw.translator
        original_path = Path(self._book.file_path)
        export_path = original_path.parent / f"{original_path.stem}_bilingual.txt"

        parts: list[str] = []
        for ch in self._content.chapters:
            parts.append(f"{'=' * 60}")
            parts.append(ch.title)
            parts.append(f"{'=' * 60}\n")
            for para in ch.paragraphs:
                parts.append(para)
                cached = translator.get_cached(para)
                if cached:
                    parts.append(f"  \u25b8 {cached}")
                parts.append("")

        export_path.write_text("\n".join(parts), encoding="utf-8")
        self.notify(f"Exported: {export_path.name}")

    # ── Spacing & Dual ─────────────────────────────

    def action_increase_spacing(self) -> None:
        if self._line_spacing < 3:
            self._line_spacing += 1
            self._reflow_and_render()

    def action_decrease_spacing(self) -> None:
        if self._line_spacing > 0:
            self._line_spacing -= 1
            self._reflow_and_render()

    def action_toggle_dual(self) -> None:
        self._dual_mode = not self._dual_mode
        self._reflow_and_render()

    # ── Navigation & Resize ────────────────────────

    def action_go_back(self) -> None:
        self._save_progress()
        self.app.pop_screen()

    def on_resize(self) -> None:
        self._reflow_and_render()
