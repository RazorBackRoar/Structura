import math
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from Structura import (
    AnalyzerDashboard,
    FolderTreePane,
    ScanWorker,
    SortWorker,
    StructuraWindow,
    SubtreeStats,
    _classify_resolution,
    _classify_fps,
    _quicktime_video_info,
    _display_folder_count,
    extension_color,
    file_emoji,
    _human_size,
    collect_sortable_extensions,
    scan_folder,
)


def _require_snapshot(snapshot):
    assert snapshot is not None
    return snapshot


def _require_video_info(info):
    assert info is not None
    return info


class ScanErrorHandlingTest(unittest.TestCase):
    def test_scan_folder_handles_oserror_without_strerror(self):
        root = Path("/tmp")
        with patch.object(Path, "iterdir", side_effect=OSError()):
            snapshot = _require_snapshot(scan_folder(root))

        self.assertEqual(snapshot.warnings, [f"Unknown error: {root}"])
        self.assertEqual(snapshot.tree_data, [("⚠ Unknown error", False, [], "", 0, "")])


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self):
        for callback in list(self._callbacks):
            callback()


class _FakeWorker:
    def __init__(self):
        self.finished = _FakeSignal()
        self.cancelled = False
        self.deleted = False
        self.wait_calls = []

    def cancel(self):
        self.cancelled = True

    def isFinished(self):
        return False

    def wait(self, timeout):
        self.wait_calls.append(timeout)
        return True

    def deleteLater(self):
        self.deleted = True


class WorkerLifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_retire_worker_keeps_reference_until_finished(self):
        pane = FolderTreePane()
        worker = _FakeWorker()
        pane_state = cast(Any, pane)

        pane_state._retire_worker(worker)

        self.assertTrue(worker.cancelled)
        self.assertIn(worker, pane_state._retired_workers)

        worker.finished.emit()

        self.assertNotIn(worker, pane_state._retired_workers)
        self.assertTrue(worker.deleted)
        pane.deleteLater()

    def test_shutdown_workers_cancels_waits_and_clears_all_worker_refs(self):
        pane = FolderTreePane()
        active = _FakeWorker()
        expansion = _FakeWorker()
        retired = _FakeWorker()
        pane_state = cast(Any, pane)
        pane_state._metadata_worker = active
        pane_state._expansion_workers = [expansion]
        pane_state._retired_workers = [retired]

        pane_state._shutdown_workers()

        self.assertIsNone(pane_state._metadata_worker)
        self.assertEqual(pane_state._expansion_workers, [])
        self.assertEqual(pane_state._retired_workers, [])
        for worker in (active, expansion, retired):
            self.assertTrue(worker.cancelled)
            self.assertEqual(worker.wait_calls, [1000])
            self.assertTrue(worker.deleted)
        pane.deleteLater()

    def test_delete_later_shuts_down_workers(self):
        pane = FolderTreePane()
        worker = _FakeWorker()
        pane_state = cast(Any, pane)
        pane_state._metadata_worker = worker

        pane.deleteLater()

        self.assertIsNone(pane_state._metadata_worker)
        self.assertTrue(worker.cancelled)
        self.assertEqual(worker.wait_calls, [1000])
        self.assertTrue(worker.deleted)

    def test_scan_worker_emits_folder_payloads_for_multiple_paths(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            (first / "a.txt").write_text("a", encoding="utf-8")
            (second / "b.txt").write_text("b", encoding="utf-8")

            payloads: list[tuple[int, Path, dict[str, int], list, list[str]]] = []
            worker = ScanWorker([first, second], include_hidden=True)
            worker.folder_ready.connect(
                lambda index, folder_path, ext_counts, tree_data, warnings: payloads.append(
                    (index, cast(Path, folder_path), ext_counts, tree_data, warnings)
                )
            )

            worker.run()

            self.assertEqual([payload[0] for payload in payloads], [1, 2])
            self.assertEqual([payload[1] for payload in payloads], [first, second])
            self.assertEqual(payloads[0][2], {".txt": 1})
            self.assertEqual(payloads[1][2], {".txt": 1})


class WindowLifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_window_close_cleans_up_background_workers(self):
        win = StructuraWindow()
        scan_worker = _FakeWorker()
        sort_worker = _FakeWorker()
        metadata_worker = _FakeWorker()
        expansion_worker = _FakeWorker()
        retired_worker = _FakeWorker()
        win_state = cast(Any, win)
        tree_pane_state = cast(Any, win._tree_pane)

        win_state._worker = scan_worker
        win_state._sort_worker = sort_worker
        tree_pane_state._metadata_worker = metadata_worker
        tree_pane_state._expansion_workers = [expansion_worker]
        tree_pane_state._retired_workers = [retired_worker]

        win.show()
        self._app.processEvents()
        win.close()
        self._app.processEvents()

        self.assertIsNone(win_state._worker)
        self.assertIsNone(win_state._sort_worker)
        self.assertIsNone(tree_pane_state._metadata_worker)
        self.assertEqual(tree_pane_state._expansion_workers, [])
        self.assertEqual(tree_pane_state._retired_workers, [])
        for worker in (
            scan_worker,
            sort_worker,
            metadata_worker,
            expansion_worker,
            retired_worker,
        ):
            self.assertTrue(worker.cancelled)
            self.assertEqual(worker.wait_calls, [1000])
            self.assertTrue(worker.deleted)
        win.deleteLater()


class ScanSnapshotTest(unittest.TestCase):
    def test_human_size_uses_macos_decimal_units(self):
        self.assertEqual(_human_size(10_200_564_382), "10.2 GB")
        self.assertEqual(_human_size(999), "999 B")
        self.assertEqual(_human_size(1_500), "1.5 KB")

    def test_display_folder_count_includes_selected_folder(self):
        self.assertEqual(
            _display_folder_count(
                SubtreeStats(path="/tmp/demo", name="demo", is_dir=True, total_dirs=1)
            ),
            1,
        )

    def test_extension_color_maps_common_formats(self):
        self.assertEqual(extension_color(".mov"), "#3b63f0")
        self.assertEqual(extension_color(".mp4"), "#d9485f")
        self.assertEqual(extension_color(".jpeg"), "#d4a017")
        self.assertEqual(extension_color(".heic"), "#2f9e5f")
        self.assertEqual(extension_color(".png"), "#8b5e3c")

    def test_file_emoji_skips_unknown_file_fallback_icon(self):
        self.assertEqual(file_emoji(".unknown", False), "")

    def test_scan_folder_returns_recursive_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "Documents"
            nested = docs / "Reports"
            docs.mkdir()
            nested.mkdir()
            (root / "notes.txt").write_text("root note", encoding="utf-8")
            (docs / "image.jpg").write_bytes(b"jpeg")
            (nested / "script.py").write_text("print('hi')", encoding="utf-8")

            snapshot = _require_snapshot(scan_folder(root))

            self.assertEqual(snapshot.root_path, root)
            self.assertEqual(snapshot.total_files, 3)
            self.assertEqual(snapshot.total_dirs, 2)
            self.assertEqual(
                snapshot.ext_counts,
                {".jpg": 1, ".py": 1, ".txt": 1},
            )
            self.assertGreater(snapshot.total_size_bytes, 0)

    def test_scan_folder_honors_hidden_toggle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".secret.txt").write_text("hidden", encoding="utf-8")
            (root / "visible.txt").write_text("visible", encoding="utf-8")

            hidden_off = _require_snapshot(scan_folder(root, include_hidden=False))
            hidden_on = _require_snapshot(scan_folder(root, include_hidden=True))

            self.assertEqual(hidden_off.total_files, 1)
            self.assertEqual(hidden_off.ext_counts, {".txt": 1})
            self.assertEqual(hidden_on.total_files, 2)
            self.assertEqual(hidden_on.ext_counts, {".txt": 2})

    def test_scan_folder_ignores_macos_custom_icon_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Icon\r").write_bytes(b"")
            (root / "visible.jpg").write_bytes(b"jpg")

            snapshot = _require_snapshot(scan_folder(root, include_hidden=True))
            preview = collect_sortable_extensions(
                root,
                include_hidden=True,
                media_mode="both",
            )

            self.assertEqual(snapshot.total_files, 1)
            self.assertEqual(snapshot.ext_counts, {".jpg": 1})
            self.assertEqual(preview.total_sortable, 1)
            self.assertEqual(preview.skipped_other, 0)

    def test_scan_folder_tracks_subtree_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shots = root / "Shots"
            dailies = shots / "Dailies"
            shots.mkdir()
            dailies.mkdir()
            (shots / "hero.jpg").write_bytes(b"12345")
            (dailies / "take.mov").write_bytes(b"1234567")

            snapshot = _require_snapshot(scan_folder(root))
            subtree = snapshot.stats_by_path[str(shots)]

            self.assertTrue(subtree.is_dir)
            self.assertEqual(subtree.total_files, 2)
            self.assertEqual(subtree.total_dirs, 2)
            self.assertEqual(subtree.ext_counts, {".jpg": 1, ".mov": 1})
            self.assertGreater(subtree.total_size_bytes, 0)


