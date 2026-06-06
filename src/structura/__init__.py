"""Re-export public API from the root Structura module.

Bridges the case-insensitive name clash between this package
(src/structura/) and the application monolith (./Structura.py)
so type checkers resolve all symbols correctly on macOS.
"""

# ruff: noqa: F401
from Structura import (  # ty: ignore[unresolved-import]  # noqa: F401
    AnalyzerDashboard,  # ty: ignore[unresolved-import]
    FolderTreePane,  # ty: ignore[unresolved-import]
    ScanWorker,  # ty: ignore[unresolved-import]
    SortWorker,  # ty: ignore[unresolved-import]
    StructuraWindow,  # ty: ignore[unresolved-import]
    SubtreeStats,  # ty: ignore[unresolved-import]
    _classify_fps,  # ty: ignore[unresolved-import]
    _classify_resolution,  # ty: ignore[unresolved-import]
    _display_folder_count,  # ty: ignore[unresolved-import]
    _human_size,  # ty: ignore[unresolved-import]
    _quicktime_video_info,  # ty: ignore[unresolved-import]
    collect_sortable_extensions,  # ty: ignore[unresolved-import]
    extension_color,  # ty: ignore[unresolved-import]
    file_emoji,  # ty: ignore[unresolved-import]
    scan_folder,  # ty: ignore[unresolved-import]
)
