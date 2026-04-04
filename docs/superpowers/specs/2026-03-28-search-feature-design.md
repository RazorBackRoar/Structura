# Search Feature Design

**Date:** 2026-03-28
**Scope:** Add a real-time file search box to `FolderTreePane` in `Structura.py`

---

## Overview

A search box in the `FolderTreePane` lets users type a partial filename and instantly see a flat results list replacing the tree. Clearing the box restores the tree exactly as it was. No new dependencies. All changes are isolated to `FolderTreePane` and its helpers.

---

## Behavior

### Search Box

- `QLineEdit` placed between the path label and the tree widget in `FolderTreePane`
- Placeholder text: `"Search files…"`
- Built-in clear button via `setClearButtonEnabled(True)`
- Hidden when no snapshot is loaded; shown once a folder is loaded
- `Cmd+F` focuses the search box
- `Escape` clears the box and returns focus to the tree

### Results List

- When the box has text: the `QTreeWidget` is hidden, a `QListWidget` appears in its place
- When the box is empty: the `QListWidget` is hidden, the `QTreeWidget` is restored
- Each row shows two lines:
  - **Line 1:** filename (full name, normal weight)
  - **Line 2:** relative path from snapshot root (dimmed, smaller font — e.g. `Footage/2024/clip.mov`)
- Long paths are elided with `…`; full path shown in tooltip
- Results sorted alphabetically by filename (case-insensitive)
- If no results: centered label `"No results for '…'"` shown inside the list area
- Clicking a row emits `FolderTreePane.path_selected` with the full absolute path — same signal the tree emits, right panel updates with no extra wiring

### Filtering Logic

- Match: case-insensitive substring of the **filename only** (not the path)
- Source: `snapshot.stats_by_path` — a flat dict already in memory, no tree traversal needed
- Only files included (`stats.is_dir == False`); folders excluded from results
- Populated fresh on every `textChanged` signal — fast enough for thousands of entries

### Snapshot Reload

- If the snapshot is replaced while search is active, the search box is cleared and the tree is shown (stale results would be misleading)

---

## Architecture

### New members on `FolderTreePane`

| Member | Type | Purpose |
|--------|------|---------|
| `_search_box` | `QLineEdit` | Search input |
| `_results_list` | `QListWidget` | Flat results view |

### New methods on `FolderTreePane`

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_on_search_changed` | `(text: str) -> None` | Slot connected to `_search_box.textChanged`; dispatches to `_filter_tree` or restores tree |
| `_filter_tree` | `(query: str) -> None` | Populates `_results_list` from `snapshot.stats_by_path` |
| `_on_result_clicked` | `(item: QListWidgetItem) -> None` | Emits `path_selected` with path stored in `Qt.UserRole` |

### Layout

```
FolderTreePane (QVBoxLayout)
├── eyebrow label
├── title label
├── path label
├── _search_box          ← NEW (hidden until snapshot loaded)
├── _tree                ← hidden when search active
├── _results_list        ← NEW (hidden when search empty)
└── _empty               ← shown when no snapshot
```

### Data flow

```
User types → textChanged → _on_search_changed(text)
  ├── text empty  → hide _results_list, show _tree
  └── text non-empty → _filter_tree(text)
        → walk stats_by_path, filter is_dir=False, filename.lower() contains query.lower()
        → sort by filename
        → populate _results_list (QListWidgetItem per result, UserRole = full path)
        → hide _tree, show _results_list

User clicks result → _on_result_clicked(item)
  → emit path_selected(item.data(Qt.UserRole))
```

---

## Styling

- `QLineEdit` styled to match the existing dark surface:
  - Background: `C["surface_raised"]`
  - Border: `1px solid C["border"]`
  - Border-radius: `10px`
  - Padding: `6px 10px`
  - Text color: `C["text_primary"]`
  - Placeholder color: `C["text_secondary"]`
- `QListWidget` uses `tree_style(background=PANEL_BG_SOFT)` (same as the tree) for visual consistency
- Each result item uses a custom delegate or two-line `QListWidgetItem` with the path in a smaller, dimmed font via HTML or `setForeground`

---

## Keyboard Shortcut

- `Cmd+F` shortcut registered in `FolderTreePane.__init__` via `QShortcut(QKeySequence("Ctrl+F"), self)` — on macOS, Qt maps `Ctrl` to `Cmd`
- `Escape` on the search box: connected to `_search_box.clear()` then `self._tree.setFocus()`

---

## Testing

New tests in `tests/test_scan_snapshot.py::DashboardBehaviorTest`:

1. **`test_search_returns_matching_files`** — scan a folder with several files, type a partial name, verify `_results_list` is visible and contains only matching items
2. **`test_search_empty_restores_tree`** — after typing, clear the box, verify `_tree` is shown and `_results_list` is hidden
3. **`test_search_excludes_folders`** — verify folder names do not appear in results
4. **`test_search_result_click_emits_path_selected`** — click a result item, verify `path_selected` signal carries the correct path
5. **`test_search_cleared_on_snapshot_reload`** — set snapshot, type a query, set a new snapshot, verify search box is empty and tree is shown
