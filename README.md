# Structura

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-arm64-brightgreen.svg)](https://support.apple.com/en-us/HT211814)
[![PySide6](https://img.shields.io/badge/PySide6-Qt6-orange.svg)](https://doc.qt.io/qtforpython/)

```text
███████╗████████╗██████╗ ██╗   ██╗ ██████╗████████╗██╗   ██╗██████╗  █████╗
██╔════╝╚══██╔══╝██╔══██╗██║   ██║██╔════╝╚══██╔══╝██║   ██║██╔══██╗██╔══██╗
███████╗   ██║   ██████╔╝██║   ██║██║        ██║   ██║   ██║██████╔╝███████║
╚════██║   ██║   ██╔══██╗██║   ██║██║        ██║   ██║   ██║██╔══██╗██╔══██║
███████║   ██║   ██║  ██║╚██████╔╝╚██████╗   ██║   ╚██████╔╝██║  ██║██║  ██║
╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝  ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
```

> **Native macOS file browser and folder analysis tool.**
> Scan a folder, explore its tree with sortable metadata, inspect extension distribution with charts, and optionally organize top-level media files into extension-based subfolders.

---

## Features

- **Recursive Tree View** — scan a root folder and browse the full directory tree with sortable columns: Title, File Type, Date Created, Date Modified, File Size, Frame Rate
- **Subtree Metrics** — total files, total size, and folder count for any selected node
- **Extension Analytics** — pie chart, top-extension bars, and a full extension table for the selected subtree
- **Media Organization** — move top-level images and videos into uppercase extension folders (`JPG`, `PNG`, `MOV`, `MP4`, etc.)
- **Hidden File Toggle** — include or exclude hidden files from both scans and previews
- **Safe Scanning** — unreadable paths and symlink loops surface as warnings instead of crashes
- **Video Frame Rate** — reads FPS metadata directly from QuickTime container atoms for `.mov`, `.mp4`, and `.m4v`
- **Apple Silicon Native** — arm64 build optimized for M1/M2/M3/M4 chips

---

## Installation

1. Download the latest `Structura.dmg` from [Releases](https://github.com/RazorBackRoar/Structura/releases)
2. Open the DMG and drag `Structura.app` to `/Applications`
3. First launch — right-click the app → **Open** to bypass Gatekeeper on the ad-hoc signed build

---

## Usage

1. **Open a folder** — click the folder picker or drag a folder onto the window
2. **Browse the tree** — click any node to see its subtree metrics and extension breakdown
3. **Organize** *(optional)* — click **Organize Top-Level** to sort images and videos into extension folders

---

## Development

### Requirements

- Python 3.14
- macOS 12.0+
- [uv](https://github.com/astral-sh/uv)

### Setup

```bash
git clone https://github.com/RazorBackRoar/Structura.git
cd Structura
uv sync
uv run python src/main.py
```

### Build

```bash
razorbuild Structura
# Output: dist/Structura.dmg
```

### Lint & Test

```bash
uv run ruff check .
uv run ty check src --python-version 3.14
uv run pytest tests/ -q
```

---

## Project Structure

```text
Structura/
├── src/
│   └── structura/
│       ├── main.py         # Entry point
│       ├── scanner.py      # Recursive directory indexer
│       ├── sorter.py       # Media organization logic
│       ├── analytics.py    # Extension distribution analysis
│       └── ui/             # PySide6 GUI components
├── assets/
│   └── Structura.icns
├── tests/
└── Structura.spec
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
Copyright © 2026 RazorBackRoar

<!-- razorcore:runtime:start -->
## Runtime Requirements

For users:
- Download the macOS `.dmg` or `.app` release. Python does not need to be installed.

For developers:
- Primary development/build target: Python 3.14 with `uv`.
- Source compatibility goal: Python 3.12-3.14 (best effort).
- Setup: `uv sync`
- Run: `uv run python src/main.py`
<!-- razorcore:runtime:end -->
