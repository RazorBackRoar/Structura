# Video Metadata Columns — Design Spec

**Date:** 2026-03-28
**Status:** Draft

## Summary

Replace Structura's single "Frame Rate" column (raw fps display) with three video-specific columns — **Resolution**, **Frame Rate** (categorized), and **Orientation** — and update GPS/Make/Model columns with emoji indicators. Merge the Type and Items columns into Title.

## Motivation

Apple devices shoot video at NTSC-derived frame rates (29.97, 59.94, 23.976) — never exactly 30.000 or 60.000. Edited/exported videos land on round numbers. Detecting this distinction lets users quickly identify which videos have been processed. Additionally, resolution and orientation are key metadata for video organization that Structura currently doesn't surface.

## Data Model

### New: VideoInfo dataclass

```python
@dataclass(frozen=True)
class VideoInfo:
    width: int                    # pixels (rotation-corrected)
    height: int                   # pixels (rotation-corrected)
    raw_fps: float | None         # actual fps from atoms (29.97, 59.94, etc.)
    resolution: str               # "4K", "1080p", "720p", "HD", "SD"
    orientation: str              # "V" or "W"
    fps_category: int | None      # 30 or 60 (None if outside 1-70 range)
    is_edited: bool               # True if scissors applies
```

### Updated: TreeItemMetadata

- `frame_rate: float | None` replaced by `video_info: VideoInfo | None`
- `frame_rate_text: str` removed — replaced by display fields derived from `VideoInfo`
- `type_label: str` remains — still needed for file type classification and emoji logic in Title column

## Classification Logic

### Resolution

Uses `max(width, height)` for consistent classification regardless of orientation:

```
long_edge = max(width, height)

long_edge >= 2160  → "4K"
long_edge >= 1080  → "1080p"
long_edge >= 720   → "720p"
long_edge > 480    → "HD"
else               → "SD"
```

### Orientation

```
height > width  → "V" (vertical/portrait)
height == width → "W" (square treated as wide)
height < width  → "W" (wide/landscape)
```

### Frame Rate Category

```
fps is None or fps < 1.0 or fps > 70.0  → None (slo-mo or unknown)
fps >= 32.0                               → category 60
fps < 32.0                                → category 30
```

### Scissors (edited video detection)

```
30.0 <= fps < 32.0  → edited (scissors) — category 30
60.0 <= fps <= 70.0 → edited (scissors) — category 60
all other ranges    → not edited
```

The scissors boundary aligns with the category split at 32.0 — no gap.

Apple devices never shoot at exactly 30.000 or 60.000 fps. If a video has these exact rates, it was processed by editing software. The 32.0–59.999 range (category 60, no scissors) covers non-Apple cameras that shoot at native rates like 48fps or 50fps (PAL).

### Slo-mo display

For fps > 70 (slo-mo), display the rounded integer (e.g. 239.76 → `240`). No category, no scissors.

## Column Layout

### Column index migration

**Old (10 columns):**
```
0: Title  1: Type  2: Items  3: File Size  4: Frame Rate  5: GPS  6: Make  7: Model  8: Created  9: Modified
```

**New (10 columns):**
```
0: Title  1: File Size  2: Resolution  3: Frame Rate  4: Orientation  5: GPS  6: Make  7: Model  8: Created  9: Modified
```

Removed: `TREE_COLUMN_TYPE` (1), `TREE_COLUMN_ITEMS` (2). Added: `TREE_COLUMN_RESOLUTION` (2), `TREE_COLUMN_ORIENTATION` (4). All column index constants must be renumbered. Callsites to update include: `_apply_tree_item_metadata()`, `_style_tree_item_title()`, `_sort_tree_data()`, `TREE_COLUMN_WIDTHS`, `TREE_HEADERS`, and all `item.setText(TREE_COLUMN_*)` / `item.setData(TREE_COLUMN_*)` calls.

| Index | Constant | Header | Width | Notes |
|---|---|---|---|---|
| 0 | TREE_COLUMN_TITLE | Title | 280 | Emoji + name. Folders: `📁 Vacation (42)`. Files: `🎬 vacation.mov` |
| 1 | TREE_COLUMN_SIZE | File Size | 110 | |
| 2 | TREE_COLUMN_RESOLUTION | Resolution | 70 | Videos only. `4K`, `1080p`, `720p`, `HD`, `SD` |
| 3 | TREE_COLUMN_FRAME_RATE | Frame Rate | 80 | Videos only. `30`, `60`, `30 ✂️`, `60 ✂️`. Tooltip: raw fps (e.g. `29.97 fps`) |
| 4 | TREE_COLUMN_ORIENTATION | Orientation | 80 | Videos only. `V` or `W` |
| 5 | TREE_COLUMN_GPS | GPS | 50 | Media only. 🌍 (has coords) or ❌ (no coords). Tooltip: coordinates |
| 6 | TREE_COLUMN_MAKE | Make | 50 | Media only. 🍎 (Apple) or ❌ (not Apple) |
| 7 | TREE_COLUMN_MODEL | Model | 160 | Media only. 📱 iPhone 16 Pro (iPhone emoji + model). Non-iPhone: model text only |
| 8 | TREE_COLUMN_CREATED | Date Created | 118 | |
| 9 | TREE_COLUMN_MODIFIED | Date Modified | 118 | |

