# Video Metadata Columns Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Structura's single raw-fps "Frame Rate" column with three video-specific columns (Resolution, Frame Rate category with scissors, Orientation), merge Type and Items into Title, and add emoji indicators for GPS/Make/Model.

**Architecture:** Extend the QuickTime atom parser to extract width/height/rotation from `tkhd` atoms in the same traversal, add a `VideoInfo` dataclass with classification logic, renumber column constants, and update all display/sort callsites atomically (no broken commits). A `mdls` fallback covers cases where atom parsing fails on `.mov`/`.mp4`/`.m4v` files.

**Tech Stack:** Python 3.14, PySide6/Qt 6, macOS `mdls` subprocess (existing pattern), `math.atan2` for rotation, `@lru_cache` for atom parse results.

**Spec:** `docs/superpowers/specs/2026-03-28-video-metadata-columns-design.md`

---

## Files Modified

- `Structura.py` — all changes live here (single-file app)
- `tests/test_scan_snapshot.py` — update and extend tests

---

## Chunk 1: VideoInfo dataclass and classification functions

### Task 1: Add VideoInfo dataclass and classification functions

**Files:**
- Modify: `Structura.py` — after `FileExif` dataclass at line ~722
- Modify: `tests/test_scan_snapshot.py`

- [ ] **Step 1: Write failing tests for classification functions**

Add to the imports in `tests/test_scan_snapshot.py`:

```python
from Structura import (
    AnalyzerDashboard,
    FolderTreePane,
    SortWorker,
    SubtreeStats,
    VideoInfo,           # NEW
    _classify_resolution, # NEW
    _classify_fps,        # NEW
    _quicktime_video_info, # NEW (replaces _quicktime_frame_rate)
    _display_folder_count,
    extension_color,
    file_emoji,
    _human_size,
    collect_sortable_extensions,
    scan_folder,
)
```

Add this new test class to `tests/test_scan_snapshot.py`:

```python
class VideoClassificationTest(unittest.TestCase):
    def test_classify_resolution_4k(self):
        self.assertEqual(_classify_resolution(3840, 2160), "4K")
        self.assertEqual(_classify_resolution(2160, 3840), "4K")  # vertical 4K

    def test_classify_resolution_1080p(self):
        self.assertEqual(_classify_resolution(1920, 1080), "1080p")
        self.assertEqual(_classify_resolution(1080, 1920), "1080p")  # vertical
        self.assertEqual(_classify_resolution(1080, 1080), "1080p")  # square

    def test_classify_resolution_720p(self):
        self.assertEqual(_classify_resolution(1280, 720), "720p")
        self.assertEqual(_classify_resolution(720, 1280), "720p")

    def test_classify_resolution_hd(self):
        self.assertEqual(_classify_resolution(960, 540), "HD")  # long edge 960 > 480, < 720

    def test_classify_resolution_sd(self):
        self.assertEqual(_classify_resolution(480, 360), "SD")
        self.assertEqual(_classify_resolution(320, 240), "SD")

    def test_classify_fps_category_30_no_scissors(self):
        for fps in [1.0, 15.5, 29.0, 29.999]:
            cat, scissors = _classify_fps(fps)
            self.assertEqual(cat, 30, f"fps={fps}")
            self.assertFalse(scissors, f"fps={fps}")

    def test_classify_fps_category_30_with_scissors(self):
        for fps in [30.0, 30.5, 31.5]:
            cat, scissors = _classify_fps(fps)
            self.assertEqual(cat, 30, f"fps={fps}")
            self.assertTrue(scissors, f"fps={fps}")

    def test_classify_fps_category_60_no_scissors(self):
        for fps in [32.0, 45.0, 59.999]:
            cat, scissors = _classify_fps(fps)
            self.assertEqual(cat, 60, f"fps={fps}")
            self.assertFalse(scissors, f"fps={fps}")

    def test_classify_fps_category_60_with_scissors(self):
        for fps in [60.0, 65.0, 70.0]:
            cat, scissors = _classify_fps(fps)
            self.assertEqual(cat, 60, f"fps={fps}")
            self.assertTrue(scissors, f"fps={fps}")

    def test_classify_fps_slomo_returns_none(self):
        for fps in [120.0, 240.0]:
            cat, scissors = _classify_fps(fps)
            self.assertIsNone(cat, f"fps={fps}")
            self.assertFalse(scissors, f"fps={fps}")

    def test_classify_fps_timelapse_returns_none(self):
        cat, scissors = _classify_fps(0.5)
        self.assertIsNone(cat)
        self.assertFalse(scissors)

    def test_classify_fps_none_returns_none(self):
        cat, scissors = _classify_fps(None)
        self.assertIsNone(cat)
        self.assertFalse(scissors)
```

- [ ] **Step 2: Run to confirm import failure**

```bash
cd /Users/razor/Documents/Claude/Structura
python -m pytest tests/test_scan_snapshot.py::VideoClassificationTest -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'VideoInfo'`

- [ ] **Step 3: Add VideoInfo and classification functions to Structura.py**

`math` is already imported via `from functools import lru_cache` — but `math` itself is not. Add to the top-level imports block (lines 9-19):

```python
import math
```

