# Structura AGENTS

**Package:** `structura`
**Version:** 0.1.0

Use this file with `/Users/home/Workspace/Apps/AGENTS.md`. It only records Structura-specific context.

## Purpose And Entry Points

- Main app: `Structura.py` (single-file runtime, ~4,700 lines — intentional, do not split)
- Source entrypoint: `src/main.py` (adds project root to `sys.path`, delegates to `Structura.main`)
- Run locally: `uv run python src/main.py`
- Build through workspace wrappers: `razorbuild Structura`
- Full release build (code signing): `./build.sh`

## Non-Obvious Rules

- `build.sh` is the primary release build path — it handles ad-hoc code signing in addition to
  the PyInstaller bundle. `razorbuild Structura` runs the simpler universal wrapper.
- `build.sh` has its own `create-dmg` call. DMG settings must stay in sync with the locked
  values in `.razorcore/universal-build.sh`: `600×350, icon 100, (175,150), (425,150)`.
- All application logic lives in `Structura.py` at the repo root — **do not split it into modules**.
  `src/main.py` is only a thin path-fixing entrypoint.
- Frame rate is extracted from QuickTime atoms directly — no ffmpeg dependency.
- `QT_QPA_PLATFORM=offscreen` is required for headless test runs (no display available).
- `razorcore` is an editable dep at `../.razorcore`. Import it for shared utilities rather than
  duplicating patterns already in the library.

## Verification

Baseline:

```bash
uv run ruff check .
uv run ty check . --python-version 3.13
uv run pytest tests/ -q
```

Add focused checks when relevant:

- Scan/snapshot behavior: `uv run pytest tests/test_scan_snapshot.py -q`
- Build entrypoint wiring: `uv run pytest tests/test_build_entrypoint.py -q`
- Headless Qt: `QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q`
- UI or end-to-end flow: `uv run python src/main.py`

## CI Limitations

CI proves lint, type safety, and unit test correctness. It does NOT prove the app launches
successfully, the packaged bundle includes all runtime assets, or the DMG layout is correct.

## Release Readiness Checklist

Before tagging a release, verify all of the following:
- [ ] `uv run ruff check .` passes with no errors
- [ ] `uv run ty check . --python-version 3.13` passes with no errors
- [ ] `uv run pytest tests/ -q` passes with no failures
- [ ] App launches locally from a clean `uv sync`
- [ ] At least one core user flow exercised manually end-to-end
- [ ] `pyproject.toml` version matches README/display text

### What CI Does Not Prove
> Green CI is necessary but not sufficient for a safe release.
> macOS code signing, DMG layout, and filesystem permission edge cases require manual verification.
