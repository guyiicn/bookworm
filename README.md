# Bookworm

A feature-rich terminal ebook reader with library management, multi-format support, and AI-powered translation — built with [Textual](https://github.com/Textualize/textual).

## Features

- **Multi-format support** — EPUB, PDF, DOCX, Markdown, TXT, MOBI
- **Library management** — import, search, sort, and delete books via a built-in file picker
- **Reading progress** — automatic chapter / page tracking, resume where you left off
- **Bookmarks** — mark any page, jump back to it later
- **Table of contents** — collapsible sidebar parsed from EPUB nav, PDF outlines, or headings
- **AI translation** — translate paragraphs on-the-fly via OpenAI, Claude, Qwen, GLM, OpenRouter, or local Ollama; results are cached in SQLite so you never pay twice
- **Bilingual export** — once a book is fully translated, export a side-by-side `.txt` file
- **Dual-page mode** — split the terminal into two columns for wider displays
- **Adjustable line spacing** — four levels (compact → extra-wide)

## Quick Start

Requires **Python ≥ 3.11** and [uv](https://github.com/astral-sh/uv).

```bash
# Clone & install
git clone https://github.com/guyiicn/bookworm.git
cd bookworm
uv sync

# Run
uv run bookworm            # open the library
uv run bookworm book.epub  # import & open a file directly
```

## Configuration

Copy `.env.example` to `.env` (in the project root, `~/.config/bookworm/`, or `~/`) and fill in the providers you want to use:

```bash
cp .env.example .env
```

Key variables:

| Variable | Description | Default |
|---|---|---|
| `BOOKWORM_TRANSLATE_PROVIDER` | Active provider: `openai` \| `claude` \| `qwen` \| `glm` \| `openrouter` \| `ollama` | `openai` |
| `BOOKWORM_TRANSLATE_TARGET_LANG` | Target language code (e.g. `zh-CN`, `ja`, `en`) | `zh-CN` |
| `<PROVIDER>_API_KEY` | API key for the chosen provider | — |
| `<PROVIDER>_BASE_URL` | Custom API endpoint (useful for proxies) | provider default |
| `<PROVIDER>_MODEL` | Model to use for translation | provider default |

Ollama requires no API key — just a running local instance.

## Keybindings

### Library

| Key | Action |
|-----|--------|
| `A` | Add book (file picker) |
| `D` | Delete selected book |
| `s` | Cycle sort order |
| `S` | Toggle search bar |
| `Enter` | Open selected book |
| `q` | Quit |

### Reader

| Key | Action |
|-----|--------|
| `←` / `→` | Previous / next page |
| `Space` | Next page |
| `,` / `.` | Previous / next chapter |
| `t` | Toggle table of contents |
| `m` | Add bookmark |
| `B` | Toggle bookmarks sidebar |
| `T` | Toggle translation mode |
| `E` | Export bilingual text |
| `=` / `-` | Increase / decrease line spacing |
| `D` | Toggle dual-page mode |
| `Esc` | Back to library |

## Project Structure

```
src/bookworm/
├── app.py              # Textual App entry point
├── config.py           # .env-based configuration
├── library/
│   ├── database.py     # SQLite: books, progress, bookmarks, translation cache
│   └── models.py       # Data classes (Book, Chapter, ReadingProgress, Bookmark)
├── parsers/
│   ├── base.py         # BaseParser ABC + format router
│   ├── epub_parser.py  # ebooklib
│   ├── pdf_parser.py   # PyMuPDF
│   ├── docx_parser.py  # python-docx
│   ├── markdown_parser.py
│   ├── txt_parser.py
│   └── mobi_parser.py
├── translation/
│   └── engine.py       # Batch translation with OpenAI-compatible API + caching
└── ui/
    ├── themes.py       # Textual CSS
    ├── screens/
    │   ├── library_screen.py
    │   └── reader_screen.py
    └── widgets/
```

## Development

```bash
uv sync --group dev
uv run pytest
```

## License

MIT