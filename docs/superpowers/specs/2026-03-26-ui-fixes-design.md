# UI Fixes Design — 2026-03-26

## Problem

The Structura UI has five concrete issues visible in production:

1. The right-panel header overflows when a file with a long UUID name is selected, and the metric tiles are inconsistently styled.
2. The top metric tiles (Total Files, Total Size, Total Folders) show the **selected item's** stats rather than root folder totals, making "TOTAL FILES: 1" appear when a single file is clicked — confusing and misleading.
3. The File Size column in the tree is too narrow — the header renders as "File S" and values are clipped.
4. The default and minimum window widths are too small, causing the right panel to feel cramped.
5. Long UUID filenames are truncated in the middle in the tree, making every row look identical.

---

## Design

### 1. Right Panel Header (selected file/folder)

**Layout (approved in visual companion session):**

```
📹 MOV · Feb 24, 2026          ← file type emoji + ext + date created, small muted text
000019ae-c0b0-7977…(H.265).mov ← filename, truncated at the right, one line

[ TYPE        ] [ SIZE         ] [ FRAME RATE   ]
[ MOV         ] [ 10.7 MB      ] [ 60 fps       ]
  #eef3ff bg     #eef3ff bg      #eef3ff bg
  #3b63f0 label  #3b63f0 label   #3b63f0 label (11px, bold)
  #284ac8 value  #284ac8 value   #284ac8 value (20px, bold)
```

- All three tiles: background `#eef3ff`, label color `#3b63f0` at 11px bold, value color `#284ac8` at 20px bold.
- The subtitle line format: `{emoji} {EXT} · {date_created}`.
- Filename: `Qt.ElideRight` (truncate at end, not middle).
- Frame Rate tile shows `—` for non-video files (consistent with existing `_format_frame_rate` behavior).

**Files to change:** `Structura.py` — the right-panel header section inside `AnalyzerDashboard`.

---

### 2. Metric Tiles Always Show Root Totals

The three top `MetricTile` widgets (Total Files, Total Size, Total Folders) must always reflect the **root folder** stats from `ScanSnapshot`, regardless of which item is selected in the tree.

- `AnalyzerDashboard.set_snapshot()` already receives both `snapshot: ScanSnapshot` (root) and `selected_stats: SubtreeStats` (selected item) — no signature change needed. The fix is to update the metric tile refresh logic inside this method to read from `snapshot` (root totals) instead of `selected_stats`.
- This separates two concerns that were previously conflated: "what is in this whole folder?" vs "what is this specific item?".

**Files to change:** `Structura.py` — `AnalyzerDashboard.set_snapshot()` and the metric tile update logic.

---

### 3. File Size Column Width

Increase the `TREE_COLUMN_SIZE` column width constant from `110` → `130` px so the "File Size" header and values are never clipped.

**Files to change:** `Structura.py` — `TREE_COLUMN_WIDTHS` constant.

---

### 4. Window Size

| Setting | Before | After |
|---------|--------|-------|
| Minimum width | 1180 | 1280 |
| Default width | 1280 | 1440 |
| Minimum height | 760 | 760 (unchanged) |
| Default height | 840 | 860 |

**Files to change:** `Structura.py` — `StructuraWindow.__init__()` calls to `setMinimumSize` and `resize`.

---

### 5. Filename Truncation in Tree

Change tree title column truncation from `Qt.ElideMiddle` → `Qt.ElideRight` so UUIDs remain distinguishable from the start of the string.

**Files to change:** `Structura.py` line 3238 — `self._tree.setTextElideMode(Qt.ElideMiddle)` inside `FolderTreePane`. Also update `set_elided_label_text()` (line 862) where it uses `Qt.ElideMiddle` for path labels in the right panel header.

---

## Files Changed

All changes are in `Structura.py`. No new files required.

| Location | Change |
|----------|--------|
| `TREE_COLUMN_WIDTHS` constant | File Size column: 110 → 130 |
| `StructuraWindow.__init__` | `setMinimumSize(1280, 760)`, `resize(1440, 860)` |
| `AnalyzerDashboard.set_snapshot()` | Top tiles use `snapshot` root totals |
| Right-panel header widget | New layout with subtitle line + 3 matching blue tiles |
| Tree item title truncation | `ElideMiddle` → `ElideRight` |

---

## Out of Scope

- Dark mode
- Any new features beyond File Type / File Size visibility (already in tree, now properly sized)
- Refactoring the single-file architecture