class SortBehaviorTest(unittest.TestCase):
    def test_collect_sortable_extensions_counts_recursively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sub = root / "Nested"
            sub.mkdir()
            (root / "hero.jpg").write_bytes(b"jpg")
            (sub / "clip.mov").write_bytes(b"mov")

            preview = collect_sortable_extensions(root, include_hidden=True, media_mode="both")

            self.assertEqual(preview.ext_counts, {".jpg": 1, ".mov": 1})

    def test_sort_worker_organizes_recursively_respecting_media_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "Nested"
            nested.mkdir()
            (root / "hero.jpg").write_bytes(b"jpg")
            (root / "clip.mov").write_bytes(b"mov")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")
            (nested / "nested.png").write_bytes(b"png")

            payload: list[tuple[dict[str, int], list[str]]] = []
            worker = SortWorker(root, include_hidden=True, media_mode="images")
            worker.sort_done.connect(lambda moved, errors: payload.append((moved, errors)))
            worker.run()

            self.assertEqual(len(payload), 1)
            moved_counts, errors = payload[0]
            self.assertEqual(errors, [])
            # Both root jpg and nested png should be organized (images mode)
            self.assertEqual(moved_counts, {".jpg": 1, ".png": 1})
            self.assertTrue((root / "JPG" / "hero.jpg").is_file())
            self.assertTrue((root / "clip.mov").is_file())  # video untouched
            self.assertTrue((nested / "PNG" / "nested.png").is_file())
            self.assertTrue((root / "notes.txt").is_file())


class DashboardBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_folder_tree_pane_sorts_by_size_without_duplicate_root_row(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "small.mov").write_bytes(b"a" * 100)
            (root / "large.mp4").write_bytes(b"b" * 1_000)

            snapshot = _require_snapshot(scan_folder(root))
            pane = FolderTreePane()
            pane.set_snapshot(snapshot)

            self.assertEqual(pane._tree.topLevelItemCount(), len(snapshot.tree_data))
            self.assertEqual(pane._tree.headerItem().text(1), "File Size")
            self.assertEqual(pane._tree.headerItem().text(2), "Resolution")
            self.assertEqual(pane._tree.headerItem().text(3), "Frame Rate")
            self.assertEqual(pane._tree.headerItem().text(9), "Date Created")
            self.assertEqual(pane._tree.headerItem().text(10), "Date Modified")

            # Trigger size-descending sort via the header-click handler
            pane._on_header_clicked(1)  # first click: sort by size ascending
            pane._on_header_clicked(1)  # second click: toggle to descending
            first_item = pane._tree.topLevelItem(0)
            assert first_item is not None

            self.assertEqual(first_item.data(0, Qt.UserRole), str(root / "large.mp4"))
            pane.deleteLater()

    def test_file_inspector_context_shows_root_totals_when_file_selected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sub = root / "Sub"
            sub.mkdir()
            (root / "a.mov").write_bytes(b"x" * 100)
            (root / "b.mov").write_bytes(b"x" * 200)
            (sub / "c.jpg").write_bytes(b"x" * 50)

            snapshot = _require_snapshot(scan_folder(root))
            file_stats = snapshot.stats_by_path[str(root / "a.mov")]

            dashboard = AnalyzerDashboard()
            dashboard.set_snapshot(
                snapshot,
                file_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=True,
            )

            self.assertIn("3 files", dashboard._inspector_context_label.text())
            self.assertIn("1 folder", dashboard._inspector_context_label.text())
            dashboard.deleteLater()

    def test_extension_filter_persists_across_selection_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "hero.mov").write_bytes(b"mov-a")
            (root / "clip.mov").write_bytes(b"mov-b")
            (root / "still.png").write_bytes(b"png")

            snapshot = _require_snapshot(scan_folder(root))
            root_stats = snapshot.stats_by_path[str(root)]
            file_stats = snapshot.stats_by_path[str(root / "hero.mov")]

            dashboard = AnalyzerDashboard()
            dashboard.set_snapshot(
                snapshot,
                root_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=True,
            )

            mov_index = dashboard._extension_filter.findData(".mov")
            self.assertGreaterEqual(mov_index, 0)
            dashboard._extension_filter.setCurrentIndex(mov_index)
            self.assertEqual(dashboard._extension_filter.currentData(), ".mov")

            dashboard.set_snapshot(
                snapshot,
                file_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=False,
            )

            self.assertEqual(dashboard._extension_filter.currentData(), ".mov")
            dashboard.deleteLater()

    def test_extension_filter_shows_clean_extension_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "hero.jpg").write_bytes(b"jpg")
            (root / "clip.mp4").write_bytes(b"mp4")

            snapshot = _require_snapshot(scan_folder(root))
            root_stats = snapshot.stats_by_path[str(root)]

            dashboard = AnalyzerDashboard()
            dashboard.set_snapshot(
                snapshot,
                root_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=True,
            )

            jpg_index = dashboard._extension_filter.findData(".jpg")
            mp4_index = dashboard._extension_filter.findData(".mp4")

            self.assertGreaterEqual(jpg_index, 0)
            self.assertGreaterEqual(mp4_index, 0)
            self.assertEqual(dashboard._extension_filter.itemText(jpg_index), "JPG")
            self.assertEqual(dashboard._extension_filter.itemText(mp4_index), "MP4")
            dashboard.deleteLater()

    def test_sort_section_shows_destination_folder_chips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "hero.jpg").write_bytes(b"jpg")
            (root / "clip.mp4").write_bytes(b"mp4")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")

            snapshot = _require_snapshot(scan_folder(root))
            root_stats = snapshot.stats_by_path[str(root)]

            dashboard = AnalyzerDashboard()
            dashboard.show()
            dashboard.set_snapshot(
                snapshot,
                root_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=True,
            )
            self._app.processEvents()

            self.assertTrue(dashboard._sort_targets_host.isVisible())
            chip_text = {label.text() for label in dashboard._sort_targets_host.findChildren(QLabel)}
            self.assertIn("JPG", chip_text)
            self.assertIn("MP4", chip_text)
            dashboard.deleteLater()

    def test_file_header_row_shown_for_file_selection_hidden_for_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sub = root / "Footage"
            sub.mkdir()
            (root / "clip.mov").write_bytes(b"x" * 500)

            snapshot = _require_snapshot(scan_folder(root))
            file_stats = snapshot.stats_by_path[str(root / "clip.mov")]
            folder_stats = snapshot.stats_by_path[str(sub)]

            dashboard = AnalyzerDashboard()
            dashboard.show()

            # File selected → inspector visible, overview hidden
            dashboard.set_snapshot(snapshot, file_stats,
                                   include_hidden=True, media_mode="both",
                                   reset_filter=True)
            self.assertTrue(dashboard._file_header_row.isVisible())
            self.assertTrue(dashboard._file_inspector.isVisible())
            self.assertFalse(dashboard._overview_surface.isVisible())
            self.assertFalse(dashboard._action_section.isVisible())

            # Folder selected → overview visible, inspector hidden
            dashboard.set_snapshot(snapshot, folder_stats,
                                   include_hidden=True, media_mode="both",
                                   reset_filter=False)
            self.assertFalse(dashboard._file_inspector.isVisible())
            self.assertTrue(dashboard._selection_title.isVisible())
            self.assertTrue(dashboard._overview_surface.isVisible())
            self.assertTrue(dashboard._action_section.isVisible())

            dashboard.deleteLater()

    def test_file_inspector_preview_panel_shows_extension_and_kind(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clip_path = root / "clip.mp4"
            clip_path.write_bytes(b"x" * 500)

            snapshot = _require_snapshot(scan_folder(root))
            file_stats = snapshot.stats_by_path[str(clip_path)]

            dashboard = AnalyzerDashboard()
            dashboard.set_snapshot(
                snapshot,
                file_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=True,
            )

            self.assertEqual(dashboard._fh_preview_badge.text(), "MP4")
            self.assertEqual(dashboard._fh_preview_caption.text(), "Video file")
            self.assertEqual(dashboard._fh_preview_detail.text(), "500 B")
            dashboard.deleteLater()

    def test_tree_has_ten_columns_with_new_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "clip.mov").write_bytes(b"x" * 100)

            snapshot = _require_snapshot(scan_folder(root))
            pane = FolderTreePane()
            pane.set_snapshot(snapshot)

            header = pane._tree.headerItem()
            self.assertEqual(header.columnCount(), 11)
            self.assertEqual(header.text(0), "Title")
            self.assertEqual(header.text(1), "File Size")
            self.assertEqual(header.text(2), "Resolution")
            self.assertEqual(header.text(3), "Frame Rate")
            self.assertEqual(header.text(4), "✂️")
            self.assertEqual(header.text(5), "Orientation")
            self.assertEqual(header.text(6), "GPS")
            self.assertEqual(header.text(7), "Make")
            self.assertEqual(header.text(8), "Model")
            self.assertEqual(header.text(9), "Date Created")
            self.assertEqual(header.text(10), "Date Modified")
            pane.deleteLater()

    def test_folder_title_includes_item_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sub = root / "Footage"
            sub.mkdir()
            (sub / "clip.mov").write_bytes(b"x" * 100)
            (sub / "hero.jpg").write_bytes(b"x" * 50)

            snapshot = _require_snapshot(scan_folder(root))
            pane = FolderTreePane()
            pane.set_snapshot(snapshot)

            item = pane._tree.topLevelItem(0)
            assert item is not None
            title_text = item.text(0)
            self.assertIn("Footage", title_text)
            self.assertIn("(2)", title_text)
            pane.deleteLater()

    def test_file_header_tiles_show_resolution_not_type(self):
        """Resolution tile replaces the old Type tile in the file header panel."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "clip.mov").write_bytes(b"x" * 100)

            snapshot = _require_snapshot(scan_folder(root))
            file_stats = snapshot.stats_by_path[str(root / "clip.mov")]
            dash = AnalyzerDashboard()
            dash.set_snapshot(
                snapshot,
                file_stats,
                include_hidden=True,
                media_mode="both",
                reset_filter=True,
            )

            # Attribute existence: renamed from _fh_type_val to _fh_resolution_val
            self.assertTrue(hasattr(dash, "_fh_resolution_val"),
                            "Expected _fh_resolution_val attribute on AnalyzerDashboard")
            self.assertFalse(hasattr(dash, "_fh_type_val"),
                             "Expected _fh_type_val to be removed from AnalyzerDashboard")
            # Data-flow: stub .mov has no valid QuickTime atoms → VideoInfo is None → "—"
            self.assertEqual(dash._fh_resolution_val.text(), "—",
                             "_fh_resolution_val should show '—' for a file with no parseable atoms")
            self.assertEqual(dash._fh_fps_val.text(), "—",
                             "_fh_fps_val should show '—' for a file with no parseable atoms")
            dash.deleteLater()

    def test_file_header_tiles_keep_height_in_window_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            footage = root / "Footage"
            footage.mkdir()
            clip_path = footage / "clip.mov"
            clip_path.write_bytes(b"x" * 100)

            snapshot = _require_snapshot(scan_folder(root))
            win = StructuraWindow()
            win.show()
            win._current_root = root
            win._on_snapshot_ready(snapshot)
            win._on_tree_path_selected(str(clip_path))
            self._app.processEvents()

            self.assertTrue(win._dashboard._file_header_row.isVisible())
            self.assertTrue(
                all(
                    frame.height() >= frame.minimumHeight() >= 76
                    for frame in win._dashboard._fh_tile_frames
                )
            )

            win.close()
            self._app.processEvents()
            win.deleteLater()

    def test_empty_window_uses_single_workspace_hero(self):
        win = StructuraWindow()
        win.show()
        self._app.processEvents()

        self.assertTrue(win._workspace_hero.isVisible())
        self.assertFalse(win._splitter.isVisible())
        self.assertIn("start", win._workspace_hero._title.text().lower())

        preview_text = {label.text() for label in win._workspace_hero._preview_type_labels}
        self.assertIn("Images", preview_text)
        self.assertIn("Videos", preview_text)
        self.assertIn("PDFs", preview_text)

        win.close()
        self._app.processEvents()
        win.deleteLater()


class VideoClassificationTest(unittest.TestCase):
    def test_classify_resolution_4k(self):
        self.assertEqual(_classify_resolution(3840, 2160), "4K")
        self.assertEqual(_classify_resolution(2160, 3840), "4K")

    def test_classify_resolution_1080p(self):
        self.assertEqual(_classify_resolution(1920, 1080), "1080p")
        self.assertEqual(_classify_resolution(1080, 1920), "1080p")
        self.assertEqual(_classify_resolution(1080, 1080), "1080p")

    def test_classify_resolution_720p(self):
        self.assertEqual(_classify_resolution(1280, 720), "720p")
        self.assertEqual(_classify_resolution(720, 1280), "720p")

    def test_classify_resolution_hd(self):
        self.assertEqual(_classify_resolution(960, 540), "HD")

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
            info = _require_video_info(
                _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
            )
        assert info.raw_fps is not None
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
            info = _require_video_info(
                _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
            )
        self.assertEqual(info.orientation, "V")
        self.assertEqual(info.width, 1080)
        self.assertEqual(info.height, 1920)

    def test_rotation_90_swaps_dimensions(self):
        # stored as 1920x1080, rotated 90 degrees → displayed as 1080x1920 (vertical)
        movie = self._make_movie(1920, 1080, 90, 600, 120, 10)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _require_video_info(
                _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
            )
        self.assertEqual(info.width, 1080)
        self.assertEqual(info.height, 1920)
        self.assertEqual(info.orientation, "V")

    def test_edited_video_gets_scissors(self):
        # 3000 timescale, 100 frames, delta=100 → 3000*100/(100*100) = 30.0 fps (edited)
        movie = self._make_movie(1920, 1080, 0, 3000, 100, 100)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _require_video_info(
                _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
            )
        assert info.raw_fps is not None
        self.assertAlmostEqual(info.raw_fps, 30.0, places=1)
        self.assertTrue(info.is_edited)
        self.assertEqual(info.fps_category, 30)

    def test_4k_resolution_detected(self):
        movie = self._make_movie(3840, 2160, 0, 600, 120, 10)
        with tempfile.NamedTemporaryFile(suffix=".mov") as f:
            f.write(movie)
            f.flush()
            info = _require_video_info(
                _quicktime_video_info(f.name, Path(f.name).stat().st_mtime_ns)
            )
        self.assertEqual(info.resolution, "4K")


if __name__ == "__main__":
    unittest.main()
