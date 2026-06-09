# Structura AGENTS

**Package:** `structura`
**Version:** 0.1.0

Use this file with `../AGENTS.md`. It only records Structura-specific context.

## Purpose And Entry Points

- Main app: `Structura.py` (single-file runtime, ~6,100 lines — intentional, do not split)
- Source entrypoint: `src/structura/main.py` (adds project root to `sys.path`, delegates to `Structura.main`)
- Run locally: `uv run python src/structura/main.py`
- Build through workspace wrappers: `razorbuild Structura`
- Full release build (code signing): `./build.sh`

## Design Rationale: Single-File Architecture

`Structura.py` is a single ~6,100-line file by deliberate choice — not by accident or neglect.

**Why:**
- Structura's components (scanner, tree model, Qt delegate, paint routines, context menu,
  toolbar, status bar) are tightly coupled by design. Splitting them into modules would require
  threading the same 3–4 objects through every call boundary, producing more complexity than
  it eliminates.
- There is no reuse surface. No other app imports from Structura. The standard benefit of
  modules (enabling reuse, limiting blast radius of changes) simply does not apply here.
- Disk-usage UI logic has high spatial locality: changing how a node is *painted* almost always
  requires a matching change to how it is *selected*, *measured*, or *labeled*. One file means
  one scroll, not four open tabs.

**The boundary rule:** If you add something genuinely decoupled — a standalone utility with no
Qt dependency (e.g., a pure data transformer) — extract it into `src/structura/`. Everything
with Qt coupling stays in `Structura.py`. When in doubt, keep it in the single file.

## Non-Obvious Rules

- `build.sh` is the primary release build path — it delegates to `../.razorcore/universal-build.sh`
  which handles ad-hoc code signing, PyInstaller bundling, and the shared locked DMG layout.
  `razorbuild Structura` runs the same path. Do **not** reintroduce a local `create-dmg` call.
- DMG layout is the single shared config in `../.razorcore/dmg-settings.py` (500×360, icon 128).
- All application logic lives in `Structura.py` at the repo root — **do not split it into modules**.
  `src/structura/main.py` is only a thin path-fixing entrypoint.
- Frame rate is extracted from QuickTime atoms directly — no ffmpeg dependency.
- `QT_QPA_PLATFORM=offscreen` is required for headless test runs (no display available).
- `razorcore` is an editable dep at `../.razorcore`. Import it for shared utilities rather than
  duplicating patterns already in the library.

## Verification

Baseline:

```bash
uv run ruff check .
uv run ty check . --python-version 3.14
uv run pytest tests/ -q
```

Add focused checks when relevant:

- Scan/snapshot behavior: `uv run pytest tests/test_scan_snapshot.py -q`
- Build entrypoint wiring: `uv run pytest tests/test_build_entrypoint.py -q`
- Headless Qt: `QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q`
- UI or end-to-end flow: `uv run python src/structura/main.py`

## CI Limitations

CI proves lint, type safety, and unit test correctness. It does NOT prove the app launches
successfully, the packaged bundle includes all runtime assets, or the DMG layout is correct.

## Release Readiness Checklist

Before tagging a release, verify all of the following:
- [ ] `uv run ruff check .` passes with no errors
- [ ] `uv run ty check . --python-version 3.14` passes with no errors
- [ ] `uv run pytest tests/ -q` passes with no failures
- [ ] App launches locally from a clean `uv sync`
- [ ] At least one core user flow exercised manually end-to-end
- [ ] `pyproject.toml` version matches README/display text

### What CI Does Not Prove
> Green CI is necessary but not sufficient for a safe release.
> Source site behavior (4Charm), macOS permissions (Nexus), and external tools (L!bra/Papyrus)
> cannot be fully validated by static CI checks.

## Shared Links
- Skills SSOT: `../../Skills`
- MCP Config: `../../mcp.json`

## Universal Safety Rules

Before making changes, read and follow:

../../docs/Agent Pre-Safety Rules.md

---

## App Repository Rules

This is an individual app repository. Keep all changes scoped to this app
unless explicitly requested.
- Do not modify unrelated apps.
- Do not create branches unless explicitly requested.
- Do not switch branches unless explicitly requested.
- Do not create or switch worktrees unless explicitly requested.
- Do not commit unless explicitly requested.
- Do not push unless explicitly requested.
- Do not delete, rename, move, or overwrite unrelated files.
- Preserve existing project style and conventions.
- Keep changes minimal and targeted.

---

## App Environment

Assume:
- Apple Silicon macOS
- Python 3.14
- uv
- ruff
- ty
- pytest

Prefer:
    uv sync
    uv run ruff check .
    uv run ty check .
    uv run pytest

---

## App Workflow

Before editing:

1. Inspect relevant files.
2. Identify existing project commands.
3. Make the smallest safe change.
4. Avoid broad refactors unless explicitly requested.
5. Avoid dependency/config changes unless required.

---

## App Validation

After code changes, suggest or run relevant checks:
    uv run ruff check .
    uv run ty check .
    uv run pytest

If packaging/build files changed, inspect existing build scripts before
suggesting build commands. Do not claim validation passed unless actual command
output confirms it.

---

## Structura Notes

Structura is a macOS filesystem explorer/media organizer app.
Be careful with filesystem operations:
- Prefer read-only inspection first.
- Do not delete, move, or rename user files unless explicitly requested.
- For cleanup features, prefer dry runs, manifests, and reversible actions.


## Behavioral Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use your judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.