Then find the `FileExif` dataclass at line ~722 and insert directly after it (after line 726):

```python
@dataclass(frozen=True)
class VideoInfo:
    width: int                 # pixels (rotation-corrected)
    height: int                # pixels (rotation-corrected)
    raw_fps: float | None      # actual fps (29.97, 59.94, etc.)
    resolution: str            # "4K", "1080p", "720p", "HD", "SD"
    orientation: str           # "V" or "W"
    fps_category: int | None   # 30, 60, or None (slo-mo/unknown)
    is_edited: bool            # True → show ✂️


def _classify_resolution(width: int, height: int) -> str:
    long_edge = max(width, height)
    if long_edge >= 2160:
        return "4K"
    if long_edge >= 1080:
        return "1080p"
    if long_edge >= 720:
        return "720p"
    if long_edge > 480:
        return "HD"
    return "SD"


def _classify_fps(raw_fps: float | None) -> tuple[int | None, bool]:
    """Return (category, is_edited). Category is 30, 60, or None."""
    if raw_fps is None or raw_fps < 1.0 or raw_fps > 70.0:
        return None, False
    if raw_fps >= 32.0:
        return 60, (60.0 <= raw_fps <= 70.0)
    return 30, (30.0 <= raw_fps < 32.0)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_scan_snapshot.py::VideoClassificationTest -v
```

Expected: All green.

- [ ] **Step 5: Commit**

```bash
git add Structura.py tests/test_scan_snapshot.py
git commit -m "feat: add VideoInfo dataclass and fps/resolution classification"
```

---

## Chunk 2: QuickTime atom parser upgrade + mdls fallback

### Task 2: Replace _quicktime_frame_rate with _quicktime_video_info

**Files:**
- Modify: `Structura.py` — lines ~989–1060

- [ ] **Step 1: Write failing tests for _quicktime_video_info**

Add this new test class to `tests/test_scan_snapshot.py`:

```python
class QuicktimeVideoInfoTest(unittest.TestCase):
    def _make_tkhd_v0(self, width_px: int, height_px: int, rotation_deg: int = 0) -> bytes:
        """Build a tkhd version-0 atom (full atom including size+type header)."""
        angle = math.radians(rotation_deg)
        a = math.cos(angle)
        b = math.sin(angle)
        c = -math.sin(angle)
        d = math.cos(angle)

        def fp(v: float) -> bytes:
            return round(v * 65536).to_bytes(4, "big", signed=True)

        # tkhd v0 payload layout:
        # 0: version(1)+flags(3), 4: ctime(4), 8: mtime(4), 12: trackid(4),
        # 16: reserved(4), 20: duration(4), 24: reserved(8),
        # 32: layer(2), 34: altgroup(2), 36: volume(2), 38: reserved(2),
        # 40: matrix(36), 76: width(4 fp16.16), 80: height(4 fp16.16)
        matrix = (
            fp(a) + fp(b) + b"\x00\x00\x00\x00"
            + fp(c) + fp(d) + b"\x00\x00\x00\x00"
            + b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00" + b"\x00\x01\x00\x00"
        )
        payload = (
            b"\x00\x00\x00\x00"   # version=0, flags
            + b"\x00\x00\x00\x00" # creation_time
            + b"\x00\x00\x00\x00" # modification_time
            + b"\x00\x00\x00\x01" # track_id
            + b"\x00\x00\x00\x00" # reserved
            + b"\x00\x00\x00\x00" # duration
            + b"\x00" * 8         # reserved
            + b"\x00\x00"         # layer
            + b"\x00\x00"         # alternate_group
            + b"\x00\x00"         # volume
            + b"\x00\x00"         # reserved
            + matrix
            + (width_px * 65536).to_bytes(4, "big")
            + (height_px * 65536).to_bytes(4, "big")
        )
        size = len(payload) + 8
        return size.to_bytes(4, "big") + b"tkhd" + payload

    def _make_movie(self, width: int, height: int, rotation: int,
                    timescale: int, frame_count: int, sample_delta: int) -> bytes:
        def atom(kind, payload):
            return (len(payload) + 8).to_bytes(4, "big") + kind + payload

        def full_box(kind, payload):
            return atom(kind, b"\x00\x00\x00\x00" + payload)

        stts = full_box(b"stts", (
            (1).to_bytes(4, "big")
            + frame_count.to_bytes(4, "big")
            + sample_delta.to_bytes(4, "big")
        ))
        stbl = atom(b"stbl", stts)
        minf = atom(b"minf", stbl)
        mdhd = full_box(b"mdhd", (
            b"\x00\x00\x00\x00"
            + b"\x00\x00\x00\x00"
            + timescale.to_bytes(4, "big")
            + (frame_count * sample_delta).to_bytes(4, "big")
            + b"\x00\x00\x00\x00"
        ))
        hdlr = full_box(b"hdlr", b"\x00\x00\x00\x00" + b"vide" + b"\x00" * 12)
        mdia = atom(b"mdia", mdhd + hdlr + minf)
        tkhd = self._make_tkhd_v0(width, height, rotation)
        trak = atom(b"trak", tkhd + mdia)
        return atom(b"moov", trak)

    def test_reads_fps_and_dimensions_landscape(self):
        # 30000 timescale, 100 frames, delta=1001 → 30000*100/(100*1001) ≈ 29.97 fps (NTSC)
        movie = self._make_movie(1920, 1080, 0, 30000, 100, 1001)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
        self.assertIsNotNone(info)
        self.assertAlmostEqual(info.raw_fps, 29.97, places=1)
        self.assertEqual(info.width, 1920)
        self.assertEqual(info.height, 1080)
        self.assertEqual(info.resolution, "1080p")
        self.assertEqual(info.orientation, "W")
        self.assertEqual(info.fps_category, 30)
        self.assertFalse(info.is_edited)

    def test_reads_vertical_orientation(self):
        movie = self._make_movie(1080, 1920, 0, 600, 120, 10)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
        self.assertEqual(info.orientation, "V")
        self.assertEqual(info.width, 1080)
        self.assertEqual(info.height, 1920)

    def test_rotation_90_swaps_dimensions(self):
        # stored as 1920x1080, rotated 90° → displayed as 1080x1920 (vertical)
        movie = self._make_movie(1920, 1080, 90, 600, 120, 10)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
        self.assertEqual(info.width, 1080)   # swapped
        self.assertEqual(info.height, 1920)  # swapped
        self.assertEqual(info.orientation, "V")

    def test_edited_video_gets_scissors(self):
        # 3000 timescale, 100 frames, delta=100 → 3000*100/(100*100) = 30.0 fps (edited)
        movie = self._make_movie(1920, 1080, 0, 3000, 100, 100)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
        self.assertAlmostEqual(info.raw_fps, 30.0, places=1)
        self.assertTrue(info.is_edited)
        self.assertEqual(info.fps_category, 30)

    def test_4k_resolution_detected(self):
        movie = self._make_movie(3840, 2160, 0, 600, 120, 10)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
        self.assertEqual(info.resolution, "4K")
```

