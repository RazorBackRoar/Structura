# Claude Code — Structura

See workspace policy: `/Users/home/Workspace/CLAUDE.md`

## Context load order
1. `/Users/home/Workspace/CLAUDE.md`
2. `/Users/home/Workspace/Apps/AGENTS.md`
3. `/Users/home/Workspace/Apps/Structura/AGENTS.md` ← nearest, wins on conflicts
4. Relevant `~/.skills/` guides

## Quick reference
- **Purpose:** Native macOS filesystem explorer — scans folders, visualises disk usage by extension, sorts/organises media files
- Entry: `uv run python src/main.py`
- Launch: `./run_preview.sh`
- Build: `razorbuild Structura` | Full release (with codesign): `./build.sh`
- Toolchain: `uv sync` → `uv run ruff check .` → `uv run ty check . --python-version 3.13`
- Tests: `uv run pytest tests/ -v` (headless: `QT_QPA_PLATFORM=offscreen uv run pytest tests/ -v`)
- razorcore: editable dep at `../.razorcore`
- **⚠️ Single-file constraint**: all app logic lives in `Structura.py` — do not split into modules
- **⚠️ No ffmpeg**: frame rate extracted from QuickTime atoms directly via `Structura.py`

## Module structure
- `Structura.py` — entire application runtime (~4,700 lines): UI, scanning, sorting, EXIF, workers
- `src/main.py` — thin entrypoint only (adds project root to `sys.path`, calls `Structura.main`)
- `tests/` — scan/snapshot behavior + build entrypoint wiring
- `assets/` — `Structura.icns` used by source app and packaged bundle
- `build.sh` — PyInstaller → ad-hoc codesign → DMG (release path)
- `Structura.spec` — PyInstaller spec (arm64, bundle ID `com.github.razorbackroar.structura`)
