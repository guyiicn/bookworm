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

---

## Environment Setup

### Linux (Ubuntu / Debian)

```bash
# 1. Install system dependencies
sudo apt update
sudo apt install -y git python3.11 python3.11-venv python3.11-dev \
    build-essential libffi-dev libssl-dev

# 2. Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or restart your terminal

# 3. Clone the project
git clone https://github.com/guyiicn/bookworm.git
cd bookworm

# 4. Install dependencies (uv will automatically use Python 3.11)
uv sync

# 5. (Optional) Set up translation
cp .env.example .env
nano .env  # fill in your API keys

# 6. Run
uv run bookworm
```

> **Arch Linux**: replace step 1 with `sudo pacman -S git python base-devel`
>
> **Fedora**: replace step 1 with `sudo dnf install git python3.11 python3.11-devel gcc libffi-devel openssl-devel`
>
> **Tip**: If your distro only ships Python 3.12+, `uv` will auto-download Python 3.11 for you — no manual install needed.

### Windows

#### Option A — PowerShell (recommended)

```powershell
# 1. Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Restart your terminal after install

# 2. Clone the project
git clone https://github.com/guyiicn/bookworm.git
cd bookworm

# 3. Install dependencies (uv auto-downloads Python 3.11 if not found)
uv sync

# 4. (Optional) Set up translation
copy .env.example .env
notepad .env  # fill in your API keys

# 5. Run
uv run bookworm
```

#### Option B — WSL2 (Windows Subsystem for Linux)

If you prefer a native terminal experience (better Unicode rendering for CJK books):

```powershell
# In PowerShell (Admin), enable WSL and install Ubuntu
wsl --install
# Restart, then open "Ubuntu" from Start menu
```

Then follow the **Linux** instructions above inside WSL.

#### Windows Prerequisites

| Requirement | How to get it |
|---|---|
| **Git** | [git-scm.com](https://git-scm.com/download/win) or `winget install Git.Git` |
| **Windows Terminal** | Pre-installed on Win 11; [get it for Win 10](https://aka.ms/terminal) — much better than `cmd.exe` for TUI apps |
| **Python 3.11+** | Optional — `uv` can download it for you. Or get it from [python.org](https://www.python.org/downloads/) |

> **Note**: Run bookworm in **Windows Terminal** (not the legacy `cmd.exe` or old PowerShell window) for proper color and Unicode support.

---

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