### Folder title format

Item count appended after `tree_display_name()` returns: `tree_display_name(name, emoji) + f" ({count})"` when count > 0.

### Removed columns
- **Type** — merged into Title (emoji already communicates type)
- **Items** — merged into Title for folders as `(count)`

## Atom Parsing Changes

### Current: `_quicktime_frame_rate()`
Traverses `moov → trak → mdia → hdlr/mdhd/minf/stbl/stts` for fps only. Returns `float | None`.

### New: `_quicktime_video_info()`
Same traversal, additionally reads `tkhd` (inside `trak`, same level as `mdia`) for width, height, and rotation.

**tkhd atom structure:**
- Version byte at offset 0 determines layout:
  - Version 0: matrix at byte offset 40, width at byte 76, height at byte 80
  - Version 1: matrix at byte offset 52, width at byte 88, height at byte 92
- Width and height are fixed-point 16.16 format (divide by 65536 or right-shift 16)
- Rotation extracted from the 3x3 transformation matrix: `rotation = atan2(matrix[0][1], matrix[0][0])` — 90° and 270° swap width/height

Returns `VideoInfo | None`.

### Fallback: mdls
If QuickTime atom parsing fails, fall back to macOS `mdls`:
- `kMDItemPixelWidth` / `kMDItemPixelHeight` for dimensions (new mdls queries — the mdls mechanism exists in the codebase for EXIF, but pixel dimensions are not currently queried)
- fps not available via mdls — will be None, resolution/orientation still determined from dimensions

## Dashboard Updates

File header info tiles when a single file is selected:
- **Type** tile → **Resolution** tile (e.g. `4K`)
- **Size** tile stays
- **Frame Rate** tile updated to show category + scissors (e.g. `30 ✂️`)

## Sorting Behavior

- **Resolution:** Sort by `width * height` (pixel count) via `TREE_SORT_ROLE`. 4K > 1080p > 720p > HD > SD. `VideoInfo` provides `width` and `height` for computing the sort key.
- **Frame Rate:** Sort by `raw_fps` (numeric) via `TREE_SORT_ROLE`, not the category string
- **Orientation:** Sort alphabetically (V, W)

## Display Examples

| Scenario | Resolution | Frame Rate | Orientation |
|---|---|---|---|
| iPhone 4K vertical, 29.97fps | 4K | 30 | V |
| iPhone 1080p wide, 59.94fps | 1080p | 60 | W |
| Edited 1080p wide, 30.0fps | 1080p | 30 ✂️ | W |
| Edited 4K wide, 60.0fps | 4K | 60 ✂️ | W |
| iPhone 720p vertical, 29.97fps | 720p | 30 | V |
| Slo-mo 1080p, 240fps | 1080p | 240 | W |
| Time-lapse 4K, 0.5fps | 4K | | W |

## Test Plan

- Update `test_quicktime_frame_rate_parser_reads_average_fps` for new `VideoInfo` return type
- Test `_classify_resolution()` using `max(width, height)`:
  - 3840x2160 → 4K, 2160x3840 → 4K (vertical)
  - 1920x1080 → 1080p, 1080x1920 → 1080p (vertical)
  - 1280x720 → 720p
  - 960x540 → HD (long edge 960 > 480)
  - 480x360 → SD
  - 1080x1080 → 1080p (square)
- Test `_classify_fps()`: all ranges
  - 0.5 → None category (time-lapse)
  - 1.0, 15.5, 29.999 → category 30, no scissors
  - 30.0, 30.5, 31.5 → category 30, scissors
  - 32.0, 45.0, 59.999 → category 60, no scissors
  - 60.0, 65.0, 70.0 → category 60, scissors
  - 120.0, 240.0 → None category (slo-mo)
- Test orientation: vertical (height > width) → V, landscape → W, square → W
- Test rotation handling: 90/270 degree rotation swaps width/height
- Test mdls fallback when atom parsing returns None
- Test column layout: 10 columns, correct headers, correct indices
- Test folder title includes item count: `📁 Vacation (42)`
- Test GPS emoji: 🌍 when coordinates present, ❌ when absent
- Test Make emoji: 🍎 when Apple, ❌ otherwise
- Test Model display: 📱 prefix for iPhone models
- Test slo-mo display: 239.76 fps → `240`
- Test Frame Rate tooltip shows raw fps formatted as `29.97 fps`
