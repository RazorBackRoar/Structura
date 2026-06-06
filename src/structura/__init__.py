"""Re-export public API from the root Structura module.

Bridges the case-insensitive name clash between this package
(src/structura/) and the application monolith (./Structura.py)
so type checkers resolve all symbols correctly on macOS.
"""

# ruff: noqa: F401
from Structura import (
    AnalyzerDashboard,
    FolderTreePane,
    ScanWorker,
    SortWorker,
    StructuraWindow,
    SubtreeStats,
    _classify_fps,
    _classify_resolution,
    _display_folder_count,
    _human_size,
    _quicktime_video_info,
    collect_sortable_extensions,
    extension_color,
    file_emoji,
    scan_folder,
)
