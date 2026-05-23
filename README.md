# Structura

Structura is a macOS-style desktop file browser and folder analysis tool built with PySide6. It scans one root folder at a time, builds a recursive tree with sortable metadata, summarizes extension distribution for any selected subtree, and can optionally organize top-level media files into extension-based folders such as `MOV` and `PNG`.

The checked-in project is local-first and desktop-only. There is no server, no database, and no cloud dependency in the current repository.

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Platform Support](#platform-support)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Daily Development Workflow](#daily-development-workflow)
- [Using the App](#using-the-app)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Sorting Semantics](#sorting-semantics)
- [Environment Variables and Configuration](#environment-variables-and-configuration)
- [Testing](#testing)
- [Packaging and Distribution](#packaging-and-distribution)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Key Features

- Scan a single root folder and recursively index its directory tree in a background thread.
- Browse the tree in a dedicated left pane with sortable columns for `Title`, `File Type`, `Date Created`, `Date Modified`, `File Size`, and `Frame Rate`.
- View subtree-aware metrics for the current selection: total files, total size, and total folders.
- Filter extension analytics for the selected node and inspect distribution with a pie chart, legend, top-extension bars, and an extension table for larger result sets.
- Organize only top-level images and videos into uppercase extension folders such as `JPG`, `PNG`, `MOV`, and `MP4`.
- Toggle hidden-file inclusion for both scanning and sort previews.
- Skip junk files such as `.DS_Store`, `Thumbs.db`, `.Spotlight-V100`, and `.Trashes`.
- Detect unreadable paths and symlink loops and surface them as warnings instead of crashing.
- Read video frame rate metadata for `.mov`, `.mp4`, and `.m4v` directly from QuickTime container atoms.
- Package the app as a macOS `.app` bundle and `.dmg`.

## Tech Stack

| Area | Technology |
| --- | --- |
| Language | Python 3.14 |
| GUI framework | PySide6 / Qt |
| Main runtime | `Structura.py` |
| Source entrypoint | `src/main.py` |
| Desktop packaging | PyInstaller |
| macOS distribution | `.app` bundle + `.dmg` via `build.sh` |
| Testing | `pytest` and `unittest` |
| Linting | Ruff |
| Type checking | `ty` |
| License | MIT |

## Platform Support

- The checked-in packaging pipeline is macOS-specific.
- `Structura.spec` sets `LSMinimumSystemVersion` to `12.0`, so the packaged app targets macOS 12 or newer.
- Source execution depends on Python 3.14 and PySide6. It may run on other platforms supported by Qt, but this repository does not include Windows or Linux packaging artifacts.
- The UI and release workflow are clearly optimized for macOS behavior and appearance.

## Prerequisites

### Required for source development

- Python `3.14` or newer
- A virtual environment
- PySide6
- PyInstaller
- `pytest`
- Ruff
- `ty`

### Recommended tools

- `uv` for virtual environment and package management
- Homebrew on macOS for installing packaging utilities

### Required only for `.dmg` packaging

- `create-dmg`
- macOS `codesign` tool (included with macOS)

Install `create-dmg` with Homebrew if you plan to run `./build.sh`:

```bash
brew install create-dmg
```

## Getting Started

### 1. Clone the repository

If you already have a local checkout, skip this step.

```bash
git clone <your-repository-url> Structura
cd Structura
```

### 2. Create and activate a virtual environment

Recommended with `uv`:

```bash
uv venv .venv
source .venv/bin/activate
```

Fallback with the standard library:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

The repository's `pyproject.toml` declares the core runtime dependencies, but the active development workflow also uses `pytest` for tests.

```bash
uv pip install -U pyside6 pyinstaller ruff ty pytest
```

If you prefer `pip`:

```bash
python -m pip install -U pyside6 pyinstaller ruff ty pytest
```

### 4. Verify your Python version

```bash
python --version
```

Expected: Python `3.14.x` or newer.

### 5. Run the application from source

```bash
python src/main.py
```

`src/main.py` is intentionally thin. It adds the project root to `sys.path` and delegates to `Structura.main()`.

### 6. Run the test suite

```bash
python -m pytest tests/
```

### 7. Run lint checks

```bash
ruff check .
```

### 8. Launch a packaged app build (optional)

Fast local app bundle build:

```bash
pyinstaller Structura.spec
```

Full macOS packaging flow:

```bash
./build.sh
```

## Daily Development Workflow

Common commands used in this repository:

| Command | Purpose |
| --- | --- |
| `python src/main.py` | Run the app from source |
| `python -m pytest tests/` | Run the full test suite |
| `python -m pytest tests/test_scan_snapshot.py -v` | Run the scan/snapshot-focused tests |
| `python -m pytest tests/test_build_entrypoint.py -v` | Validate entrypoints and PyInstaller spec wiring |
| `ruff check .` | Run lint checks |
| `ruff format .` | Format the codebase |
| `ty check .` | Run static type analysis |
| `pip check` | Verify installed packages for dependency conflicts |
| `pyinstaller Structura.spec` | Build `dist/Structura.app` via the spec file |
| `pyinstaller --windowed Structura.spec` | Explicitly build the windowed app bundle |
| `rm -rf build dist` | Remove generated packaging artifacts |
| `./build.sh` | Build, ad-hoc sign, verify, and create a DMG |

## Using the App

### Basic scan workflow

1. Launch Structura.
2. Click `Choose Folder…` or drag a folder into the window.
3. Structura scans one root folder at a time in the background.
4. The left pane (`Contents`) shows the recursive tree.
5. The right pane (`Folder Analyzer`) updates based on the current selection.

### What you can inspect

- Total file count for the selected node
- Total byte size for the selected node
- Total folder count for the selected node
- Extension distribution for the selected node
- Sortable file metadata in the tree

### Sortable tree columns

The active file tree supports sorting by:

- `Title`
- `File Type`
- `Date Created`
- `Date Modified`
- `File Size`
- `Frame Rate`

Notes:

- `File Size` sorts numerically, not lexically.
- `Frame Rate` is available only for supported video files.
- Unsupported or unavailable metadata displays as `—`.

### Hidden files

The `Hidden On` / `Hidden Off` toggle affects:

- recursive scanning
- the analytics visible in the dashboard
- the root-level sort preview
- the actual media organization operation

### What "Organize Files" does

The sort action is intentionally conservative:

- It only considers files directly inside the loaded root folder.
- It never moves files inside nested folders.
- It only targets images and videos.
- It creates uppercase extension folders like `JPG`, `PNG`, `MOV`, and `MP4`.
- It leaves unrelated files and subfolders untouched.

Example:

```text
Before
root/
├── hero.mov
├── still.png
├── notes.txt
└── Nested/
    └── clip.mov

After
root/
├── MOV/
│   └── hero.mov
├── PNG/
│   └── still.png
├── notes.txt
└── Nested/
    └── clip.mov
```

## Project Structure

```text
.
├── AGENTS.md                     # Project-specific agent instructions
├── LICENSE                       # MIT license
├── README.md                     # Project documentation
├── Structura.py                  # Main application runtime and UI
├── Structura.spec                # PyInstaller build spec for Structura.app
├── build.sh                      # macOS build → ad-hoc sign → DMG pipeline
├── pyproject.toml                # Python metadata and tool configuration
├── assets/
│   ├── Structura.icns            # Application icon used by the bundle
│   └── Structura.iconset/        # Source iconset assets
├── src/
│   └── main.py                   # Thin source entrypoint
├── tests/
│   ├── test_build_entrypoint.py  # Entry/spec wiring tests
│   └── test_scan_snapshot.py     # Scan, sort, metadata, and UI behavior tests
├── build/                        # Generated PyInstaller build artifacts
└── dist/                         # Generated .app and .dmg outputs
```

Additional notes:

- `Structura.py` is the real application. This repository is intentionally simple and keeps the runtime in one file.
- `main()` currently instantiates `StructuraWindow`.
- Older UI classes such as `MainWindow` and `FileBrowserPane` still exist in `Structura.py`, but they are not the default runtime path.

## Architecture

### Runtime entry path

The active startup chain is:

```text
src/main.py
  -> Structura.main()
      -> QApplication setup
      -> Fusion style, fonts, palette, icon
      -> StructuraWindow()
```

`Structura.main()` is responsible for:

- creating the `QApplication`
- applying the app font and palette
- loading the `.icns` icon from `assets/Structura.icns`
- creating and showing `StructuraWindow`

### High-level data flow

```text
Choose or drop folder
  -> StructuraWindow._scan_path()
  -> ScanWorker.run()
  -> scan_folder()
  -> ScanSnapshot
  -> FolderTreePane.set_snapshot()
  -> AnalyzerDashboard.set_snapshot()
```

Sort flow:

```text
Click "Organize Files"
  -> AnalyzerDashboard.sort_requested
  -> StructuraWindow._sort_root_folder()
  -> SortWorker.run()
  -> _safe_move()
  -> rescan current root
```

### Core data objects

The app uses a small set of explicit data containers:

- `SortPreview`
  - counts root-level sortable extensions
  - tracks skipped folders, ignored files, and errors
- `SubtreeStats`
  - describes one folder or file node
  - stores extension counts, file totals, folder totals, and size totals
- `ScanSnapshot`
  - represents the result of one full scan
  - stores `tree_data`, root totals, warnings, and `stats_by_path`

`stats_by_path` is the key structure that makes the UI responsive after scanning. Once a scan completes, selecting a folder in the tree can immediately refresh the dashboard without rescanning the filesystem.

### UI composition

The active window is `StructuraWindow`, which is composed of:

- a menu bar
- a toolbar with the root-path pill, folder chooser, and hidden toggle
- a horizontal splitter
- `FolderTreePane` on the left
- `AnalyzerDashboard` on the right

#### `FolderTreePane`

Responsibilities:

- show the recursive folder tree
- display sortable metadata columns
- emit `path_selected` when the current selection changes
- lazily expand very large trees

Important details:

- Tree columns are configured centrally through `TREE_HEADERS`.
- Tree widths are configured through `TREE_COLUMN_WIDTHS`.
- The tree uses custom per-column sort keys via `TREE_SORT_ROLE`.
- `SortableTreeItem.__lt__` ensures sort behavior uses those stored sort keys instead of plain text.

#### `AnalyzerDashboard`

Responsibilities:

- render the current selection title and subtitle
- show metrics tiles for file count, size, and folder count
- rebuild the extension filter for the current node
- render the pie chart, legend, top-extension bars, and optional extension table
- expose the media organization controls

Important behaviors:

- The root selection is intentionally labeled `Folder Overview` to avoid repeating the loaded folder name in multiple places.
- The extension filter persists across selection changes unless explicitly reset.
- The sort preview is recalculated from the loaded root, not the currently selected nested node.

### Scan pipeline

The recursive scan is implemented in `scan_folder(root, include_hidden=True, progress_cb=None)`.

What it does:

- walks the directory tree recursively
- sorts entries with folders first, then files
- skips junk files defined in `JUNK_FILES`
- optionally skips hidden names beginning with `.`
- aggregates per-extension counts for each subtree
- records per-file size and per-folder totals
- builds `stats_by_path` entries for every scanned directory and file

Failure handling:

- unreadable paths become warnings
- permission errors are captured and shown in the UI
- unresolvable paths become warnings
- symlink loops are detected and skipped

Progress reporting:

- the scan worker emits progress every 50 indexed directories
- progress is shown in the dashboard empty/scanning state

### Lazy tree population

The tree is not rendered all at once for very large scans.

Instead:

- `_populate_tree_lazy()` populates only an initial budget of nodes
- remaining branches are represented by a lazy placeholder
- `_expand_lazy_placeholder()` expands the rest only when needed

This keeps the UI more responsive on large folder trees.

### Metadata and sortable columns

Each tree row is configured in three stages:

1. title styling
2. metadata extraction
3. metadata + tooltip + sort-role application

Tree metadata includes:

- `Date Created`
- `Date Modified`
- `File Size`
- `Frame Rate`

Behavior details:

- Date fields use filesystem timestamps.
- Size is formatted in Finder-style decimal units via `_human_size()`.
- Frame rate is currently extracted for `.mov`, `.mp4`, and `.m4v`.
- Unsupported file types show `—` for unavailable metadata.

### Frame-rate parsing

Structura does not shell out to external media tools for frame-rate display. Instead it parses QuickTime-family containers directly:

- `_iter_quicktime_atoms()`
- `_find_quicktime_atom()`
- `_quicktime_timescale()`
- `_quicktime_sample_timing()`
- `_quicktime_frame_rate()`

That parser result is cached with `@lru_cache(maxsize=2048)` and keyed by file path plus modification time.

### Root-level media organization

The sort system is intentionally separate from scanning:

- `collect_sortable_extensions()` previews what is eligible to move
- `SortWorker` performs the actual moves
- `_safe_move()` creates destination folders and resolves name collisions by appending `(1)`, `(2)`, and so on

The organization action is constrained on purpose:

- directories are never reorganized
- nested media files are never reorganized
- non-media files are ignored
- hidden-file behavior respects the current UI toggle

## Sorting Semantics

If you plan to change the sort behavior, these are the current rules:

| Rule | Current behavior |
| --- | --- |
| Scope | Root folder only |
| Eligible file types | Images and videos only |
| Media filter modes | `both`, `images`, `videos` |
| Destination names | Uppercase extension folder names such as `MOV` or `PNG` |
| Name collisions | Resolved by `_safe_move()` using `name(1).ext`, `name(2).ext`, etc. |
| Hidden files | Included or excluded based on the current toggle |
| Nested folders | Counted in scan metrics but never reorganized |

## Environment Variables and Configuration

The checked-in codebase does not require any project-specific environment variables.

Current state:

- no `.env`
- no `.env.example`
- no secrets file
- no database connection settings
- no API keys

Configuration currently lives in code and packaging files:

- `pyproject.toml`
- `Structura.spec`
- `build.sh`

macOS runtime note:

- if you scan protected locations such as Desktop, Documents, Downloads, or external volumes, macOS may prompt for filesystem access

## Testing

Run the full test suite:

```bash
python -m pytest tests/
```

Run a specific file:

```bash
python -m pytest tests/test_scan_snapshot.py -v
python -m pytest tests/test_build_entrypoint.py -v
```

Run a single test:

```bash
python -m pytest tests/test_scan_snapshot.py::DashboardBehaviorTest::test_folder_tree_pane_sorts_by_size_without_duplicate_root_row -v
```

### What the test suite covers

- human-readable size formatting
- extension color mapping
- unknown file icon fallback behavior
- QuickTime frame-rate parsing
- recursive scan totals
- hidden-file inclusion/exclusion
- subtree stats aggregation
- root-only media sort behavior
- tree header and sorting behavior
- extension filter persistence
- PyInstaller entrypoint correctness
- `src/main.py` delegation to `Structura.main()`

### Headless Qt testing

The tests set `QT_QPA_PLATFORM=offscreen` so they can run without a visible desktop session. This is useful for CI and local terminal-only execution.

## Packaging and Distribution

### Fast local bundle build

```bash
pyinstaller Structura.spec
```

This produces a macOS `.app` bundle in `dist/`.

### Full macOS package build

```bash
./build.sh
```

`build.sh` performs the following steps:

1. builds `Structura.app` with PyInstaller
2. signs the app with an ad-hoc signature
3. verifies the signature
4. creates `Structura.dmg`

Expected outputs:

- `dist/Structura.app`
- `dist/Structura.dmg`

### What `Structura.spec` configures

- source entry script: `src/main.py`
- icon asset: `assets/Structura.icns`
- bundle identifier: `com.github.razorbackroar.structura`
- minimum macOS version: `12.0`
- windowed build with `console=False`

### Signing

The scripted build signs ad-hoc (`Signing identity: -`, RazorBackRoar).

### Installing a prebuilt app

If you already have a `Structura.dmg`:

1. Open the DMG.
2. Drag `Structura.app` into `/Applications`.
3. Launch the app.

If Gatekeeper blocks the first launch because the app is not notarized:

1. Right-click `Structura.app`
2. Choose `Open`
3. Confirm the prompt

## Troubleshooting

### Python version is too old

Symptom:

- install fails
- lint tools fail
- type checking behaves unexpectedly

Fix:

```bash
python --version
```

Use Python `3.14+`.

### `ModuleNotFoundError` or missing PySide6

Fix:

```bash
source .venv/bin/activate
uv pip install -U pyside6 pyinstaller ruff ty pytest
```

### `create-dmg: command not found`

`build.sh` depends on `create-dmg`.

Fix:

```bash
brew install create-dmg
```

### PyInstaller build issues

Try a clean rebuild:

```bash
rm -rf build dist
pyinstaller --clean --noconfirm Structura.spec
```

### App icon missing in the built bundle

Verify the icon exists:

```bash
ls assets/Structura.icns
```

The PyInstaller spec expects that exact file.

### App opens but macOS blocks it

The app is ad-hoc signed, not notarized.

Recommended first try:

1. Right-click the app
2. Choose `Open`

If you are working only with a local build, you can also inspect or clear quarantine attributes as appropriate for your environment.

### Qt display or plugin issues in headless contexts

For test-only runs, the suite already sets the platform to `offscreen`.

If you are debugging Qt behavior manually in a headless session, you can force the same mode:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/
```

### Scan warnings appear for some folders

This is usually expected for:

- permission-restricted directories
- broken symlinks
- symlink loops
- files that disappear during scanning

Structura records these as warnings and continues instead of aborting the scan.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
