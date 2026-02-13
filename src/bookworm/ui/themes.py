"""Textual CSS themes for bookworm."""

APP_CSS = """
/* ── Global ────────────────────────────────── */
Screen {
    background: $surface;
}

/* ── Library Screen ────────────────────────── */
#library-header {
    dock: top;
    height: 3;
    padding: 1 2;
    background: $primary;
    color: $text;
    text-style: bold;
}

#search-bar {
    dock: top;
    height: 3;
    padding: 0 2;
    background: $surface-darken-1;
    display: none;
}

#search-input {
    width: 100%;
}

#book-table {
    height: 1fr;
}

/* ── Reader Screen ─────────────────────────── */
#reader-header {
    dock: top;
    height: 1;
    background: $primary;
    color: $text;
    padding: 0 2;
    text-style: bold;
}

#reader-body {
    height: 1fr;
}

#toc-sidebar {
    width: 30;
    dock: left;
    display: none;
    background: $surface-darken-1;
    border-right: solid $primary;
}

#toc-sidebar.visible {
    display: block;
}

#toc-list {
    height: 1fr;
}

#toc-title {
    padding: 1 1;
    text-style: bold;
    background: $primary-darken-1;
    color: $text;
    text-align: center;
    height: 3;
}

#bookmark-sidebar {
    width: 32;
    dock: right;
    display: none;
    background: $surface-darken-1;
    border-left: solid $primary;
}

#bookmark-sidebar.visible {
    display: block;
}

#bookmark-title {
    padding: 1 1;
    text-style: bold;
    background: $primary-darken-1;
    color: $text;
    text-align: center;
    height: 3;
}

#bookmark-list {
    height: 1fr;
}

#content-text {
    height: 1fr;
    padding: 1 4;
    overflow: hidden;
}



/* ── Translated text ───────────────────────── */
.translated {
    color: $secondary;
    text-style: italic;
}

.original {
    color: $text;
}

.para-spacing-0 {
    margin: 0 0;
}

.para-spacing-1 {
    margin: 1 0;
}

.para-spacing-2 {
    margin: 2 0;
}

.para-spacing-3 {
    margin: 3 0;
}

/* ── Confirm dialog ────────────────────────── */
#confirm-dialog {
    align: center middle;
    width: 50;
    height: 10;
    background: $surface;
    border: solid $primary;
    padding: 1 2;
}

#confirm-dialog Static {
    text-align: center;
    margin: 1 0;
}

#confirm-buttons {
    align: center middle;
    height: 3;
}

#confirm-buttons Button {
    margin: 0 2;
}

/* ── Loading indicator ─────────────────────── */
.loading-text {
    color: $warning;
    text-style: italic;
}

/* ── List items ────────────────────────────── */
.toc-item {
    padding: 0 1;
    height: 1;
}

.toc-item:hover {
    background: $primary-darken-1;
}

.bookmark-item {
    padding: 0 1;
    height: 2;
}

.bookmark-item:hover {
    background: $primary-darken-1;
}
"""