Add `import math` to the test file imports (it's needed by `_make_tkhd_v0`):
```python
import math
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_scan_snapshot.py::QuicktimeVideoInfoTest -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name '_quicktime_video_info'`

- [ ] **Step 3: Add _quicktime_tkhd_dimensions and _quicktime_video_info to Structura.py**

Find the `@lru_cache(maxsize=2048)` decorator on `_quicktime_frame_rate` at line ~989. Replace the entire `_quicktime_frame_rate` function (lines ~989–1034) with:

```python
def _quicktime_tkhd_dimensions(handle, payload_start: int) -> tuple[int, int] | None:
    """Read width, height (rotation-corrected) from a tkhd atom payload."""
    try:
        handle.seek(payload_start)
        version_byte = handle.read(1)
        if not version_byte:
            return None
        version = version_byte[0]
        # Version 0: matrix at byte offset 40, width at 76, height at 80
        # Version 1: matrix at byte offset 52, width at 88, height at 92
        if version == 0:
            matrix_offset, dim_offset = 40, 76
        elif version == 1:
            matrix_offset, dim_offset = 52, 88
        else:
            return None

        handle.seek(payload_start + matrix_offset)
        matrix_bytes = handle.read(36)
        if len(matrix_bytes) < 36:
            return None

        # a and b are the first two 16.16 fixed-point values; atan2(b, a) gives rotation
        a = int.from_bytes(matrix_bytes[0:4], "big", signed=True) / 65536
        b = int.from_bytes(matrix_bytes[4:8], "big", signed=True) / 65536
        angle_deg = round(math.degrees(math.atan2(b, a)))

        handle.seek(payload_start + dim_offset)
        dim_bytes = handle.read(8)
        if len(dim_bytes) < 8:
            return None

        w_raw = int.from_bytes(dim_bytes[0:4], "big") >> 16
        h_raw = int.from_bytes(dim_bytes[4:8], "big") >> 16

        # Swap dimensions if rotated 90 or 270 degrees
        if angle_deg in (90, -90, 270, -270):
            return h_raw, w_raw
        return w_raw, h_raw
    except Exception:
        return None


@lru_cache(maxsize=2048)
def _quicktime_video_info(path_str: str, modified_ns: int) -> "VideoInfo | None":
    del modified_ns  # only used as cache key to bust stale results
    path = Path(path_str)
    try:
        file_size = path.stat().st_size
        with path.open("rb") as handle:
            moov = _find_quicktime_atom(handle, 0, file_size, b"moov")
            if not moov:
                return None
            moov_start, moov_end = moov

            width, height, raw_fps = None, None, None

            for kind, trak_start, trak_end in _iter_quicktime_atoms(
                handle, moov_start, moov_end
            ):
                if kind != b"trak":
                    continue
                mdia = _find_quicktime_atom(handle, trak_start, trak_end, b"mdia")
                if not mdia:
                    continue
                mdia_start, mdia_end = mdia
                hdlr = _find_quicktime_atom(handle, mdia_start, mdia_end, b"hdlr")
                if not hdlr or _quicktime_handler_type(handle, hdlr[0]) != b"vide":
                    continue

                # Dimensions from tkhd (sibling of mdia, inside trak)
                tkhd = _find_quicktime_atom(handle, trak_start, trak_end, b"tkhd")
                if tkhd and width is None:
                    dims = _quicktime_tkhd_dimensions(handle, tkhd[0])
                    if dims:
                        width, height = dims

                # Frame rate from mdhd + stts
                mdhd = _find_quicktime_atom(handle, mdia_start, mdia_end, b"mdhd")
                minf = _find_quicktime_atom(handle, mdia_start, mdia_end, b"minf")
                if mdhd and minf and raw_fps is None:
                    stbl = _find_quicktime_atom(handle, minf[0], minf[1], b"stbl")
                    if stbl:
                        stts = _find_quicktime_atom(handle, stbl[0], stbl[1], b"stts")
                        if stts:
                            timescale = _quicktime_timescale(handle, mdhd[0])
                            sample_timing = _quicktime_sample_timing(handle, stts[0])
                            if timescale and sample_timing:
                                total_samples, total_duration = sample_timing
                                if total_duration > 0:
                                    raw_fps = timescale * total_samples / total_duration

            if width is None or height is None:
                return None

            fps_category, is_edited = _classify_fps(raw_fps)
            return VideoInfo(
                width=width,
                height=height,
                raw_fps=raw_fps,
                resolution=_classify_resolution(width, height),
                orientation="V" if height > width else "W",
                fps_category=fps_category,
                is_edited=is_edited,
            )
    except OSError:
        return None
```

- [ ] **Step 4: Update _file_browser_metadata to use _quicktime_video_info and add mdls fallback**

Find `_file_browser_metadata` at line ~1037 and replace the entire function:

```python
def _mdls_video_dimensions(path: str) -> tuple[int, int] | None:
    """Read pixel dimensions from macOS Spotlight for when atom parsing fails."""
    try:
        result = subprocess.run(
            ["mdls", "-raw", "-nullMarker", "",
             "-name", "kMDItemPixelWidth",
             "-name", "kMDItemPixelHeight",
             path],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            return None
        lines = [ln.strip() for ln in result.stdout.strip().splitlines()]
        if len(lines) < 2 or not lines[0] or not lines[1]:
            return None
        return int(float(lines[0])), int(float(lines[1]))
    except Exception:
        return None


def _file_browser_metadata(
    path_str: str,
    *,
    is_dir: bool,
    ext: str,
) -> tuple[float | None, float | None, "VideoInfo | None"]:
    if not path_str:
        return None, None, None
    path = Path(path_str)
    try:
        stat_result = path.stat()
    except OSError:
        return None, None, None

    created_ts = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
    modified_ts = stat_result.st_mtime
    video_info = None
    if (
        not is_dir
        and ext in QUICKTIME_FRAME_RATE_EXTENSIONS
        and ext in VIDEO_EXTENSIONS
    ):
        video_info = _quicktime_video_info(path_str, stat_result.st_mtime_ns)
        if video_info is None:
            # Atom parsing failed (e.g. corrupted file) — try Spotlight dimensions
            dims = _mdls_video_dimensions(path_str)
            if dims:
                w, h = dims
                fps_cat, is_edited = _classify_fps(None)
                video_info = VideoInfo(
                    width=w, height=h, raw_fps=None,
                    resolution=_classify_resolution(w, h),
                    orientation="V" if h > w else "W",
                    fps_category=fps_cat,
                    is_edited=is_edited,
                )
    return created_ts, modified_ts, video_info
```

- [ ] **Step 5: Update the existing old test that imported _quicktime_frame_rate**

In `tests/test_scan_snapshot.py`, the old `test_quicktime_frame_rate_parser_reads_average_fps` in `ScanSnapshotTest` still references `_quicktime_frame_rate`. Delete that test — it is replaced by `QuicktimeVideoInfoTest.test_reads_fps_and_dimensions_landscape`.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_scan_snapshot.py::QuicktimeVideoInfoTest tests/test_scan_snapshot.py::VideoClassificationTest -v
```

Expected: All green.

- [ ] **Step 7: Commit**

```bash
git add Structura.py tests/test_scan_snapshot.py
git commit -m "feat: replace _quicktime_frame_rate with _quicktime_video_info (tkhd atoms + mdls fallback)"
```

---

## Chunk 3: Column constants, TreeItemMetadata, and all callsite updates (atomic)

> **Important:** Column constant renumbering and all callsite updates MUST be committed together. Do not commit partial changes — any intermediate state will produce `NameError` on `TREE_COLUMN_TYPE` and `TREE_COLUMN_ITEMS`.

### Task 3: Renumber columns, update TreeItemMetadata, fix all callsites

**Files:**
- Modify: `Structura.py` — column constants (~line 298), TREE_HEADERS, TREE_COLUMN_WIDTHS, TreeItemMetadata (~line 2390), `_apply_tree_item_metadata` (~line 2444), `_sort_tree_data` (~line 2551), MetadataWorker (~line 3495)

- [ ] **Step 1: Write failing test for new column layout**

Add to `tests/test_scan_snapshot.py::DashboardBehaviorTest`:

```python
def test_tree_has_ten_columns_with_new_headers(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "clip.mov").write_bytes(b"x" * 100)

        snapshot = scan_folder(root)
        pane = FolderTreePane()
        pane.set_snapshot(snapshot)

        header = pane._tree.headerItem()
        self.assertEqual(header.columnCount(), 10)
        self.assertEqual(header.text(0), "Title")
        self.assertEqual(header.text(1), "File Size")
        self.assertEqual(header.text(2), "Resolution")
        self.assertEqual(header.text(3), "Frame Rate")
        self.assertEqual(header.text(4), "Orientation")
        self.assertEqual(header.text(5), "GPS")
        self.assertEqual(header.text(6), "Make")
        self.assertEqual(header.text(7), "Model")
        self.assertEqual(header.text(8), "Date Created")
        self.assertEqual(header.text(9), "Date Modified")
        pane.deleteLater()

def test_folder_title_includes_item_count(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        sub = root / "Footage"
        sub.mkdir()
        (sub / "clip.mov").write_bytes(b"x" * 100)
        (sub / "hero.jpg").write_bytes(b"x" * 50)

        snapshot = scan_folder(root)
        pane = FolderTreePane()
        pane.set_snapshot(snapshot)

        item = pane._tree.topLevelItem(0)
        title_text = item.text(0)
        self.assertIn("Footage", title_text)
        self.assertIn("(2)", title_text)
        pane.deleteLater()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_scan_snapshot.py::DashboardBehaviorTest::test_tree_has_ten_columns_with_new_headers -v
```

Expected: FAIL — headers are wrong (still old layout).

- [ ] **Step 3: Replace column constants in Structura.py**

Find lines 298–331 and replace the entire block:

```python
TREE_COLUMN_TITLE = 0
TREE_COLUMN_SIZE = 1
TREE_COLUMN_RESOLUTION = 2
TREE_COLUMN_FRAME_RATE = 3
TREE_COLUMN_ORIENTATION = 4
TREE_COLUMN_GPS = 5
TREE_COLUMN_MAKE = 6
TREE_COLUMN_MODEL = 7
TREE_COLUMN_CREATED = 8
TREE_COLUMN_MODIFIED = 9
TREE_HEADERS = (
    "Title",
    "File Size",
    "Resolution",
    "Frame Rate",
    "Orientation",
    "GPS",
    "Make",
    "Model",
    "Date Created",
    "Date Modified",
)
TREE_COLUMN_WIDTHS = (
    (TREE_COLUMN_TITLE, 280),
    (TREE_COLUMN_SIZE, 110),
    (TREE_COLUMN_RESOLUTION, 70),
    (TREE_COLUMN_FRAME_RATE, 80),
    (TREE_COLUMN_ORIENTATION, 80),
    (TREE_COLUMN_GPS, 50),
    (TREE_COLUMN_MAKE, 50),
    (TREE_COLUMN_MODEL, 160),
    (TREE_COLUMN_CREATED, 118),
    (TREE_COLUMN_MODIFIED, 118),
)
```

- [ ] **Step 4: Update TreeItemMetadata dataclass**

Find `TreeItemMetadata` (~line 2390) and replace:

```python
@dataclass(frozen=True)
class TreeItemMetadata:
    type_label: str
    created_ts: float | None
    modified_ts: float | None
    video_info: "VideoInfo | None"     # replaces frame_rate + frame_rate_text
    created_text: str
    modified_text: str
    size_text: str
```

- [ ] **Step 5: Update _tree_item_metadata**

Find `_tree_item_metadata` (~line 2420) and replace:

```python
def _tree_item_metadata(
    path_str: str,
    *,
    is_dir: bool,
    ext: str,
    size_bytes: int,
) -> TreeItemMetadata:
    created_ts, modified_ts, video_info = _file_browser_metadata(
        path_str,
        is_dir=is_dir,
        ext=ext,
    )
    return TreeItemMetadata(
        type_label=_tree_item_type_label(is_dir=is_dir, ext=ext),
        created_ts=created_ts,
        modified_ts=modified_ts,
        video_info=video_info,
        created_text=_format_browser_date(created_ts),
        modified_text=_format_browser_date(modified_ts),
        size_text=_human_size(size_bytes) if size_bytes else "—",
    )
```

- [ ] **Step 6: Add display formatter helpers (insert before _apply_tree_item_metadata)**

Insert these helper functions before `_apply_tree_item_metadata`:

```python
def _format_frame_rate_display(video_info: "VideoInfo | None") -> str:
    if video_info is None:
        return ""
    if video_info.fps_category is None:
        # Slo-mo: show rounded integer
        if video_info.raw_fps is not None:
            return str(round(video_info.raw_fps))
        return ""
    scissors = " ✂️" if video_info.is_edited else ""
    return f"{video_info.fps_category}{scissors}"


def _format_frame_rate_tooltip(video_info: "VideoInfo | None") -> str:
    if video_info is None or video_info.raw_fps is None:
        return ""
    fps = video_info.raw_fps
    rounded = round(fps)
    if abs(fps - rounded) < 0.01:
        return f"{rounded:d} fps"
    return f"{fps:.2f} fps"


def _format_gps_display(gps: str | None) -> str:
    return "🌍" if gps else "❌"


def _format_make_display(make: str | None) -> str:
    if not make:
        return "❌"
    return "🍎" if "apple" in make.lower() else "❌"


def _format_model_display(model: str | None) -> str:
    if not model:
        return "—"
    if "iphone" in model.lower():
        return f"📱 {model}"
    return model
```

- [ ] **Step 7: Rewrite _apply_tree_item_metadata**

Find `_apply_tree_item_metadata` (~line 2444) and replace the entire function:

```python
def _apply_tree_item_metadata(
    item: QTreeWidgetItem,
    *,
    name: str,
    path_str: str,
    size_bytes: int,
    metadata: TreeItemMetadata,
    folder_item_count: int = 0,
) -> None:
    _ext_key = f".{metadata.type_label.lower()}"
    _is_video = _ext_key in VIDEO_EXTENSIONS
    _is_media = _is_video or _ext_key in IMAGE_EXTENSIONS

    # Title: append item count for folders
    if metadata.type_label == "folder" and folder_item_count > 0:
        current_title = item.text(TREE_COLUMN_TITLE)
        item.setText(TREE_COLUMN_TITLE, f"{current_title} ({folder_item_count})")

    item.setText(TREE_COLUMN_SIZE, metadata.size_text)
    item.setText(TREE_COLUMN_CREATED, metadata.created_text)
    item.setText(TREE_COLUMN_MODIFIED, metadata.modified_text)

    # Video-only columns
    vi = metadata.video_info
    if _is_video and vi is not None:
        item.setText(TREE_COLUMN_RESOLUTION, vi.resolution)
        item.setText(TREE_COLUMN_FRAME_RATE, _format_frame_rate_display(vi))
        item.setText(TREE_COLUMN_ORIENTATION, vi.orientation)
        item.setToolTip(TREE_COLUMN_FRAME_RATE, _format_frame_rate_tooltip(vi))
    else:
        item.setText(TREE_COLUMN_RESOLUTION, "")
        item.setText(TREE_COLUMN_FRAME_RATE, "")
        item.setText(TREE_COLUMN_ORIENTATION, "")

    # Alignment
    for col in (TREE_COLUMN_SIZE, TREE_COLUMN_FRAME_RATE):
        item.setData(col, Qt.TextAlignmentRole, int(Qt.AlignRight | Qt.AlignVCenter))

    item.setData(TREE_COLUMN_TITLE, Qt.UserRole, path_str)
    if path_str:
        item.setToolTip(TREE_COLUMN_TITLE, path_str)
    item.setToolTip(TREE_COLUMN_CREATED, _format_browser_datetime(metadata.created_ts))
    item.setToolTip(TREE_COLUMN_MODIFIED, _format_browser_datetime(metadata.modified_ts))

    # Sort keys stored via TREE_SORT_ROLE
    name_key = sanitize_name(name).casefold()
    size_key = (size_bytes == 0, size_bytes, name_key)
    created_key = (metadata.created_ts is None, metadata.created_ts or 0.0, name_key)
    modified_key = (metadata.modified_ts is None, metadata.modified_ts or 0.0, name_key)
    resolution_key = (vi is None, 0 if vi is None else vi.width * vi.height, name_key)
    fps_key = (vi is None or vi.raw_fps is None,
               vi.raw_fps if vi and vi.raw_fps else 0.0, name_key)
    orient_key = (vi is None, vi.orientation if vi else "", name_key)

    item.setData(TREE_COLUMN_TITLE, TREE_SORT_ROLE, (False, name_key))
    item.setData(TREE_COLUMN_SIZE, TREE_SORT_ROLE, size_key)
    item.setData(TREE_COLUMN_RESOLUTION, TREE_SORT_ROLE, resolution_key)
    item.setData(TREE_COLUMN_FRAME_RATE, TREE_SORT_ROLE, fps_key)
    item.setData(TREE_COLUMN_ORIENTATION, TREE_SORT_ROLE, orient_key)
    item.setData(TREE_COLUMN_CREATED, TREE_SORT_ROLE, created_key)
    item.setData(TREE_COLUMN_MODIFIED, TREE_SORT_ROLE, modified_key)

    # GPS / Make / Model — pre-fill with em-dash; MetadataWorker fills real values
    if _is_media:
        item.setText(TREE_COLUMN_GPS, "\u2014")
        item.setText(TREE_COLUMN_MAKE, "\u2014")
        item.setText(TREE_COLUMN_MODEL, "\u2014")
    else:
        item.setText(TREE_COLUMN_GPS, "")
        item.setText(TREE_COLUMN_MAKE, "")
        item.setText(TREE_COLUMN_MODEL, "")
```

- [ ] **Step 8: Update _sort_tree_data (remove TREE_COLUMN_TYPE branch)**

Find `_sort_tree_data` (~line 2551) and replace:

```python
def _sort_tree_data(data: list, column: int, ascending: bool) -> list:
    """Sort tree_data recursively in Python — avoids Qt's C++→Python __lt__ dispatch."""
    def key_fn(entry):
        name, is_dir, _children, _path, size_bytes, ext = entry
        name_k = sanitize_name(name).casefold()
        if column == TREE_COLUMN_SIZE:
            return (size_bytes == 0, size_bytes, name_k)
        # Title, dates, Resolution, Frame Rate, Orientation — sort by name only at
        # the tree_data level; per-item TREE_SORT_ROLE handles precise item-level sort.
        return (name_k,)

    folders = [e for e in data if e[1]]
    files = [e for e in data if not e[1]]
    sorted_folders = sorted(folders, key=key_fn, reverse=not ascending)
    sorted_files = sorted(files, key=key_fn, reverse=not ascending)
    result = sorted_folders + sorted_files
    return [
        (name, is_dir, _sort_tree_data(children, column, ascending), path, size, ext)
        for name, is_dir, children, path, size, ext in result
    ]
```

- [ ] **Step 9: Verify _style_tree_item_title needs no changes**

Open `_style_tree_item_title` (~line 2402). Confirm it only references `TREE_COLUMN_TITLE` (no `TREE_COLUMN_TYPE` or `TREE_COLUMN_ITEMS`). No edits required — it is clean.

- [ ] **Step 10: Fix folder detection in MetadataWorker (line ~3495)**

Find the line:
```python
if item.text(TREE_COLUMN_TYPE).startswith("📁"):
```

Replace with:
```python
if item.text(TREE_COLUMN_TITLE).startswith("📁"):
```

- [ ] **Step 11: Update MetadataWorker GPS/Make/Model display to use emoji formatters**

Find where MetadataWorker applies EXIF results to tree items (search for `item.setText(TREE_COLUMN_GPS` in the MetadataWorker chunk_ready handler). Replace that block with:

```python
item.setText(TREE_COLUMN_GPS, _format_gps_display(exif.gps))
item.setToolTip(TREE_COLUMN_GPS, exif.gps or "")
item.setText(TREE_COLUMN_MAKE, _format_make_display(exif.make))
item.setToolTip(TREE_COLUMN_MAKE, exif.make or "")
item.setText(TREE_COLUMN_MODEL, _format_model_display(exif.model))
item.setToolTip(TREE_COLUMN_MODEL, exif.model or "")
```

- [ ] **Step 12: Fix old test assertions with stale column indices**

In `test_folder_tree_pane_sorts_by_size_without_duplicate_root_row`, replace:
```python
self.assertEqual(pane._tree.headerItem().text(2), "Items")
self.assertEqual(pane._tree.headerItem().text(3), "File Size")
self.assertEqual(pane._tree.headerItem().text(4), "Frame Rate")
self.assertEqual(pane._tree.headerItem().text(8), "Date Created")
self.assertEqual(pane._tree.headerItem().text(9), "Date Modified")
# ...
pane._on_header_clicked(3)  # sort by size
pane._on_header_clicked(3)
```

With:
```python
self.assertEqual(pane._tree.headerItem().text(1), "File Size")
self.assertEqual(pane._tree.headerItem().text(2), "Resolution")
self.assertEqual(pane._tree.headerItem().text(3), "Frame Rate")
self.assertEqual(pane._tree.headerItem().text(8), "Date Created")
self.assertEqual(pane._tree.headerItem().text(9), "Date Modified")
# ...
pane._on_header_clicked(1)  # sort by size (now index 1)
pane._on_header_clicked(1)
```

- [ ] **Step 13: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All green.

- [ ] **Step 14: Commit**

```bash
git add Structura.py tests/test_scan_snapshot.py
git commit -m "feat: renumber columns, update tree display, folder counts in title, emoji GPS/Make/Model"
```

---

## Chunk 4: Dashboard tiles

### Task 4: Update dashboard file header tiles

**Files:**
- Modify: `Structura.py` — `AnalyzerDashboard` file header (~line 3710), `_update_header_and_tiles` (~line 3974)

- [ ] **Step 1: Replace "Type" tile with "Resolution" tile**

Find the tile construction block (~line 3710):
```python
_type_frame, self._fh_type_val = _make_info_tile("Type")
_size_frame, self._fh_size_val = _make_info_tile("Size")
_fps_frame, self._fh_fps_val = _make_info_tile("Frame Rate")
_fh_tiles_layout.addWidget(_type_frame, 1)
_fh_tiles_layout.addWidget(_size_frame, 1)
_fh_tiles_layout.addWidget(_fps_frame, 1)
```

Replace with:
```python
_resolution_frame, self._fh_resolution_val = _make_info_tile("Resolution")
_size_frame, self._fh_size_val = _make_info_tile("Size")
_fps_frame, self._fh_fps_val = _make_info_tile("Frame Rate")
_fh_tiles_layout.addWidget(_resolution_frame, 1)
_fh_tiles_layout.addWidget(_size_frame, 1)
_fh_tiles_layout.addWidget(_fps_frame, 1)
```

- [ ] **Step 2: Update _update_header_and_tiles to use VideoInfo**

Find `_update_header_and_tiles` (~line 3974). In the `if not stats.is_dir:` branch, the complete existing block to replace is:

```python
# OLD — replace this entire block (lines ~3977–3997):
ext = Path(stats.path).suffix.lower()
emoji = file_emoji(ext, is_dir=False)
created_ts, _, frame_rate = _file_browser_metadata(
    stats.path, is_dir=False, ext=ext
)
meta_text = (
    f"{emoji} {ext.lstrip('.').upper()} · {_format_browser_date(created_ts)}"
    if ext else f"{emoji} · {_format_browser_date(created_ts)}"
)
self._fh_meta_label.setText(meta_text)
fm = self._fh_name_label.fontMetrics()
truncated = fm.elidedText(
    sanitize_name(stats.name), Qt.ElideRight, PATH_LABEL_MAX_WIDTH
)
self._fh_name_label.setText(truncated)
self._fh_name_label.setToolTip(stats.name)
self._fh_type_val.setText(ext.lstrip(".").upper() or "—")
self._fh_size_val.setText(
    _human_size(stats.total_size_bytes) if stats.total_size_bytes else "—"
)
self._fh_fps_val.setText(_format_frame_rate(frame_rate))
```

Replace with:

```python
ext = Path(stats.path).suffix.lower()
emoji = file_emoji(ext, is_dir=False)
created_ts, _, video_info = _file_browser_metadata(
    stats.path, is_dir=False, ext=ext
)
meta_text = (
    f"{emoji} {ext.lstrip('.').upper()} · {_format_browser_date(created_ts)}"
    if ext else f"{emoji} · {_format_browser_date(created_ts)}"
)
self._fh_meta_label.setText(meta_text)
fm = self._fh_name_label.fontMetrics()
truncated = fm.elidedText(
    sanitize_name(stats.name), Qt.ElideRight, PATH_LABEL_MAX_WIDTH
)
self._fh_name_label.setText(truncated)
self._fh_name_label.setToolTip(stats.name)
self._fh_resolution_val.setText(
    video_info.resolution if video_info is not None else "—"
)
self._fh_size_val.setText(
    _human_size(stats.total_size_bytes) if stats.total_size_bytes else "—"
)
if video_info is not None:
    self._fh_fps_val.setText(_format_frame_rate_display(video_info))
    self._fh_fps_val.setToolTip(_format_frame_rate_tooltip(video_info))
else:
    self._fh_fps_val.setText("—")
    self._fh_fps_val.setToolTip("")
```

- [ ] **Step 3: Remove the old _format_frame_rate function**

Search for `def _format_frame_rate(` (~line 884) and delete the entire function — it is now replaced by `_format_frame_rate_display` and `_format_frame_rate_tooltip`.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All green.

- [ ] **Step 5: Smoke test — launch the app**

```bash
python src/main.py
```

Verify:
- App opens without errors or tracebacks
- Tree shows 10 columns: Title, File Size, Resolution, Frame Rate, Orientation, GPS, Make, Model, Date Created, Date Modified
- Drag in a folder with `.mov`/`.mp4` files → Resolution (e.g. `1080p`), Frame Rate (e.g. `30` or `30 ✂️`), Orientation (`V`/`W`) populate
- Folders show `📁 FolderName (N)` in Title column
- GPS/Make/Model show 🌍/🍎/📱 or ❌ after metadata loads
- Selecting a video file in the right panel shows Resolution tile (e.g. `4K`) instead of Type tile

- [ ] **Step 6: Final commit**

```bash
git add Structura.py
git commit -m "feat: dashboard Resolution tile, Frame Rate category display, remove _format_frame_rate"
```

---

## Summary of all changes

| File | What changed |
|---|---|
| `Structura.py` | `import math` added to top-level imports |
| `Structura.py` | `VideoInfo` dataclass added after `FileExif` (~line 727) |
| `Structura.py` | `_classify_resolution()` and `_classify_fps()` added |
| `Structura.py` | `_quicktime_tkhd_dimensions()` — reads width/height/rotation from tkhd |
| `Structura.py` | `_quicktime_video_info()` — replaces `_quicktime_frame_rate()`, has `@lru_cache` |
| `Structura.py` | `_mdls_video_dimensions()` — mdls fallback for pixel dimensions |
| `Structura.py` | `_file_browser_metadata()` — returns `VideoInfo` instead of `float` |
| `Structura.py` | Column constants renumbered; `TREE_COLUMN_TYPE`, `TREE_COLUMN_ITEMS` removed; `TREE_COLUMN_RESOLUTION`, `TREE_COLUMN_ORIENTATION` added |
| `Structura.py` | `TreeItemMetadata` — `video_info` replaces `frame_rate`/`frame_rate_text` |
| `Structura.py` | `_tree_item_metadata()` — populates `video_info` |
| `Structura.py` | `_format_frame_rate_display/tooltip`, `_format_gps_display`, `_format_make_display`, `_format_model_display` added |
| `Structura.py` | `_format_frame_rate()` removed |
| `Structura.py` | `_apply_tree_item_metadata()` — full rewrite for new columns with TREE_SORT_ROLE keys |
| `Structura.py` | `_sort_tree_data()` — `TREE_COLUMN_TYPE` branch removed |
| `Structura.py` | MetadataWorker folder detection — `TREE_COLUMN_TYPE` → `TREE_COLUMN_TITLE` |
| `Structura.py` | MetadataWorker GPS/Make/Model — emoji formatters applied |
| `Structura.py` | Dashboard tiles — Resolution replaces Type |
| `Structura.py` | `_update_header_and_tiles()` — uses `VideoInfo` for tile values |
| `tests/test_scan_snapshot.py` | `VideoClassificationTest` — new |
| `tests/test_scan_snapshot.py` | `QuicktimeVideoInfoTest` — new (replaces old frame rate test) |
| `tests/test_scan_snapshot.py` | `DashboardBehaviorTest` — updated column indices, new header/folder-count tests |
