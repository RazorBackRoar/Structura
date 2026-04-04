#!/usr/bin/env python3
"""
Structura – A PySide6 macOS desktop app that accepts drag-and-dropped folders,
recursively scans them, displays a lazy-loaded tree hierarchy, and summarizes
file extension counts with sortable tables and pie charts.
Scanning runs on a background thread for large external SSDs.
"""

import html
import math
import os
import shutil
import subprocess
import sys
import threading
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt, QMimeData, QRectF, QThread, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QPlainTextEdit,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Color palette – frosted aluminum neutrals with deep cobalt accents
# ---------------------------------------------------------------------------
C = {
    "bg": "#edf2f7",
    "surface": "#ffffff",
    "surface_raised": "#f9fbfd",
    "surface_alt": "#f3f6fa",
    "surface_panel": "#e9eef5",
    "border": "#cfd8e3",
    "border_light": "#dee6ef",
    "border_shine": "#ffffff",
    "accent": "#3b63f0",
    "accent_soft": "#6e8cff",
    "accent_hover": "#284ac8",
    "accent_glow": "#9db6ff",
    "accent_deep": "#dfe7ff",
    "heading": "#15233b",
    "text": "#23314a",
    "text_secondary": "#627089",
    "text_dim": "#8c97aa",
    "folder_color": "#3b63f0",
    "file_color": "#51627a",
    "error": "#c2415c",
    "success": "#1f7a52",
    "success_bg": "#e9f9f1",
    "success_border": "#9bddbd",
    "warning": "#b26a16",
    "warning_bg": "#fff4e5",
    "warning_border": "#efc17a",
    "tbl_header_bg": "#eef3ff",
    "tbl_row_a": "#ffffff",
    "tbl_row_b": "#f8fafd",
    "drop_border": "#bcc8da",
    "drop_active_bg": "#e5ecff",
    "drop_active_bdr": "#5f7cff",
    "number_bg": "#355fe9",
    "number_fg": "#ffffff",
    "scanning_fg": "#284ac8",
    "collapse_bg": "#edf2ff",
    # Gradient stop colors used in BUTTON_BG / TOOLBAR_BG_GRADIENT / etc.
    "metal_top": "#f5f7fb",
    "metal_upper": "#edf2f8",
    "metal_mid": "#dde6f1",
    "metal_lower": "#cdd8e5",
    "metal_bot": "#bcc9da",
    "metal_sheen": "#ffffff",
    "chrome_highlight": "#e5ecf5",
    "chrome_shadow": "#c3cfde",
}

JUNK_FILES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    "._.ds_store",
    ".spotlight-v100",
    ".trashes",
    ".fseventsd",
    ".temporaryitems",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".3g2",
    ".ogv",
    ".ts",
    ".mts",
    ".m2ts",
    ".vob",
    ".divx",
    ".xvid",
    ".rm",
    ".rmvb",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
    ".svg",
    ".ico",
    ".raw",
    ".cr2",
    ".nef",
    ".arw",
    ".dng",
    ".orf",
    ".sr2",
    ".psd",
    ".xcf",
}

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".rtf",
    ".odt",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".md",
    ".tex",
    ".pages",
    ".numbers",
    ".key",
}

ARCHIVE_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".dmg",
    ".iso",
    ".sit",
    ".sitx",
    ".pkg",
    ".deb",
    ".rpm",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
    ".m4a",
    ".opus",
    ".aiff",
    ".alac",
    ".mid",
    ".midi",
}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".go",
    ".rs",
    ".swift",
    ".kt",
    ".php",
    ".html",
    ".css",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".r",
    ".m",
    ".lua",
    ".pl",
}

EXECUTABLE_EXTENSIONS = {
    ".exe",
    ".app",
    ".bin",
    ".com",
    ".bat",
    ".cmd",
    ".msi",
    ".appimage",
}

CHART_COLORS = [
    "#3b63f0",
    "#5f7cff",
    "#82a0ff",
    "#4b9fff",
    "#65c5ff",
    "#46c0b8",
    "#6dcc8c",
    "#f1b260",
    "#e97d6d",
    "#9d87ff",
]

EXTENSION_COLORS = {
    ".mov": "#3b63f0",
    ".mp4": "#d9485f",
    ".jpeg": "#d4a017",
    ".jpg": "#d4a017",
    ".heic": "#2f9e5f",
    ".heif": "#2f9e5f",
    ".png": "#8b5e3c",
    ".gif": "#7c5cff",
    ".pdf": "#0f9aa8",
    ".txt": "#6b778c",
    ".py": "#f59f00",
    ".wav": "#9c6bff",
    ".mp3": "#9c6bff",
}

TREE_INITIAL_CAP = 200
TREE_LAZY_SENTINEL = "__lazy_placeholder__"
TREE_SORT_ROLE = Qt.UserRole + 5
TREE_COLUMN_TITLE = 0
TREE_COLUMN_SIZE = 1
TREE_COLUMN_RESOLUTION = 2
TREE_COLUMN_FRAME_RATE = 3
TREE_COLUMN_EDITED = 4
TREE_COLUMN_ORIENTATION = 5
TREE_COLUMN_GPS = 6
TREE_COLUMN_MAKE = 7
TREE_COLUMN_MODEL = 8
TREE_COLUMN_CREATED = 9
TREE_COLUMN_MODIFIED = 10
TREE_HEADERS = (
    "Title",
    "File Size",
    "Resolution",
    "Frame Rate",
    "✂️",
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
    (TREE_COLUMN_RESOLUTION, 80),
    (TREE_COLUMN_FRAME_RATE, 84),
    (TREE_COLUMN_EDITED, 44),
    (TREE_COLUMN_ORIENTATION, 84),
    (TREE_COLUMN_GPS, 52),
    (TREE_COLUMN_MAKE, 52),
    (TREE_COLUMN_MODEL, 160),
    (TREE_COLUMN_CREATED, 118),
    (TREE_COLUMN_MODIFIED, 118),
)
APP_FONT_FAMILY = "Helvetica Neue"
SORTABLE_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
MEDIA_MODES = ("both", "images", "videos")
MEDIA_MODE_LABELS = {
    "both": "Both",
    "images": "Images",
    "videos": "Videos",
}
APP_ICON_RELATIVE_PATH = Path("assets/Structura.icns")
EXTENSION_FILTER_ALL = "__all_extensions__"
PATH_LABEL_MAX_WIDTH = 380
DASHBOARD_MIN_WIDTH = 520
QUICKTIME_FRAME_RATE_EXTENSIONS = {".mov", ".mp4", ".m4v"}

SPACE_2XS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

PANEL_BG = C["surface"]
PANEL_BG_SOFT = C["surface_raised"]
PANEL_BG_ACCENT = C["drop_active_bg"]
BUTTON_BG = (
    "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    f" stop:0 {C['chrome_highlight']},"
    f" stop:0.18 {C['metal_top']},"
    f" stop:0.76 {C['metal_mid']},"
    f" stop:1 {C['chrome_shadow']})"
)
BUTTON_BG_HOVER = (
    "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    f" stop:0 {C['metal_sheen']},"
    f" stop:0.18 {C['chrome_highlight']},"
    f" stop:0.72 {C['metal_upper']},"
    f" stop:1 {C['metal_bot']})"
)
BUTTON_BG_ACTIVE = (
    "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    f" stop:0 {C['chrome_shadow']},"
    f" stop:0.45 {C['metal_lower']},"
    f" stop:1 {C['metal_mid']})"
)
BUTTON_BG_PRIMARY = (
    "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    f" stop:0 {C['accent_hover']},"
    f" stop:0.2 {C['accent']},"
    f" stop:0.76 {C['accent_soft']},"
    f" stop:1 {C['accent_glow']})"
)
BUTTON_BG_PRIMARY_HOVER = (
    "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    f" stop:0 {C['accent_hover']},"
    f" stop:0.16 {C['accent_hover']},"
    f" stop:0.68 {C['accent']},"
    f" stop:1 {C['accent_soft']})"
)
WINDOW_BG_GRADIENT = (
    "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
    " stop:0 #ffffff,"
    " stop:0.65 #f8fbff,"
    " stop:1 #edf4ff)"
)
TOOLBAR_BG_GRADIENT = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:0,"
    " stop:0 #ffffff,"
    " stop:0.68 #f8fbff,"
    " stop:1 #eef5ff)"
)
PANEL_BG_GRADIENT = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
    " stop:0 #ffffff,"
    " stop:1 #f9fbff)"
)
ACCENT_PANEL_GRADIENT = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:1,"
    " stop:0 #f2f7ff,"
    " stop:1 #e7f0ff)"
)
PATH_CARD_GRADIENT = (
    "qlineargradient(x1:0, y1:0, x2:1, y2:0,"
    " stop:0 #ffffff,"
    " stop:1 #f3f8ff)"
)


def button_style(*, variant: str = "secondary", compact: bool = False) -> str:
    if variant == "primary":
        fg = C["border_shine"]
        bg = C["accent"]
        hover = C["accent_hover"]
        border = C["accent"]
        pressed_fg = C["border_shine"]
    else:
        fg = C["text"]
        bg = C["surface"]
        hover = C["surface_raised"]
        border = C["border"]
        pressed_fg = C["accent_hover"]

    pad_v = 7 if compact else 10
    pad_h = 14 if compact else 18
    font_size = 12 if compact else 14
    radius = 10 if compact else 12

    return f"""
        QPushButton {{
            color: {fg};
            background: {bg};
            border: 1px solid {border};
            border-radius: {radius}px;
            padding: {pad_v}px {pad_h}px;
            font-size: {font_size}px;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover {{
            background: {hover};
            color: {C["accent_hover"] if variant != "primary" else C["border_shine"]};
        }}
        QPushButton:pressed {{
            background: {C["surface_panel"] if variant != "primary" else C["accent_soft"]};
            color: {pressed_fg};
        }}
        QPushButton:focus {{
            border: 1px solid {C["accent"]};
        }}
        QPushButton:disabled {{
            color: {C["text_dim"]};
            background: {C["surface_panel"]};
            border: 1px solid {C["border"]};
        }}
    """


def mode_button_style(*, active: bool = False) -> str:
    bg = C["accent"] if active else C["surface"]
    fg = C["border_shine"] if active else C["text_secondary"]
    border = C["accent"] if active else C["border"]
    hover = C["accent_hover"] if active else C["surface_raised"]
    pressed = C["accent"] if active else C["surface_panel"]
    return f"""
        QPushButton {{
            color: {fg};
            background: {bg};
            border: 1px solid {border};
            border-radius: 9px;
            padding: 7px 14px;
            min-height: 36px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover {{
            background: {hover};
            color: {C["border_shine"] if active else C["text"]};
        }}
        QPushButton:pressed {{
            background: {pressed};
            color: {C["border_shine"] if active else C["heading"]};
        }}
        QPushButton:focus {{
            border: 1px solid {C["accent"]};
        }}
        QPushButton:checked {{
            background: {C["accent"]};
            color: {C["border_shine"]};
            border: 1px solid {C["accent"]};
        }}
        QPushButton:disabled {{
            color: {C["text_dim"]};
            background: {C["surface_panel"]};
            border: 1px solid {C["border"]};
        }}
    """


def toolbar_toggle_style(*, active: bool = False) -> str:
    bg = C["accent_deep"] if active else C["surface"]
    fg = C["accent_hover"] if active else C["text"]
    border = C["accent_glow"] if active else C["border"]
    hover = C["tbl_header_bg"] if active else C["surface_raised"]
    return f"""
        QPushButton {{
            color: {fg};
            background: {bg};
            border: 1px solid {border};
            border-radius: 12px;
            padding: 9px 16px;
            min-height: 40px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover {{
            background: {hover};
            color: {C["heading"] if not active else C["accent_hover"]};
        }}
        QPushButton:pressed {{
            background: {C["surface_panel"] if not active else C["accent_glow"]};
        }}
        QPushButton:focus {{
            border: 1px solid {C["accent"]};
        }}
    """


def path_card_style(*, loaded: bool) -> str:
    background = C["surface"] if loaded else C["surface_raised"]
    border = C["border_light"] if loaded else C["border"]
    top_border = C["border_light"] if loaded else C["border_shine"]
    return f"""
        QFrame#path_card {{
            background: {background};
            border: 1px solid {border};
            border-top: 1px solid {top_border};
            border-radius: 12px;
        }}
        QLabel {{
            background: transparent;
        }}
    """


def scroll_bar_style(track: str) -> str:
    return f"""
        QScrollBar:vertical {{
            background: {track};
            width: 12px;
            border-radius: 6px;
            margin: 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {C["border_light"]};
            border: 2px solid {track};
            border-radius: 6px;
            min-height: 36px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {C["accent_glow"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """


def tree_style(*, background: str) -> str:
    return f"""
        QTreeWidget {{
            background: {background};
            alternate-background-color: {C["surface"]};
            color: {C["text"]};
            border: 1px solid {C["border"]};
            border-top: 1px solid {C["border_shine"]};
            border-radius: 12px;
            font-size: 13px;
            padding: 4px;
            selection-background-color: {C["surface_alt"]};
        }}
        QHeaderView::section {{
            background: {C["surface_raised"]};
            color: {C["text_secondary"]};
            border: none;
            border-bottom: 1px solid {C["border"]};
            padding: 8px 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        QTreeWidget::item {{
            padding: 6px 6px;
        }}
        QTreeWidget::item:hover {{
            background: {C["surface_alt"]};
            border-radius: 4px;
        }}
        QTreeWidget::item:selected {{
            background: {PANEL_BG_ACCENT};
            color: {C["heading"]};
            border-radius: 4px;
        }}
        QTreeWidget::branch {{
            background: transparent;
        }}
        {scroll_bar_style(background)}
    """


class StatusPill(QLabel):
    def __init__(self, text: str = "READY", tone: str = "idle"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(28)
        self.setContentsMargins(12, 0, 12, 0)
        self.set_state(text, tone)

    def set_state(self, text: str, tone: str = "idle"):
        palette = {
            "idle": (PANEL_BG_SOFT, C["text_secondary"], C["border"]),
            "active": (PANEL_BG_ACCENT, C["accent_hover"], C["accent_soft"]),
            "warn": (PANEL_BG_SOFT, C["warning"], C["warning"]),
        }
        background, fg, border = palette.get(tone, palette["idle"])
        self.setText(text.upper())
        self.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background: {background};
                border: 1px solid {border};
                border-top: 1px solid {C["border_shine"]};
                border-radius: 13px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1.4px;
            }}
        """)


class MetricTile(QFrame):
    def __init__(self, label: str, value: str, *, accent: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("metric_tile")
        bg = ACCENT_PANEL_GRADIENT if accent else C["surface"]
        border = C["accent_soft"] if accent else C["border"]
        value_color = C["accent_hover"] if accent else C["heading"]
        label_color = C["accent"] if accent else C["text_secondary"]
        self.setStyleSheet(f"""
            QFrame#metric_tile {{
                background: {bg};
                border: 1px solid {border};
                border-top: 2px solid {border};
                border-radius: 10px;
            }}
            QLabel#metric_label {{
                color: {label_color};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1.2px;
                background: transparent;
            }}
            QLabel#metric_value {{
                color: {value_color};
                font-size: 21px;
                font-weight: 700;
                letter-spacing: 0.3px;
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._value_lbl = QLabel(value)
        self._value_lbl.setObjectName("metric_value")
        self._label_lbl = QLabel(label.upper())
        self._label_lbl.setObjectName("metric_label")

        layout.addWidget(self._label_lbl)
        layout.addWidget(self._value_lbl)

    def set_value(self, value: str):
        self._value_lbl.setText(value)

    def set_label(self, label: str):
        self._label_lbl.setText(label.upper())


def classify_file_type(ext: str) -> str:
    """Return 'video', 'image', or 'misc' for a lowercase extension string."""
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "misc"


def media_mode_matches(ext: str, media_mode: str) -> bool:
    file_type = classify_file_type(ext)
    if media_mode == "images":
        return file_type == "image"
    if media_mode == "videos":
        return file_type == "video"
    return file_type in {"image", "video"}


def media_mode_summary_label(media_mode: str) -> str:
    return {
        "both": "photos and videos",
        "images": "photos",
        "videos": "videos",
    }.get(media_mode, "photos and videos")


def media_mode_empty_label(media_mode: str) -> str:
    return {
        "both": "No photos or videos to organize.",
        "images": "No photos to organize.",
        "videos": "No videos to organize.",
    }.get(media_mode, "No photos or videos to organize.")


def media_mode_drop_detail(media_mode: str) -> str:
    return {
        "both": (
            "Structura will map your folder tree, summarize file extensions, "
            "and keep root-level media sorting available when you need it."
        ),
        "images": (
            "Structura will analyze the folder structure and keep image-only "
            "root sorting available when you need it."
        ),
        "videos": (
            "Structura will analyze the folder structure and keep video-only "
            "root sorting available when you need it."
        ),
    }.get(media_mode, "")


def file_kind_label(ext: str) -> str:
    return {
        "video": "Video file",
        "image": "Image file",
        "misc": "File",
    }.get(classify_file_type(ext), "File")


@dataclass
class SortPreview:
    ext_counts: dict[str, int] = field(default_factory=dict)
    skipped_dirs: int = 0
    skipped_other: int = 0
    errors: list[str] = field(default_factory=list)
    ignored_names: list[str] = field(default_factory=list)

    @property
    def total_sortable(self) -> int:
        return sum(self.ext_counts.values())

    @property
    def folder_names(self) -> list[str]:
        return [extension_folder_name(ext) for ext in self.ext_counts]


@dataclass
class SubtreeStats:
    path: str
    name: str
    is_dir: bool
    ext_counts: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_dirs: int = 0
    total_size_bytes: int = 0


@dataclass
class ScanSnapshot:
    root_path: Path
    tree_data: list
    ext_counts: dict[str, int]
    total_files: int
    total_dirs: int
    total_size_bytes: int
    warnings: list[str] = field(default_factory=list)
    stats_by_path: dict[str, SubtreeStats] = field(default_factory=dict)


@dataclass(frozen=True)
class FileExif:
    gps: str | None = None    # formatted coordinates string or None
    make: str | None = None   # camera/device make or None
    model: str | None = None  # camera/device model or None


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
    short_edge = min(width, height)
    if short_edge >= 2160:
        return "4K"
    if short_edge >= 1080:
        return "1080p"
    if short_edge >= 720:
        return "720p"
    if short_edge > 480:
        return "HD"
    return "SD"


def _classify_fps(raw_fps: float | None) -> tuple[int | None, bool]:
    """Return (category, is_edited). Category is 30, 60, or None."""
    if raw_fps is None or raw_fps < 1.0 or raw_fps > 70.0:
        return None, False
    if raw_fps >= 32.0:
        return 60, (60.0 <= raw_fps <= 70.0)
    return 30, (30.0 <= raw_fps < 32.0)


def extension_folder_name(ext: str) -> str:
    return ext.lstrip(".").upper()


def extension_display_label(ext: str) -> str:
    if not ext:
        return "No Extension"
    if ext == "other":
        return "Other"
    return extension_folder_name(ext)


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def extension_color(ext: str) -> str:
    normalized = ext.lower().strip()
    if not normalized:
        return C["file_color"]
    if normalized == "other":
        return C["text_dim"]
    if normalized in EXTENSION_COLORS:
        return EXTENSION_COLORS[normalized]
    index = sum(ord(ch) for ch in normalized) % len(CHART_COLORS)
    return CHART_COLORS[index]


def collect_sortable_extensions(
    folder_path: Path,
    *,
    include_hidden: bool = True,
    media_mode: str = "both",
) -> SortPreview:
    ext_counts: dict[str, int] = defaultdict(int)
    skipped_dirs = 0
    skipped_other = 0
    errors: list[str] = []
    ignored_names: list[str] = []

    # Walk recursively through all directories
    dirs_to_scan = [folder_path]
    while dirs_to_scan:
        current_dir = dirs_to_scan.pop()
        try:
            entries = list(current_dir.iterdir())
        except OSError as exc:
            errors.append(f"Cannot read folder: {exc}")
            continue

        for entry in entries:
            try:
                if entry.is_dir():
                    if not include_hidden and entry.name.startswith("."):
                        continue
                    # Don't descend into folders we created (e.g. "MOV", "JPG")
                    if entry.name.upper() not in {
                        extension_folder_name(e).upper() for e in SORTABLE_EXTENSIONS
                    }:
                        dirs_to_scan.append(entry)
                    skipped_dirs += 1
                    continue
                if not entry.is_file():
                    continue
                if not include_hidden and entry.name.startswith("."):
                    continue
                ext = entry.suffix.lower()
                if ext in SORTABLE_EXTENSIONS and media_mode_matches(ext, media_mode):
                    ext_counts[ext] += 1
                else:
                    skipped_other += 1
                    if current_dir == folder_path:
                        ignored_names.append(sanitize_name(entry.name))
            except OSError as exc:
                errors.append(f"{entry.name}: {exc.strerror}")

    return SortPreview(
        ext_counts=dict(
            sorted(
                ext_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        skipped_dirs=skipped_dirs,
        skipped_other=skipped_other,
        errors=errors,
        ignored_names=sorted(ignored_names, key=str.lower),
    )


def file_emoji(ext: str, is_dir: bool) -> str:
    """Return an emoji string for a file based on extension or directory status."""
    if is_dir:
        return "📂"
    if ext in VIDEO_EXTENSIONS:
        return "🎥"
    if ext in IMAGE_EXTENSIONS:
        return "🖼️"
    if ext in DOCUMENT_EXTENSIONS:
        return "📄"
    if ext in ARCHIVE_EXTENSIONS:
        return "📦"
    if ext in AUDIO_EXTENSIONS:
        return "🎵"
    if ext in CODE_EXTENSIONS:
        return "💻"
    if ext in EXECUTABLE_EXTENSIONS:
        return "⚙️"
    return ""


def _safe_move(src: Path, dest_dir: Path) -> Path:
    """Move src into dest_dir, auto-renaming on collision. Returns final Path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists():
        shutil.move(str(src), str(dest))
        return dest
    stem, suffix, counter = src.stem, src.suffix, 1
    while True:
        candidate = dest_dir / f"{stem}({counter}){suffix}"
        if not candidate.exists():
            shutil.move(str(src), str(candidate))
            return candidate
        counter += 1


def resolve_asset_path(relative_path: Path) -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base_dir / relative_path
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parent / relative_path


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def sanitize_name(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    return "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")


def tree_display_name(name: str, emoji: str = "") -> str:
    clean_name = sanitize_name(name)
    return f"{emoji} {clean_name}" if emoji else clean_name


def _to_datetime(timestamp: float | None) -> "datetime | None":
    return None if timestamp is None else datetime.fromtimestamp(timestamp)


def _format_browser_date(timestamp: float | None) -> str:
    dt = _to_datetime(timestamp)
    if dt is None:
        return "—"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _format_browser_datetime(timestamp: float | None) -> str:
    dt = _to_datetime(timestamp)
    if dt is None:
        return ""
    hour = dt.strftime("%I").lstrip("0") or "0"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}, {hour}:{dt:%M %p}"



def set_elided_label_text(
    label: QLabel,
    text: str,
    max_width: int,
    mode: Qt.TextElideMode = Qt.ElideRight,
) -> None:
    display_text = label.fontMetrics().elidedText(text, mode, max_width)
    label.setText(display_text)
    label.setToolTip(text if text else "")


def sanitize_path(raw: str) -> Path | None:
    try:
        p = Path(os.path.expanduser(raw)).resolve()
        if p.exists():
            return p
    except (OSError, ValueError):
        pass
    return None


def is_junk(name: str) -> bool:
    return name.lower() in JUNK_FILES


def _iter_quicktime_atoms(handle, start: int, end: int):
    position = start
    while position + 8 <= end:
        handle.seek(position)
        header = handle.read(8)
        if len(header) < 8:
            return
        size = int.from_bytes(header[:4], "big")
        kind = header[4:8]
        header_size = 8
        if size == 1:
            large_size = handle.read(8)
            if len(large_size) < 8:
                return
            size = int.from_bytes(large_size, "big")
            header_size = 16
        elif size == 0:
            size = end - position
        if size < header_size:
            return
        payload_start = position + header_size
        payload_end = position + size
        yield kind, payload_start, payload_end
        position += size


def _find_quicktime_atom(handle, start: int, end: int, target: bytes):
    for kind, payload_start, payload_end in _iter_quicktime_atoms(handle, start, end):
        if kind == target:
            return payload_start, payload_end
    return None


def _quicktime_handler_type(handle, start: int) -> bytes | None:
    handle.seek(start)
    data = handle.read(12)
    if len(data) < 12:
        return None
    return data[8:12]


def _quicktime_timescale(handle, start: int) -> int | None:
    handle.seek(start)
    header = handle.read(24)
    if len(header) < 24:
        return None
    version = header[0]
    if version == 1:
        handle.seek(start + 20)
    else:
        handle.seek(start + 12)
    data = handle.read(4)
    if len(data) < 4:
        return None
    return int.from_bytes(data, "big")


def _quicktime_sample_timing(handle, start: int) -> tuple[int, int] | None:
    handle.seek(start)
    header = handle.read(8)
    if len(header) < 8:
        return None
    entry_count = int.from_bytes(header[4:8], "big")
    total_samples = 0
    total_duration = 0
    for _ in range(entry_count):
        row = handle.read(8)
        if len(row) < 8:
            return None
        sample_count = int.from_bytes(row[:4], "big")
        sample_delta = int.from_bytes(row[4:8], "big")
        total_samples += sample_count
        total_duration += sample_count * sample_delta
    return total_samples, total_duration


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


def _mdls_video_dimensions(path: Path) -> tuple[int, int] | None:
    """Read pixel dimensions from macOS Spotlight (fallback when atom parsing fails)."""
    try:
        result = subprocess.run(
            ["mdls", "-raw", "-nullMarker", "",
             "-name", "kMDItemPixelWidth",
             "-name", "kMDItemPixelHeight",
             str(path)],
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
            dims = _mdls_video_dimensions(path)
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


def _dms_to_decimal(dms_value, ref: str) -> float | None:
    """Convert EXIF DMS (degrees/minutes/seconds) tuple to decimal degrees."""
    try:
        d, m, s = dms_value
        decimal = float(d) + float(m) / 60 + float(s) / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def _exif_from_pillow(path: str) -> tuple[str | None, str | None, str | None]:
    """Read GPS/Make/Model from image EXIF via Pillow. Returns (gps_str, make, model)."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            exif_data = img.getexif()  # public API (works for JPEG/PNG/TIFF/WebP)
            if not exif_data:
                return None, None, None

            make = exif_data.get(271)   # Make tag
            model = exif_data.get(272)  # Model tag
            gps_ifd = exif_data.get_ifd(0x8825)  # GPSInfo sub-IFD (returns dict)

            gps_str = None
            if gps_ifd:
                lat_ref = gps_ifd.get(1)   # 'N' or 'S'
                lon_ref = gps_ifd.get(3)   # 'E' or 'W'
                # Don't default hemisphere — returning None is safer than guessing
                if lat_ref and lon_ref:
                    lat = _dms_to_decimal(gps_ifd.get(2), lat_ref)
                    lon = _dms_to_decimal(gps_ifd.get(4), lon_ref)
                    if lat is not None and lon is not None:
                        gps_str = (
                            f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, "
                            f"{abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
                        )

            return (gps_str,
                    str(make).strip() if make else None,
                    str(model).strip() if model else None)
    except Exception:
        return None, None, None


def _exif_from_mdls(path: str) -> tuple[str | None, str | None, str | None]:
    """Read GPS/Make/Model from macOS Spotlight mdls. Works for HEIC/video/any type."""
    import subprocess
    try:
        result = subprocess.run(
            ["mdls", "-raw", "-nullMarker", "",
             "-name", "kMDItemAcquisitionMake",
             "-name", "kMDItemAcquisitionModel",
             "-name", "kMDItemLatitude",
             "-name", "kMDItemLongitude",
             path],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            return None, None, None
        lines = [line.strip() for line in result.stdout.strip().splitlines()]
        # mdls -raw outputs one value per line in the order requested
        if len(lines) < 4:
            return None, None, None
        make_val = lines[0] if lines[0] else None
        model_val = lines[1] if lines[1] else None
        lat_str = lines[2] if lines[2] else None
        lon_str = lines[3] if lines[3] else None

        gps_str = None
        if lat_str and lon_str:
            try:
                lat = float(lat_str)
                lon = float(lon_str)
                gps_str = f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.4f}° {'E' if lon >= 0 else 'W'}"
            except ValueError:
                pass

        return gps_str, make_val, model_val
    except Exception:
        return None, None, None


_IMAGE_EXIF_EXTS = frozenset({
    ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".png", ".webp",
    ".heic", ".heif",  # iPhone default formats (pillow-heif plugin if available, else mdls)
    ".dng",            # DNG is TIFF-based — Pillow can read its EXIF natively
})

def _read_file_exif(path: str, ext: str) -> FileExif:
    """Read GPS/Make/Model. Tries Pillow first for images, then mdls."""
    gps, make, model = None, None, None

    # Normalise ext: accept both "jpg" and ".jpg"
    ext_normalised = ext if ext.startswith(".") else f".{ext}"
    if ext_normalised.lower() in _IMAGE_EXIF_EXTS:
        gps, make, model = _exif_from_pillow(path)

    # Fill missing fields via mdls (works for HEIC, video, and any image)
    if gps is None or make is None or model is None:
        m_gps, m_make, m_model = _exif_from_mdls(path)
        gps = gps or m_gps
        make = make or m_make
        model = model or m_model

    return FileExif(gps=gps, make=make, model=model)


class _ScanCancelled(Exception):
    """Raised inside _walk to abort a scan that was cancelled mid-flight."""


def scan_folder(
    root: Path,
    include_hidden: bool = True,
    progress_cb=None,
    cancel_event: threading.Event | None = None,
) -> ScanSnapshot | None:
    """Scan *root* recursively. Returns None if cancelled via *cancel_event*."""
    warnings: list[str] = []
    stats_by_path: dict[str, SubtreeStats] = {}
    seen_real_paths: set[str] = set()
    dirs_scanned = 0

    def _merge_counts(into: dict[str, int], counts: dict[str, int]):
        for ext, count in counts.items():
            into[ext] += count

    def _sorted_counts(counts: dict[str, int]) -> dict[str, int]:
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def _walk(directory: Path) -> tuple[list, SubtreeStats]:
        nonlocal dirs_scanned
        safe_directory_name = sanitize_name(directory.name or str(directory))
        try:
            real = str(directory.resolve(strict=True))
        except OSError:
            warnings.append(f"Unresolvable path: {directory}")
            stats = SubtreeStats(
                path=str(directory),
                name=safe_directory_name,
                is_dir=True,
                total_dirs=1,
            )
            stats_by_path[str(directory)] = stats
            return [("⚠ Unresolvable path", False, [], "", 0, "")], stats
        if real in seen_real_paths:
            warnings.append(f"Symlink loop skipped: {directory}")
            stats = SubtreeStats(
                path=str(directory),
                name=safe_directory_name,
                is_dir=True,
                total_dirs=1,
            )
            stats_by_path[str(directory)] = stats
            return [("⚠ Symlink loop (skipped)", False, [], "", 0, "")], stats
        seen_real_paths.add(real)
        dirs_scanned += 1
        if cancel_event and cancel_event.is_set():
            raise _ScanCancelled
        if progress_cb and dirs_scanned % 50 == 0:
            progress_cb(dirs_scanned)

        children = []
        ext_counts: dict[str, int] = defaultdict(int)
        total_files = 0
        total_dirs = 1
        total_size_bytes = 0
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            warnings.append(f"Permission denied: {directory}")
            children.append(("⚠ Permission denied", False, [], "", 0, ""))
            stats = SubtreeStats(
                path=str(directory),
                name=safe_directory_name,
                is_dir=True,
                total_dirs=1,
            )
            stats_by_path[str(directory)] = stats
            return children, stats
        except OSError as exc:
            detail = exc.strerror or "Unknown error"
            warnings.append(f"{detail}: {directory}")
            children.append((f"⚠ {sanitize_name(detail)}", False, [], "", 0, ""))
            stats = SubtreeStats(
                path=str(directory),
                name=safe_directory_name,
                is_dir=True,
                total_dirs=1,
            )
            stats_by_path[str(directory)] = stats
            return children, stats

        for entry in entries:
            if is_junk(entry.name):
                continue
            if not include_hidden and entry.name.startswith("."):
                continue
            safe_name = sanitize_name(entry.name)
            try:
                is_dir = entry.is_dir()
                is_file = entry.is_file()
            except OSError:
                continue
            if is_dir:
                sub, child_stats = _walk(entry)
                children.append(
                    (
                        safe_name,
                        True,
                        sub,
                        str(entry),
                        child_stats.total_size_bytes,
                        "",
                    )
                )
                _merge_counts(ext_counts, child_stats.ext_counts)
                total_files += child_stats.total_files
                total_dirs += child_stats.total_dirs
                total_size_bytes += child_stats.total_size_bytes
            elif is_file:
                ext = entry.suffix.lower()
                size = 0
                try:
                    size = entry.stat().st_size
                except OSError as exc:
                    warnings.append(f"{entry}: {exc.strerror}")
                if ext:
                    ext_counts[ext] += 1
                children.append((safe_name, False, [], str(entry), size, ext))
                total_files += 1
                total_size_bytes += size
                stats_by_path[str(entry)] = SubtreeStats(
                    path=str(entry),
                    name=safe_name,
                    is_dir=False,
                    ext_counts={ext: 1} if ext else {},
                    total_files=1,
                    total_size_bytes=size,
                )

        stats = SubtreeStats(
            path=str(directory),
            name=safe_directory_name,
            is_dir=True,
            ext_counts=_sorted_counts(ext_counts),
            total_files=total_files,
            total_dirs=total_dirs,
            total_size_bytes=total_size_bytes,
        )
        stats_by_path[str(directory)] = stats
        return children, stats

    try:
        tree_data, root_stats = _walk(root)
    except _ScanCancelled:
        return None
    return ScanSnapshot(
        root_path=root,
        tree_data=tree_data,
        ext_counts=root_stats.ext_counts,
        total_files=root_stats.total_files,
        total_dirs=max(root_stats.total_dirs - 1, 0),
        total_size_bytes=root_stats.total_size_bytes,
        warnings=warnings,
        stats_by_path=stats_by_path,
    )


# ---------------------------------------------------------------------------
# Background scanner thread
# ---------------------------------------------------------------------------
class ScanWorker(QThread):
    folder_ready = Signal(int, object, dict, list, list)
    snapshot_ready = Signal(object)
    progress = Signal(str, int)
    all_done = Signal()

    def __init__(self, folder_path: Path | list[Path], include_hidden: bool = True):
        super().__init__()
        self._folder_paths = (
            [folder_path] if isinstance(folder_path, Path) else list(folder_path)
        )
        self._emit_snapshot = isinstance(folder_path, Path)
        self._include_hidden = include_hidden
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        for index, folder_path in enumerate(self._folder_paths, start=1):
            if self._cancel_event.is_set():
                break

            def _progress(count, *, current_path: Path = folder_path):
                self.progress.emit(current_path.name, count)

            snapshot = scan_folder(
                folder_path,
                include_hidden=self._include_hidden,
                progress_cb=_progress,
                cancel_event=self._cancel_event,
            )
            if snapshot is None:
                break
            if self._emit_snapshot:
                self.snapshot_ready.emit(snapshot)
            else:
                self.folder_ready.emit(
                    index,
                    folder_path,
                    snapshot.ext_counts,
                    snapshot.tree_data,
                    snapshot.warnings,
                )
        self.all_done.emit()


# ---------------------------------------------------------------------------
# Background metadata (EXIF) thread
# ---------------------------------------------------------------------------
class MetadataWorker(QThread):
    """Background worker that reads GPS/Make/Model EXIF for a list of file paths."""
    chunk_ready = Signal(dict)  # emits dict[str, FileExif]

    def __init__(self, file_paths: list[tuple[str, str]]):
        """file_paths: list of (path_str, ext) tuples for files only (not dirs)."""
        super().__init__()
        self._file_paths = file_paths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        batch: dict[str, FileExif] = {}
        for path, ext in self._file_paths:
            if self._cancelled:
                return
            try:
                batch[path] = _read_file_exif(path, ext)
            except Exception:
                batch[path] = FileExif()
            if len(batch) >= 25:
                self.chunk_ready.emit(dict(batch))
                batch.clear()
        if batch:
            self.chunk_ready.emit(batch)


# ---------------------------------------------------------------------------
# Background sort thread
# ---------------------------------------------------------------------------
class SortWorker(QThread):
    sort_done = Signal(dict, list)

    def __init__(
        self,
        folder_path: Path,
        include_hidden: bool = True,
        media_mode: str = "both",
    ):
        super().__init__()
        self._folder_path = folder_path
        self._include_hidden = include_hidden
        self._media_mode = media_mode

    def run(self):
        preview = collect_sortable_extensions(
            self._folder_path,
            include_hidden=self._include_hidden,
            media_mode=self._media_mode,
        )
        moved_counts: dict[str, int] = {}

        if preview.errors and not preview.ext_counts:
            self.sort_done.emit({}, preview.errors)
            return

        errors = list(preview.errors)
        # Walk all directories and organize media files in each one
        ext_folder_names = {
            extension_folder_name(e).upper() for e in SORTABLE_EXTENSIONS
        }
        dirs_to_process = [self._folder_path]
        while dirs_to_process:
            current_dir = dirs_to_process.pop()
            try:
                entries = list(current_dir.iterdir())
            except OSError as exc:
                errors.append(f"Cannot read {current_dir.name}: {exc}")
                continue

            for entry in entries:
                try:
                    if entry.is_dir():
                        if not self._include_hidden and entry.name.startswith("."):
                            continue
                        # Don't descend into folders we created
                        if entry.name.upper() not in ext_folder_names:
                            dirs_to_process.append(entry)
                        continue
                    if not entry.is_file():
                        continue
                    if not self._include_hidden and entry.name.startswith("."):
                        continue
                    ext = entry.suffix.lower()
                    if ext not in SORTABLE_EXTENSIONS or not media_mode_matches(
                        ext, self._media_mode
                    ):
                        continue
                    dest_dir = current_dir / extension_folder_name(ext)
                    _safe_move(entry, dest_dir)
                    moved_counts[ext] = moved_counts.get(ext, 0) + 1
                except OSError as exc:
                    errors.append(f"{entry.name}: {exc.strerror}")

        self.sort_done.emit(moved_counts, errors)


def _app_bundle_size() -> str:
    """Return the disk size of the running .app bundle, or N/A."""
    exe = Path(sys.executable)
    for parent in exe.parents:
        if parent.suffix == ".app":
            try:
                result = subprocess.run(
                    ["du", "-sh", str(parent)],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if result.returncode == 0:
                    return result.stdout.split("\t")[0].strip()
            except Exception:
                pass
    return "N/A"


_MIT_LICENSE_TEXT = """\
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


class AboutDialog(QDialog):
    """Help → About dialog for Structura."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Structura")
        self.setFixedSize(480, 400)
        self.setStyleSheet(f"""
            QDialog {{
                background: {C["bg"]};
            }}
            QLabel {{
                background: transparent;
                color: {C["text"]};
            }}
            QLabel#app_name {{
                color: {C["heading"]};
                font-size: 24px;
                font-weight: 700;
            }}
            QLabel#tag_line {{
                color: {C["text_secondary"]};
                font-size: 12px;
            }}
            QLabel#info_key {{
                color: {C["text_secondary"]};
                font-size: 12px;
            }}
            QLabel#info_val {{
                color: {C["text"]};
                font-size: 12px;
                font-weight: 500;
            }}
            QFrame#divider {{
                background: {C["border"]};
                border: none;
            }}
            QLabel#license_header {{
                color: {C["text_dim"]};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QPlainTextEdit {{
                background: {C["surface_panel"]};
                color: {C["text_secondary"]};
                border: 1px solid {C["border"]};
                border-radius: 6px;
                font-size: 10px;
                font-family: "SF Mono", "Menlo", monospace;
                padding: 8px;
            }}
            QPushButton {{
                background: {C["accent"]};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 7px 22px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {C["accent_hover"]};
            }}
        """)

        import platform
        arch = platform.machine()
        bundle_size = _app_bundle_size()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 22)
        layout.setSpacing(0)

        name_lbl = QLabel("Structura")
        name_lbl.setObjectName("app_name")
        layout.addWidget(name_lbl)

        tag_lbl = QLabel("Folder scanner · File type analysis · Media organizer")
        tag_lbl.setObjectName("tag_line")
        layout.addWidget(tag_lbl)

        layout.addSpacing(16)

        div1 = QFrame()
        div1.setObjectName("divider")
        div1.setFixedHeight(1)
        layout.addWidget(div1)

        layout.addSpacing(14)

        for label, value in [
            ("Version", "1.0.0"),
            ("Architecture", arch),
            ("App Size", bundle_size),
            ("Copyright", "© 2026 RazorBackRoar"),
            ("License", "MIT License"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(0)
            key_lbl = QLabel(f"{label}:")
            key_lbl.setObjectName("info_key")
            key_lbl.setFixedWidth(120)
            val_lbl = QLabel(value)
            val_lbl.setObjectName("info_val")
            row.addWidget(key_lbl)
            row.addWidget(val_lbl)
            row.addStretch()
            layout.addLayout(row)
            layout.addSpacing(5)

        layout.addSpacing(12)

        div2 = QFrame()
        div2.setObjectName("divider")
        div2.setFixedHeight(1)
        layout.addWidget(div2)

        layout.addSpacing(10)

        license_hdr = QLabel("MIT LICENSE")
        license_hdr.setObjectName("license_header")
        layout.addWidget(license_hdr)

        layout.addSpacing(6)

        license_box = QPlainTextEdit()
        license_box.setReadOnly(True)
        license_box.setPlainText(_MIT_LICENSE_TEXT)
        license_box.setFixedHeight(100)
        layout.addWidget(license_box)

        layout.addSpacing(16)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


# ---------------------------------------------------------------------------
# Sort confirmation dialog
# ---------------------------------------------------------------------------
class SortConfirmDialog(QDialog):
    def __init__(
        self,
        folder_name: str,
        ext_counts: dict[str, int],
        n_skipped: int,
        n_other_files: int,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Sort by Extension")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{
                background: {C["surface"]};
                color: {C["text"]};
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(f'Sort "{sanitize_name(folder_name)}"')
        title.setStyleSheet(
            f"color: {C['heading']}; font-size: 20px; font-weight: 700;"
            f" background: transparent;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Top-level image and video files will be moved into folders named "
            "after their extension. Other files and subfolders stay where they are."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px; line-height: 1.45;"
            f" background: transparent;"
        )
        layout.addWidget(desc)

        if ext_counts:
            list_label = QLabel("Folders to create")
            list_label.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 11px; font-weight: 700;"
                f" letter-spacing: 0.8px; text-transform: uppercase;"
            )
            layout.addWidget(list_label)

            for ext, count in ext_counts.items():
                label = extension_folder_name(ext)
                row = QWidget()
                row.setStyleSheet(f"""
                    QWidget {{
                        background: {C["surface_raised"]};
                        border: 1px solid {C["border"]};
                        border-radius: 10px;
                    }}
                """)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(14, 11, 14, 11)
                rl.setSpacing(12)
                name_lbl = QLabel(label)
                name_lbl.setStyleSheet(
                    f"color: {C['heading']}; font-size: 13px;"
                    f" font-weight: 600; background: transparent;"
                )
                count_lbl = QLabel(str(count))
                count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                count_lbl.setStyleSheet(
                    f"color: {C['accent']}; font-size: 14px;"
                    f" font-weight: 700; background: transparent;"
                )
                rl.addWidget(name_lbl, 1)
                rl.addWidget(count_lbl)
                layout.addWidget(row)
        else:
            empty_lbl = QLabel("No sortable image or video files were found.")
            empty_lbl.setWordWrap(True)
            empty_lbl.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px;"
                f" background: {C['surface_raised']}; border: 1px solid {C['border']};"
                f" border-radius: 10px; padding: 12px;"
            )
            layout.addWidget(empty_lbl)

        detail_parts = []
        if n_other_files:
            detail_parts.append(
                f"{n_other_files} other file{'s' if n_other_files != 1 else ''} ignored"
            )
        if n_skipped:
            detail_parts.append(
                f"{n_skipped} subfolder{'s' if n_skipped != 1 else ''} left untouched"
            )

        if detail_parts:
            info_lbl = QLabel(" · ".join(detail_parts))
            info_lbl.setWordWrap(True)
            info_lbl.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px;"
                f" background: {C['surface_raised']}; border: 1px solid {C['border']};"
                f" border-radius: 10px; padding: 10px 12px;"
            )
            layout.addWidget(info_lbl)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        br = QHBoxLayout(btn_row)
        br.setContentsMargins(0, 4, 0, 0)
        br.setSpacing(10)
        br.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(button_style(compact=True))
        cancel_btn.clicked.connect(self.reject)
        br.addWidget(cancel_btn)

        sort_btn = QPushButton("Organize")
        sort_btn.setCursor(Qt.PointingHandCursor)
        sort_btn.setEnabled(bool(ext_counts))
        sort_btn.setStyleSheet(button_style(variant="primary", compact=True))
        sort_btn.clicked.connect(self.accept)
        br.addWidget(sort_btn)

        layout.addWidget(btn_row)


# ---------------------------------------------------------------------------
# Pie chart widget
# ---------------------------------------------------------------------------
class PieChart(QWidget):
    def __init__(self, ext_counts: dict[str, int], parent=None):
        super().__init__(parent)
        self.setFixedSize(192, 192)
        self._slices: list[tuple[str, int, QColor]] = []
        sorted_exts = sorted(ext_counts.items(), key=lambda kv: -kv[1])
        top = sorted_exts[:8]
        other = sum(c for _, c in sorted_exts[8:])
        for ext, count in top:
            self._slices.append((ext, count, QColor(extension_color(ext))))
        if other > 0:
            self._slices.append(("other", other, QColor(extension_color("other"))))
        self._total = sum(ext_counts.values()) or 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        dim = min(self.width(), self.height())
        ring_rect = QRectF(2, 2, dim - 4, dim - 4)
        painter.setBrush(QBrush(QColor(C["surface_alt"])))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(ring_rect)

        rect = QRectF(10, 10, dim - 20, dim - 20)
        start_angle = 90 * 16
        for _, count, color in self._slices:
            span = int(round(count / self._total * 360 * 16))
            if span == 0:
                span = 16
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(C["bg"]), 1.6))
            painter.drawPie(rect, start_angle, -span)
            start_angle -= span

        inner_size = dim * 0.42
        inner_offset = (dim - inner_size) / 2
        inner = QRectF(inner_offset, inner_offset, inner_size, inner_size)
        painter.setBrush(QBrush(QColor(C["surface_panel"])))
        painter.setPen(QPen(QColor(C["border"]), 1.2))
        painter.drawEllipse(inner)

        label_font = QFont(APP_FONT_FAMILY, 7)
        label_font.setBold(True)
        painter.setFont(label_font)
        painter.setPen(QColor(C["text_secondary"]))
        painter.drawText(QRectF(inner_offset - 4, inner_offset + 12, inner_size + 8, 12), Qt.AlignCenter, "FILES")

        total_font = QFont(APP_FONT_FAMILY, 16)
        total_font.setBold(True)
        painter.setFont(total_font)
        painter.setPen(QColor(C["heading"]))
        painter.drawText(QRectF(inner_offset - 6, inner_offset + 28, inner_size + 12, 24), Qt.AlignCenter, str(self._total))
        painter.end()


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class DropZone(QLabel):
    STYLE_IDLE = f"""
        QLabel {{
            color: {C["text_secondary"]};
            border: 1px solid {C["border_light"]};
            border-radius: 20px;
            padding: 30px;
            background: {C["surface"]};
        }}
    """
    STYLE_HOVER = f"""
        QLabel {{
            border: 1px solid {C["accent_soft"]};
            border-radius: 20px;
            padding: 30px;
            background: {PANEL_BG_GRADIENT};
        }}
    """
    STYLE_SCANNING = f"""
        QLabel {{
            border: 1px solid {C["accent_soft"]};
            border-radius: 20px;
            padding: 30px;
            background: {PANEL_BG_GRADIENT};
        }}
    """

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
        self.setMinimumHeight(156)
        self.set_idle("both")

    def _markup(self, title: str, body: str) -> str:
        return (
            f'<div style="font-size:34px; margin-bottom:10px;">📂</div>'
            f'<div style="color:{C["heading"]}; font-size:28px; font-weight:700;'
            f' margin-bottom:8px;">{title}</div>'
            f'<div style="color:{C["text_secondary"]}; font-size:13px; line-height:1.5;">'
            f"{body}</div>"
        )

    def set_idle(self, media_mode: str = "both"):
        self.setStyleSheet(self.STYLE_IDLE)
        self.setText(
            self._markup(
                "Drop a folder to scan it",
                media_mode_drop_detail(media_mode),
            )
        )

    def set_hover(self, media_mode: str = "both"):
        self.setStyleSheet(self.STYLE_HOVER)
        self.setText(
            self._markup(
                "Release to scan",
                "Structura will build the folder tree, summarize extensions, "
                "and prepare the analyzer workspace.",
            )
        )

    def set_scanning(self, headline: str, detail: str):
        self.setStyleSheet(self.STYLE_SCANNING)
        self.setText(
            self._markup(
                html.escape(headline),
                html.escape(detail),
            )
        )


class HeroFlowItem(QFrame):
    def __init__(self, number: str, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setObjectName("hero_flow_item")
        self.setStyleSheet(f"""
            QFrame#hero_flow_item {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {C["border_light"]};
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(14)

        badge = QLabel(number)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(28, 28)
        badge.setStyleSheet(
            f"color: {C['accent_hover']}; font-size: 11px; font-weight: 700;"
            f" background: {C['tbl_header_bg']}; border: 1px solid {C['accent_glow']};"
            f" border-radius: 14px;"
        )
        layout.addWidget(badge, 0, Qt.AlignTop)

        text_col = QWidget()
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {C['heading']}; font-size: 15px; font-weight: 650;"
        )
        text_layout.addWidget(title_lbl)

        detail_lbl = QLabel(detail)
        detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
        )
        text_layout.addWidget(detail_lbl)

        layout.addWidget(text_col, 1)


class HeroFolderChip(QFrame):
    def __init__(self, label: str, detail: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("hero_folder_chip")
        self.setStyleSheet(f"""
            QFrame#hero_folder_chip {{
                background: {C["surface"]};
                border: 1px solid {C["border_light"]};
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        label_row = QLabel(f"📁 {label}")
        label_row.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: 700;"
        )
        layout.addWidget(label_row)

        detail_row = QLabel(detail)
        detail_row.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px;"
        )
        layout.addWidget(detail_row)


class HeroPreviewLegendItem(QFrame):
    def __init__(self, emoji: str, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setObjectName("hero_preview_legend_item")
        self.setStyleSheet(f"""
            QFrame#hero_preview_legend_item {{
                background: rgba(255, 255, 255, 0.62);
                border: 1px solid {C["border_light"]};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        emoji_lbl = QLabel(emoji)
        emoji_lbl.setStyleSheet("font-size: 19px;")
        layout.addWidget(emoji_lbl, 0, Qt.AlignTop)

        text_col = QWidget()
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {C['heading']}; font-size: 14px; font-weight: 700;"
        )
        text_layout.addWidget(title_lbl)

        detail_lbl = QLabel(detail)
        detail_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px;"
        )
        text_layout.addWidget(detail_lbl)

        layout.addWidget(text_col, 1)


class WorkspaceHero(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workspace_hero")
        self.setStyleSheet(f"""
            QFrame#workspace_hero {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f8fbff,
                    stop:0.52 #edf4ff,
                    stop:1 #dde9ff
                );
                border: 1px solid {C["accent_glow"]};
                border-top: 1px solid {C["border_shine"]};
                border-radius: 34px;
            }}
            QFrame#hero_panel {{
                background: rgba(245, 249, 255, 0.92);
                border: 1px solid {C["accent_glow"]};
                border-radius: 24px;
            }}
            QFrame#hero_preview {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eef4ff,
                    stop:1 #e2ecff
                );
                border: 1px solid {C["accent_glow"]};
                border-radius: 24px;
            }}
            QFrame#hero_sample_board {{
                background: rgba(248, 251, 255, 0.84);
                border: 1px solid {C["accent_glow"]};
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        self.setMinimumHeight(520)
        self.setMinimumWidth(1100)
        self.setMaximumWidth(1220)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(40, 40, 40, 40)
        root_layout.setSpacing(28)

        left_panel = QFrame()
        left_panel.setObjectName("hero_panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(34, 34, 34, 30)
        left_layout.setSpacing(18)

        self._eyebrow = QLabel("STRUCTURA WORKSPACE")
        self._eyebrow.setStyleSheet(
            f"color: {C['accent']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 2.2px;"
        )
        left_layout.addWidget(self._eyebrow)

        self._title = QLabel("")
        self._title.setWordWrap(True)
        self._title.setMaximumWidth(520)
        self._title.setStyleSheet(
            f"color: {C['heading']}; font-size: 42px; font-weight: 780;"
            f" line-height: 1.05;"
        )
        left_layout.addWidget(self._title)

        self._copy = QLabel("")
        self._copy.setWordWrap(True)
        self._copy.setMaximumWidth(470)
        self._copy.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 15px; line-height: 1.4;"
        )
        left_layout.addWidget(self._copy)

        flow_label = QLabel("WHAT HAPPENS NEXT")
        flow_label.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.4px;"
        )
        left_layout.addWidget(flow_label)

        flow_stack = QWidget()
        flow_layout = QVBoxLayout(flow_stack)
        flow_layout.setContentsMargins(0, 0, 0, 0)
        flow_layout.setSpacing(0)
        self._flow_items = [
            HeroFlowItem("01", "Map the structure", "Build the tree and show nested folders."),
            HeroFlowItem("02", "See the file mix", "Spot the dominant file types before you clean up."),
            HeroFlowItem("03", "Create clean folders", "Sort media into JPG, PNG, MP4, and other buckets."),
        ]
        for item in self._flow_items:
            flow_layout.addWidget(item)
        left_layout.addWidget(flow_stack)

        self._helper = QLabel("")
        self._helper.setWordWrap(True)
        self._helper.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 12px;"
        )
        left_layout.addWidget(self._helper)
        left_layout.addStretch()

        root_layout.addWidget(left_panel, 5)

        preview = QFrame()
        preview.setObjectName("hero_preview")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(28, 28, 28, 28)
        preview_layout.setSpacing(18)

        preview_eyebrow = QLabel("PREVIEW")
        preview_eyebrow.setStyleSheet(
            f"color: {C['accent_hover']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.4px;"
        )
        preview_layout.addWidget(preview_eyebrow)

        self._preview_title = QLabel("A mixed folder becomes a clean workspace.")
        self._preview_title.setWordWrap(True)
        self._preview_title.setStyleSheet(
            f"color: {C['heading']}; font-size: 24px; font-weight: 700;"
        )
        preview_layout.addWidget(self._preview_title)

        self._preview_copy = QLabel(
            "Structura reads the folder, shows what is taking up space, and keeps the next organizing step close."
        )
        self._preview_copy.setWordWrap(True)
        self._preview_copy.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px; line-height: 1.4;"
        )
        preview_layout.addWidget(self._preview_copy)

        sample_board = QFrame()
        sample_board.setObjectName("hero_sample_board")
        sample_layout = QVBoxLayout(sample_board)
        sample_layout.setContentsMargins(18, 18, 18, 18)
        sample_layout.setSpacing(12)

        mixed_label = QLabel("FILE TYPES YOU'LL SEE")
        mixed_label.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.1px;"
        )
        sample_layout.addWidget(mixed_label)

        self._preview_type_labels: list[QLabel] = []
        for emoji, title, detail in (
            ("🖼️", "Images", "JPG, PNG, HEIC"),
            ("🎥", "Videos", "MP4, MOV, M4V"),
            ("📄", "PDFs", "Documents and exports"),
            ("🎵", "Audio", "MP3, WAV, M4A"),
        ):
            row = HeroPreviewLegendItem(emoji, title, detail)
            sample_layout.addWidget(row)
            self._preview_type_labels.extend(row.findChildren(QLabel))

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(
            f"color: {C['border_light']}; background: {C['border_light']};"
        )
        sample_layout.addWidget(divider)

        organized_label = QLabel("SORTED INTO CLEAN FOLDERS")
        organized_label.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.1px;"
        )
        sample_layout.addWidget(organized_label)

        chip_row = QWidget()
        chip_row.setStyleSheet("background: transparent;")
        chip_layout = QHBoxLayout(chip_row)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.setSpacing(10)
        chip_layout.addWidget(HeroFolderChip("JPG", "Images", extension_color(".jpg")))
        chip_layout.addWidget(HeroFolderChip("PNG", "Artwork", extension_color(".png")))
        chip_layout.addWidget(HeroFolderChip("MP4", "Clips", extension_color(".mp4")))
        sample_layout.addWidget(chip_row)

        preview_layout.addWidget(sample_board)

        self._preview_helper = QLabel("Drop anywhere in the window. Choose Folder stays in the toolbar.")
        self._preview_helper.setWordWrap(True)
        self._preview_helper.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 12px;"
        )
        preview_layout.addWidget(self._preview_helper)
        preview_layout.addStretch()

        root_layout.addWidget(preview, 4)
        self.set_idle()

    def set_idle(self) -> None:
        self._title.setText("Drop a folder anywhere to start.")
        self._copy.setText(
            "Structura maps the folder, shows the file types inside, and keeps cleanup one step away."
        )
        self._helper.setText("Drop anywhere in the window or use Choose Folder.")
        self._preview_title.setText("See the file types before you organize.")
        self._preview_copy.setText(
            "The preview keeps the labels simple, so you can scan a folder fast and know what each emoji means."
        )
        self._preview_helper.setText("Good for downloads, export folders, camera rolls, and mixed personal files.")

    def set_hover(self) -> None:
        self._title.setText("Release to scan this folder.")
        self._copy.setText(
            "Structura will build the tree, label the file types, and prepare the workspace for cleanup."
        )
        self._helper.setText("Drop anywhere in the window.")
        self._preview_title.setText("This folder is ready to load.")
        self._preview_copy.setText(
            "Once the scan finishes, the overview will show the file mix and the next organizing step."
        )
        self._preview_helper.setText("You can keep dragging over any part of the empty window.")

    def set_scanning(self, headline: str, detail: str) -> None:
        self._title.setText(headline)
        self._copy.setText(detail)
        self._helper.setText("The workspace will appear as soon as the scan is ready.")
        self._preview_title.setText("Scanning the folder now.")
        self._preview_copy.setText(
            "Structura is building the tree, collecting file counts, and preparing the analysis view."
        )
        self._preview_helper.setText("Large folders may take a moment.")


class NumberBadge(QLabel):
    def __init__(self, number: int):
        super().__init__(f"{number:02d}")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(32, 22)
        self.setStyleSheet(f"""
            QLabel {{
                background: {PANEL_BG_ACCENT};
                color: {C["accent_hover"]};
                border: 1px solid {C["accent_soft"]};
                border-top: 1px solid {C["accent_hover"]};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.2px;
                border-radius: 11px;
            }}
        """)


def section_header(number: int, text: str) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    h.addWidget(NumberBadge(number))
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {C['accent']}; font-size: 10px; font-weight: 700;"
        f" background: transparent; letter-spacing: 1.6px;"
    )
    h.addWidget(lbl)
    h.addStretch()
    return row


class OverviewStatChip(QFrame):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("overview_stat_chip")
        self.setStyleSheet(f"""
            QFrame#overview_stat_chip {{
                background: {C["surface"]};
                border: 1px solid {C["border_light"]};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(1)

        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"color: {C['heading']}; font-size: 20px; font-weight: 760;"
        )
        layout.addWidget(self._value)

        self._label = QLabel(label.upper())
        self._label.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.0px;"
        )
        layout.addWidget(self._label)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class DestinationFolderChip(QFrame):
    def __init__(self, label: str, detail: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("destination_folder_chip")
        self.setStyleSheet(f"""
            QFrame#destination_folder_chip {{
                background: {C["surface"]};
                border: 1px solid {C["border_light"]};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(0)

        title = QLabel(label)
        title.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: 760;"
        )
        layout.addWidget(title)

        subtitle = QLabel(detail)
        subtitle.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px;"
        )
        layout.addWidget(subtitle)


class ExtensionTable(QFrame):
    def __init__(
        self,
        ext_counts: dict[str, int],
        *,
        left_header: str = "Folder",
        label_transform=None,
    ):
        super().__init__()
        self._ext_counts = ext_counts
        self._left_header = left_header
        self._label_transform = label_transform or extension_folder_name
        self.setObjectName("extension_table")
        self.setStyleSheet(f"""
            QFrame#extension_table {{
                background: {C["surface"]};
                border: 1px solid {C["border"]};
                border-radius: 12px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._build_rows()

    def _build_rows(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        header = self._row(self._left_header, "Files", is_header=True)
        self._layout.addWidget(header)

        for idx, (ext, count) in enumerate(self._ext_counts.items()):
            self._layout.addWidget(
                self._row(
                    self._label_transform(ext),
                    str(count),
                    even=(idx % 2 == 0),
                    ext=ext,
                )
            )

    def _row(
        self,
        left: str,
        right: str,
        *,
        is_header: bool = False,
        even: bool = True,
        ext: str = "",
    ) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 10, 16, 10)

        lbl_l = QLabel(left)
        lbl_r = QLabel(right)
        lbl_r.setAlignment(Qt.AlignRight)

        if is_header:
            bg = C["surface_panel"]
            left_style = (
                f"color: {C['text_secondary']}; font-size: 12px; font-weight: 700;"
                f" letter-spacing: 0.8px; text-transform: uppercase;"
                f" background: transparent;"
            )
            right_style = left_style
        else:
            bg = C["tbl_row_a"] if even else C["tbl_row_b"]
            accent_color = extension_color(ext)
            left_style = (
                f"color: {accent_color}; font-size: 14px; font-weight: 600;"
                f" background: transparent;"
            )
            right_style = (
                f"color: {accent_color}; font-size: 14px; font-weight: 700;"
                f" background: transparent;"
            )

        w.setStyleSheet(f"background: {bg};")
        lbl_l.setStyleSheet(left_style)
        lbl_r.setStyleSheet(right_style)
        h.addWidget(lbl_l)
        h.addWidget(lbl_r)

        return w


class PieChartLegend(QWidget):
    def __init__(self, ext_counts: dict[str, int]):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        sorted_exts = sorted(ext_counts.items(), key=lambda kv: -kv[1])
        top = sorted_exts[:8]
        other = sum(c for _, c in sorted_exts[8:])

        entries = list(top)
        if other > 0:
            entries.append(("other", other))

        total = sum(ext_counts.values()) or 1
        for ext, count in entries:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {extension_color(ext)};"
                f" font-size: 12px; background: transparent;"
            )
            dot.setFixedWidth(12)
            rl.addWidget(dot)

            pct = count / total * 100
            name = QLabel(extension_display_label(ext))
            name.setStyleSheet(
                f"color: {C['heading']}; font-size: 13px; font-weight: 600;"
                f" background: transparent;"
            )
            rl.addWidget(name, 1)

            count_lbl = QLabel(f"{count:,}")
            count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_lbl.setStyleSheet(
                f"color: {C['text']}; font-size: 13px; font-weight: 700;"
                f" background: transparent;"
            )
            rl.addWidget(count_lbl)

            pct_lbl = QLabel(f"{pct:.0f}%")
            pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pct_lbl.setFixedWidth(42)
            pct_lbl.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px; font-weight: 600;"
                f" background: transparent;"
            )
            rl.addWidget(pct_lbl)
            rl.addStretch()
            layout.addWidget(row)
        layout.addStretch()


# ---------------------------------------------------------------------------
# File browser pane – shows contents of the selected folder with emoji icons
# ---------------------------------------------------------------------------
class FileBrowserPane(QFrame):
    folder_selected = Signal(str)  # emitted when user clicks a folder
    _TREE_STYLE = tree_style(background=PANEL_BG_SOFT)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("browser_pane")
        self.setStyleSheet(f"""
            QFrame#browser_pane {{
                background: {PANEL_BG};
                border: 1px solid {C["border"]};
                border-top: 1px solid {C["border_shine"]};
                border-radius: 14px;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(8)

        self._eyebrow = QLabel("NAVIGATOR")
        self._eyebrow.setStyleSheet(
            f"color: {C['accent']}; font-size: 10px; font-weight: 700;"
            f" letter-spacing: 1.8px; background: transparent;"
        )
        root_layout.addWidget(self._eyebrow)

        # Header
        self._header = QLabel("Nothing selected")
        self._header.setStyleSheet(
            f"color: {C['heading']}; font-size: 22px; font-weight: 700;"
            f" letter-spacing: 0.3px; background: transparent;"
        )
        root_layout.addWidget(self._header)

        # Path label
        self._path_lbl = QLabel("Pick a scanned folder to inspect its contents.")
        self._path_lbl.setWordWrap(True)
        self._path_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px; line-height: 1.4;"
            f" background: transparent;"
        )
        root_layout.addWidget(self._path_lbl)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Type", "Size"])
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(12)
        self._tree.setColumnWidth(0, 200)
        self._tree.setColumnWidth(1, 60)
        self._tree.setStyleSheet(self._TREE_STYLE)
        self._tree.itemDoubleClicked.connect(self._on_item_double_click)
        root_layout.addWidget(self._tree, 1)

        # Empty state
        self._empty_lbl = QLabel(
            "Select a folder from scan results\nto browse its contents."
        )
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 12px; background: {PANEL_BG_SOFT};"
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['border_shine']};"
            f" border-radius: 10px; padding: 22px;"
        )
        root_layout.addWidget(self._empty_lbl, 1)

        self._current_path: Path | None = None
        self.reset()

    def _show_tree(self):
        self._empty_lbl.hide()
        self._tree.show()

    def _show_empty_state(self, text: str):
        self._empty_lbl.setText(text)
        self._empty_lbl.show()
        self._tree.hide()

    def reset(self):
        self._current_path = None
        self._header.setText("Nothing selected")
        self._path_lbl.setText("Pick a scanned folder to inspect its contents.")
        self._path_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px; background: transparent;"
        )
        self._tree.clear()
        self._show_empty_state(
            "Select a folder from scan results\nto browse its contents."
        )

    def set_folder(self, folder_path: Path):
        """Populate the browser with the contents of *folder_path*."""
        self._current_path = folder_path
        self._header.setText(sanitize_name(folder_path.name))
        self._path_lbl.setText(str(folder_path))
        self._path_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px; background: transparent;"
        )
        self._tree.clear()
        self._show_tree()

        try:
            entries = sorted(
                folder_path.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except (PermissionError, OSError):
            self._show_empty_state("Cannot read this folder.")
            return

        count = 0
        for entry in entries:
            if is_junk(entry.name):
                continue
            try:
                is_dir = entry.is_dir()
                is_file = entry.is_file()
            except OSError:
                continue

            ext = entry.suffix.lower() if is_file else ""
            emoji = file_emoji(ext, is_dir)
            item = QTreeWidgetItem()
            item.setText(0, tree_display_name(entry.name, emoji))

            if is_dir:
                apply_tree_item_colors(item, is_dir=True)
                item.setText(1, "folder")
                item.setText(2, "—")
            else:
                apply_tree_item_colors(item, is_dir=False, ext=ext)
                item.setText(1, ext.lstrip(".") if ext else "—")
                try:
                    size = entry.stat().st_size
                    item.setText(2, _human_size(size))
                except OSError:
                    item.setText(2, "—")

            item.setData(0, Qt.UserRole, str(entry))
            self._tree.addTopLevelItem(item)
            count += 1

        if count == 0:
            self._show_empty_state("This folder is empty.")
        else:
            # Update header with count
            self._header.setText(
                f"📂 {sanitize_name(folder_path.name)}  ({count} items)"
            )

    def _on_item_double_click(self, item: QTreeWidgetItem, column: int):
        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        if path.is_dir():
            self.set_folder(path)
            self.folder_selected.emit(str(path))


def _human_size(nbytes: int) -> str:
    """Format bytes the way Finder does: decimal units with a GB label."""
    value = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1000 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} PB"


def _tree_preview_lines(
    folder_name: str,
    tree_data: list,
    *,
    max_lines: int = 12,
    max_depth: int = 3,
) -> list[str]:
    lines = [f"📂 {sanitize_name(folder_name)}"]
    overflow = {"count": 0}

    def walk(nodes: list, prefix: str = "", depth: int = 0):
        if depth >= max_depth:
            if nodes:
                overflow["count"] += len(nodes)
            return
        for index, (name, is_dir, children, _, _, ext) in enumerate(nodes):
            if len(lines) >= max_lines:
                overflow["count"] += len(nodes) - index
                return
            branch = "└── " if index == len(nodes) - 1 else "├── "
            child_prefix = "    " if index == len(nodes) - 1 else "│   "
            emoji = "📁" if is_dir else file_emoji(ext, False)
            lines.append(f"{prefix}{branch}{tree_display_name(name, emoji)}")
            if children:
                walk(children, prefix + child_prefix, depth + 1)
                if len(lines) >= max_lines:
                    return

    walk(tree_data)
    if overflow["count"] > 0 and len(lines) < max_lines + 1:
        lines.append(f"└── … {overflow['count']} more item{'s' if overflow['count'] != 1 else ''}")
    return lines


def apply_tree_item_colors(item: QTreeWidgetItem, *, is_dir: bool, ext: str = "") -> None:
    color = QColor(C["folder_color"] if is_dir else extension_color(ext))
    item.setForeground(0, color)
    item.setForeground(1, color)


class TreePreview(QFrame):
    def __init__(self, folder_name: str, tree_data: list, parent=None):
        super().__init__(parent)
        self.setObjectName("tree_preview")
        self.setStyleSheet(f"""
            QFrame#tree_preview {{
                background: {C["surface_raised"]};
                border: 1px solid {C["border"]};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        label = QLabel("Folder Preview")
        label.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 0.7px; text-transform: uppercase;"
        )
        layout.addWidget(label)

        preview = QLabel("\n".join(_tree_preview_lines(folder_name, tree_data)))
        preview.setTextFormat(Qt.PlainText)
        preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        preview.setStyleSheet(
            f"color: {C['text']}; font-size: 12px; background: transparent;"
            f" font-family: Menlo, Monaco, 'SF Mono'; line-height: 1.45;"
        )
        layout.addWidget(preview)


# ---------------------------------------------------------------------------
# Lazy tree population helpers
# ---------------------------------------------------------------------------
class SortableTreeItem(QTreeWidgetItem):
    pass


def _count_tree_nodes(data: list) -> int:
    total = 0
    for _, _, children, _, _, _ in data:
        total += 1
        if children:
            total += _count_tree_nodes(children)
    return total


def _tree_item_type_label(*, is_dir: bool, ext: str) -> str:
    if is_dir:
        return "folder"
    return ext.lstrip(".") if ext else "file"


_EXT_TO_EMOJI: dict[str, str] = {
    # Images
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️",
    ".bmp": "🖼️", ".tiff": "🖼️", ".tif": "🖼️", ".webp": "🖼️",
    ".heic": "🖼️", ".heif": "🖼️", ".svg": "🖼️",
    ".raw": "🖼️", ".cr2": "🖼️", ".cr3": "🖼️", ".nef": "🖼️",
    ".arw": "🖼️", ".dng": "🖼️", ".orf": "🖼️", ".rw2": "🖼️",
    # Video
    ".mp4": "🎬", ".mov": "🎬", ".avi": "🎬", ".mkv": "🎬",
    ".wmv": "🎬", ".flv": "🎬", ".webm": "🎬", ".m4v": "🎬",
    ".3gp": "🎬", ".mts": "🎬", ".m2ts": "🎬",
    # Audio
    ".mp3": "🎵", ".wav": "🎵", ".aac": "🎵", ".m4a": "🎵",
    ".flac": "🎵", ".ogg": "🎵", ".wma": "🎵", ".aiff": "🎵", ".alac": "🎵",
    # Documents
    ".pdf": "📄",
    ".docx": "📝", ".doc": "📝", ".txt": "📝", ".rtf": "📝",
    ".md": "📝", ".pages": "📝",
    # Spreadsheets
    ".xlsx": "📊", ".xls": "📊", ".csv": "📊", ".numbers": "📊",
    # Archives
    ".zip": "🗜️", ".rar": "🗜️", ".tar": "🗜️", ".gz": "🗜️",
    ".7z": "🗜️", ".dmg": "🗜️", ".iso": "🗜️",
}


def _type_emoji(type_label: str) -> str:
    """Return a single emoji for the Type column."""
    if type_label == "folder":
        return "📁"
    return _EXT_TO_EMOJI.get(f".{type_label.lower()}", "📎")


@dataclass(frozen=True)
class TreeItemMetadata:
    type_label: str
    created_ts: float | None
    modified_ts: float | None
    video_info: "VideoInfo | None"
    created_text: str
    modified_text: str
    size_text: str


def _style_tree_item_title(
    item: QTreeWidgetItem,
    *,
    name: str,
    is_dir: bool,
    ext: str,
) -> None:
    item.setText(TREE_COLUMN_TITLE, tree_display_name(name, file_emoji(ext, is_dir)))
    if is_dir:
        apply_tree_item_colors(item, is_dir=True)
        font = item.font(TREE_COLUMN_TITLE)
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        item.setFont(TREE_COLUMN_TITLE, font)
        return
    apply_tree_item_colors(item, is_dir=False, ext=ext)


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


def _format_frame_rate_display(video_info: "VideoInfo | None") -> str:
    if video_info is None:
        return ""
    if video_info.fps_category is None:
        if video_info.raw_fps is not None:
            return str(round(video_info.raw_fps))
        return ""
    return str(video_info.fps_category)


def _format_frame_rate_tooltip(video_info: "VideoInfo | None") -> str:
    if video_info is None or video_info.raw_fps is None:
        return ""
    fps = video_info.raw_fps
    rounded = round(fps)
    if abs(fps - rounded) < 0.01:
        return f"{rounded:d} fps"
    return f"{fps:.2f} fps"


def _format_gps_display(gps: str | None) -> str:
    return "\U0001f30d" if gps else "\u274c"


def _format_make_display(make: str | None) -> str:
    if not make:
        return "\u274c"
    return "\U0001f34e" if "apple" in make.lower() else "\u274c"


def _format_model_display(model: str | None) -> str:
    if not model:
        return "\u2014"
    if "iphone" in model.lower():
        return f"\U0001f4f1 {model}"
    return model


def _apply_tree_item_metadata(
    item: QTreeWidgetItem,
    *,
    name: str,
    path_str: str,
    size_bytes: int,
    metadata: TreeItemMetadata,
    folder_item_count: int = 0,
) -> None:
    _ext_key = f".{metadata.type_label.lower()}" if metadata.type_label != "folder" else ""
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
        item.setText(TREE_COLUMN_EDITED, "\u2702\ufe0f" if vi.is_edited else "")
        item.setText(TREE_COLUMN_ORIENTATION, vi.orientation)
        item.setToolTip(TREE_COLUMN_FRAME_RATE, _format_frame_rate_tooltip(vi))
    else:
        item.setText(TREE_COLUMN_RESOLUTION, "")
        item.setText(TREE_COLUMN_FRAME_RATE, "")
        item.setText(TREE_COLUMN_EDITED, "")
        item.setText(TREE_COLUMN_ORIENTATION, "")

    # Alignment
    item.setData(TREE_COLUMN_SIZE, Qt.TextAlignmentRole, int(Qt.AlignRight | Qt.AlignVCenter))
    for col in (TREE_COLUMN_RESOLUTION, TREE_COLUMN_FRAME_RATE, TREE_COLUMN_EDITED,
                TREE_COLUMN_ORIENTATION, TREE_COLUMN_GPS, TREE_COLUMN_MAKE, TREE_COLUMN_MODEL):
        item.setData(col, Qt.TextAlignmentRole, int(Qt.AlignHCenter | Qt.AlignVCenter))

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
    item.setData(TREE_COLUMN_EDITED, TREE_SORT_ROLE, (vi is None, not vi.is_edited if vi else True, name_key))
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


def _configure_tree_item(
    item: QTreeWidgetItem,
    *,
    name: str,
    is_dir: bool,
    path_str: str,
    size_bytes: int,
    ext: str,
    folder_item_count: int = 0,
) -> None:
    _style_tree_item_title(item, name=name, is_dir=is_dir, ext=ext)
    metadata = _tree_item_metadata(
        path_str,
        is_dir=is_dir,
        ext=ext,
        size_bytes=size_bytes,
    )
    _apply_tree_item_metadata(
        item,
        name=name,
        path_str=path_str,
        size_bytes=size_bytes,
        metadata=metadata,
        folder_item_count=folder_item_count,
    )


def _sort_tree_data(data: list, column: int, ascending: bool) -> list:
    """Sort tree_data recursively in Python — avoids Qt's C++→Python __lt__ dispatch."""
    def key_fn(entry):
        name, is_dir, _children, _path, size_bytes, ext = entry
        name_k = sanitize_name(name).casefold()
        if column == TREE_COLUMN_SIZE:
            return (size_bytes == 0, size_bytes, name_k)
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


def _populate_tree_lazy(tree: QTreeWidget, data: list, parent=None, budget=None):
    if budget is None:
        budget = [TREE_INITIAL_CAP]

    for i, (name, is_dir, children, path_str, size_bytes, ext) in enumerate(data):
        if budget[0] <= 0:
            remaining = len(data) - i
            placeholder = QTreeWidgetItem(parent) if parent else QTreeWidgetItem(tree)
            placeholder.setText(0, f"… {remaining} more items")
            placeholder.setForeground(0, QColor(C["accent_soft"]))
            placeholder.setData(0, Qt.UserRole, TREE_LAZY_SENTINEL)
            placeholder.setData(0, Qt.UserRole + 1, data[i:])
            return
        budget[0] -= 1

        item = QTreeWidgetItem(parent) if parent else QTreeWidgetItem(tree)
        _configure_tree_item(
            item,
            name=name,
            is_dir=is_dir,
            path_str=path_str,
            size_bytes=size_bytes,
            ext=ext,
            folder_item_count=len(children) if is_dir else 0,
        )

        if children:
            # Always lazy-load folder children — never pre-expand during initial
            # load so the budget applies only to siblings at the same level.
            placeholder = QTreeWidgetItem(item)
            placeholder.setText(0, f"… {len(children)} items")
            placeholder.setForeground(0, QColor(C["accent_soft"]))
            placeholder.setData(0, Qt.UserRole, TREE_LAZY_SENTINEL)
            placeholder.setData(0, Qt.UserRole + 1, children)


def _expand_lazy_placeholder(tree: QTreeWidget, item: QTreeWidgetItem):
    data = item.data(0, Qt.UserRole + 1)
    if not data:
        return

    parent = item.parent()
    if parent:
        idx = parent.indexOfChild(item)
        parent.removeChild(item)
        for entry_data in data:
            name, is_dir, children, path_str, size_bytes, ext = entry_data
            child = QTreeWidgetItem()
            _configure_tree_item(
                child,
                name=name,
                is_dir=is_dir,
                path_str=path_str,
                size_bytes=size_bytes,
                ext=ext,
                folder_item_count=len(children) if is_dir else 0,
            )
            parent.insertChild(idx, child)
            idx += 1
            if children:
                _populate_tree_lazy(tree, children, child, budget=[TREE_INITIAL_CAP])
    else:
        idx = tree.indexOfTopLevelItem(item)
        tree.takeTopLevelItem(idx)
        for entry_data in data:
            name, is_dir, children, path_str, size_bytes, ext = entry_data
            child = QTreeWidgetItem()
            _configure_tree_item(
                child,
                name=name,
                is_dir=is_dir,
                path_str=path_str,
                size_bytes=size_bytes,
                ext=ext,
                folder_item_count=len(children) if is_dir else 0,
            )
            tree.insertTopLevelItem(idx, child)
            idx += 1
            if children:
                _populate_tree_lazy(tree, children, child, budget=[TREE_INITIAL_CAP])



# ---------------------------------------------------------------------------
# Collapsible folder card
# ---------------------------------------------------------------------------
class FolderResultCard(QFrame):
    rescan_requested = Signal(object)
    status_requested = Signal(str, str)

    def __init__(
        self,
        index: int,
        folder_path: Path,
        ext_counts: dict[str, int],
        tree_data: list,
        warnings: list[str],
        include_hidden: bool,
        media_mode: str,
    ):
        super().__init__()
        self.setObjectName("result_card")
        self.setStyleSheet(f"""
            QFrame#result_card {{
                background: {C["surface"]};
                border: 1px solid {C["border"]};
                border-radius: 18px;
            }}
        """)

        self._collapsed = False
        self._folder_path = folder_path
        self._include_hidden = include_hidden
        self._media_mode = media_mode
        self._sort_worker: SortWorker | None = None
        preview = collect_sortable_extensions(
            folder_path,
            include_hidden=include_hidden,
            media_mode=media_mode,
        )
        warning_total = len(warnings)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(10)

        header_row = QWidget()
        header_row.setStyleSheet("background: transparent;")
        header_hbox = QHBoxLayout(header_row)
        header_hbox.setContentsMargins(0, 0, 0, 0)
        header_hbox.setSpacing(12)

        title_block = QWidget()
        title_block.setStyleSheet("background: transparent;")
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        folder_icon = QLabel("📁")
        folder_icon.setStyleSheet("font-size: 20px; background: transparent;")
        title_layout.addWidget(folder_icon)

        title_lbl = QLabel(sanitize_name(folder_path.name))
        title_lbl.setStyleSheet(
            f"color: {C['heading']}; font-size: 22px; font-weight: 700;"
            f" background: transparent;"
        )
        title_layout.addWidget(title_lbl)

        path_lbl = QLabel(str(folder_path))
        path_lbl.setWordWrap(True)
        path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px; background: transparent;"
        )
        title_layout.addWidget(path_lbl)

        header_hbox.addWidget(title_block, 1)

        self._sort_btn = QPushButton("Organize")
        self._sort_btn.setCursor(Qt.PointingHandCursor)
        self._sort_btn.setFixedWidth(116)
        self._sort_btn.setMinimumHeight(38)
        self._sort_btn.setEnabled(bool(preview.ext_counts))
        self._sort_btn.setStyleSheet(button_style(variant="primary", compact=True))
        self._sort_btn.clicked.connect(self._on_sort_clicked)
        header_hbox.addWidget(self._sort_btn, 0, Qt.AlignTop)

        root_layout.addWidget(header_row)

        summary_text = (
            f"This folder has {preview.total_sortable} {media_mode_summary_label(media_mode)}"
            f" in {len(preview.ext_counts)} extension"
            f"{'' if len(preview.ext_counts) == 1 else 's'}."
            if preview.ext_counts
            else media_mode_empty_label(media_mode)
        )
        summary_lbl = QLabel(summary_text)
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 14px; font-weight: 600;"
            f" background: transparent;"
        )
        root_layout.addWidget(summary_lbl)

        if preview.ext_counts:
            root_layout.addWidget(ExtensionTable(preview.ext_counts))
            creates_lbl = QLabel(f"Will create: {', '.join(preview.folder_names)}")
            creates_lbl.setWordWrap(True)
            creates_lbl.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px;"
                f" background: transparent;"
            )
            root_layout.addWidget(creates_lbl)
        else:
            empty_lbl = QLabel(
                "No photos or videos to organize."
            )
            empty_lbl.setWordWrap(True)
            empty_lbl.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px;"
                f" background: transparent;"
            )
            root_layout.addWidget(empty_lbl)

        root_layout.addWidget(TreePreview(folder_path.name, tree_data))

        detail_parts = []
        if preview.skipped_other:
            detail_parts.append(
                f"{preview.skipped_other} other file"
                f"{'' if preview.skipped_other == 1 else 's'} ignored."
            )
        if preview.skipped_dirs:
            detail_parts.append(
                f"{preview.skipped_dirs} subfolder"
                f"{'' if preview.skipped_dirs == 1 else 's'} untouched."
            )
        hidden_state = "included" if include_hidden else "excluded"
        detail_parts.append(f"Hidden files {hidden_state}.")
        if warning_total:
            detail_parts.append(
                f"{warning_total} scan warning{'s' if warning_total != 1 else ''}."
            )

        note_lbl = QLabel(" ".join(detail_parts))
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px;"
            f" background: transparent;"
        )
        root_layout.addWidget(note_lbl)

        if preview.ignored_names:
            ignored_preview = ", ".join(preview.ignored_names[:5])
            if len(preview.ignored_names) > 5:
                remaining = len(preview.ignored_names) - 5
                ignored_preview += f" and {remaining} more"
            ignored_lbl = QLabel(f"Ignored files: {ignored_preview}")
            ignored_lbl.setWordWrap(True)
            ignored_lbl.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px;"
                f" background: {C['surface_raised']}; border: 1px solid {C['border']};"
                f" border-radius: 10px; padding: 12px;"
            )
            root_layout.addWidget(ignored_lbl)

        combined_errors = warnings[:3] + preview.errors[:3]
        if combined_errors:
            warn_lbl = QLabel("\n".join(f"• {sanitize_name(w)}" for w in combined_errors))
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet(
                f"color: {C['warning']}; font-size: 12px; background: {C['warning_bg']};"
                f" border: 1px solid {C['warning_border']}; border-radius: 10px;"
                f" padding: 12px;"
            )
            root_layout.addWidget(warn_lbl)

    def _on_sort_clicked(self):
        preview = collect_sortable_extensions(
            self._folder_path,
            include_hidden=self._include_hidden,
            media_mode=self._media_mode,
        )
        if not preview.ext_counts and not preview.errors:
            return

        self._sort_btn.setEnabled(False)
        self._sort_btn.setText("Organizing…")
        self._sort_worker = SortWorker(
            self._folder_path,
            include_hidden=self._include_hidden,
            media_mode=self._media_mode,
        )
        self._sort_worker.sort_done.connect(self._on_sort_done)
        self._sort_worker.start()

    def _on_sort_done(self, moved_counts: dict, errors: list):
        self._sort_worker = None
        self._sort_btn.setEnabled(True)
        self._sort_btn.setText("Organize")
        if moved_counts and not errors:
            moved_total = sum(moved_counts.values())
            folder_names = ", ".join(
                extension_folder_name(ext) for ext in sorted(moved_counts)
            )
            self.status_requested.emit(
                f"Organized {moved_total} file"
                f"{'' if moved_total == 1 else 's'} into {folder_names}.",
                "success",
            )
        elif moved_counts and errors:
            moved_total = sum(moved_counts.values())
            self.status_requested.emit(
                f"Organized {moved_total} file"
                f"{'' if moved_total == 1 else 's'}, but some files could not be moved.",
                "warning",
            )
        elif errors:
            self.status_requested.emit(
                "Nothing was organized because the folder could not be updated.",
                "warning",
            )
        self.rescan_requested.emit(self._folder_path)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Structura")
        self.setMinimumSize(1080, 860)
        self.resize(1180, 920)
        self.setAcceptDrops(True)
        self.setUnifiedTitleAndToolBarOnMac(True)
        self._apply_palette()

        self._worker: ScanWorker | None = None
        self._include_hidden = True
        self._media_mode = "both"
        self._last_paths: list[Path] = []
        self._pending_status: tuple[str, str] | None = None

        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(f"""
            QMenuBar {{
                background: {TOOLBAR_BG_GRADIENT};
                color: {C["text"]};
                border-bottom: 1px solid {C["border"]};
                padding: 3px 10px;
                font-size: 12px;
            }}
            QMenuBar::item {{
                padding: 5px 10px;
                border-radius: 6px;
                background: transparent;
            }}
            QMenuBar::item:selected {{
                background: {PANEL_BG_GRADIENT};
            }}
            QMenu {{
                background: {PANEL_BG_GRADIENT};
                color: {C["text"]};
                border: 1px solid {C["border"]};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {C["surface_raised"]};
            }}
            QMenu::separator {{
                height: 1px;
                background: {C["border"]};
                margin: 4px 8px;
            }}
        """)

        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Open Folder…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_folder_dialog)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_action)

        view_menu = menu_bar.addMenu("View")
        self._hidden_action = QAction("Show Hidden Files", self)
        self._hidden_action.setCheckable(True)
        self._hidden_action.setChecked(True)
        self._hidden_action.triggered.connect(self._toggle_hidden)
        view_menu.addAction(self._hidden_action)

        help_menu = menu_bar.addMenu("Help")
        about_action_mw = QAction("About Structura", self)
        about_action_mw.triggered.connect(lambda: AboutDialog(self).exec())
        help_menu.addAction(about_action_mw)

        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {C["surface"]};
                border-bottom: 1px solid {C["border"]};
                spacing: 10px;
                padding: 12px 18px;
            }}
            QToolBar::separator {{
                width: 8px;
                background: transparent;
            }}
        """)

        title_block = QWidget()
        title_block.setStyleSheet("background: transparent;")
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        app_title = QLabel("Structura")
        app_title.setStyleSheet(
            f"color: {C['heading']}; font-size: 30px; font-weight: 700;"
            f" background: transparent;"
        )
        title_layout.addWidget(app_title)

        subtitle = QLabel(
            "Drop a folder, review sortable extensions, then click Sort."
        )
        subtitle.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px; background: transparent;"
        )
        title_layout.addWidget(subtitle)
        toolbar.addWidget(title_block)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)

        mode_group = QWidget()
        mode_group.setObjectName("mode_group")
        mode_group.setStyleSheet(f"""
            QWidget#mode_group {{
                background: {C["surface_alt"]};
                border: 1px solid {C["border"]};
                border-radius: 12px;
            }}
        """)
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setContentsMargins(6, 6, 6, 6)
        mode_layout.setSpacing(6)
        self._mode_buttons: dict[str, QPushButton] = {}
        for mode in MEDIA_MODES:
            button = QPushButton(MEDIA_MODE_LABELS[mode])
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked, selected_mode=mode: self._set_media_mode(selected_mode)
            )
            self._mode_buttons[mode] = button
            mode_layout.addWidget(button)
        self._refresh_mode_buttons()
        toolbar.addWidget(mode_group)

        open_btn = QPushButton("Open Folder")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setStyleSheet(button_style(variant="primary"))
        open_btn.setMinimumHeight(40)
        open_btn.clicked.connect(self._open_folder_dialog)
        toolbar.addWidget(open_btn)

        self._hidden_btn = QPushButton("Hidden: On")
        self._hidden_btn.setCursor(Qt.PointingHandCursor)
        self._hidden_btn.setStyleSheet(button_style())
        self._hidden_btn.setMinimumHeight(40)
        self._hidden_btn.clicked.connect(self._toggle_hidden)
        toolbar.addWidget(self._hidden_btn)

        self.addToolBar(toolbar)

        # --- Results area (right side) ---
        self.scroll: QScrollArea = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            {scroll_bar_style(C["bg"])}
        """)

        self.container = QWidget()
        self.container.setStyleSheet(f"background: {C['bg']};")
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(18, 16, 18, 20)
        self.main_layout.setSpacing(12)
        self.main_layout.setAlignment(Qt.AlignTop)

        self.drop_zone = DropZone()
        self.main_layout.addWidget(self.drop_zone)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color: {C['warning']}; font-size: 12px; background: {C['warning_bg']};"
            f" border: 1px solid {C['warning_border']}; border-radius: 12px;"
            f" padding: 12px 14px;"
        )
        self.status.hide()
        self.main_layout.addWidget(self.status)

        self.results_widgets: list[QWidget] = []

        self.scroll.setWidget(self.container)
        self.setCentralWidget(self.scroll)
        self.drop_zone.set_idle(self._media_mode)

    def _apply_palette(self):
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(C["bg"]))
        pal.setColor(QPalette.WindowText, QColor(C["text"]))
        self.setPalette(pal)

    def _status_style(self, tone: str) -> str:
        if tone == "success":
            fg = C["success"]
            bg = C["success_bg"]
            border = C["success_border"]
        else:
            fg = C["warning"]
            bg = C["warning_bg"]
            border = C["warning_border"]
        return (
            f"color: {fg}; font-size: 12px; background: {bg};"
            f" border: 1px solid {border}; border-radius: 12px;"
            f" padding: 12px 14px;"
        )

    def _show_status(self, message: str, tone: str = "warning"):
        self.status.setStyleSheet(self._status_style(tone))
        self.status.setText(message)
        self.status.show()

    def _refresh_mode_buttons(self):
        for mode, button in self._mode_buttons.items():
            is_active = mode == self._media_mode
            button.setChecked(is_active)
            button.setStyleSheet(mode_button_style(active=is_active))

    def _set_media_mode(self, media_mode: str):
        if media_mode not in MEDIA_MODES or media_mode == self._media_mode:
            self._refresh_mode_buttons()
            return
        self._media_mode = media_mode
        self._refresh_mode_buttons()
        self.drop_zone.set_idle(self._media_mode)
        if self._last_paths:
            self._scan_paths(self._last_paths)

    def _open_folder_dialog(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Scan",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if path:
            resolved = sanitize_path(path)
            if resolved and resolved.is_dir():
                self._scan_paths([resolved])

    def _toggle_hidden(self):
        self._include_hidden = not self._include_hidden
        self._hidden_action.setChecked(self._include_hidden)
        state = "On" if self._include_hidden else "Off"
        self._hidden_btn.setText(f"Hidden: {state}")
        if self._last_paths:
            self._scan_paths(self._last_paths)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._worker and self._worker.isRunning():
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.set_hover(self._media_mode)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_zone.set_idle(self._media_mode)

    def dropEvent(self, event: QDropEvent):
        self.drop_zone.set_idle(self._media_mode)
        if self._worker and self._worker.isRunning():
            event.ignore()
            return
        mime: QMimeData = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        event.acceptProposedAction()
        self.status.hide()

        errors: list[str] = []
        valid_paths: list[Path] = []

        for url in mime.urls():
            raw = url.toLocalFile()
            path = sanitize_path(raw)
            if path is None:
                errors.append(f"Could not resolve path: {sanitize_name(raw)}")
                continue
            if not path.is_dir():
                errors.append(f"Skipped (not a folder): {sanitize_name(path.name)}")
                continue
            valid_paths.append(path)

        if errors:
            self._show_status("\n".join(errors), "warning")

        if not valid_paths:
            if not errors:
                self._show_status("No valid folders were dropped.", "warning")
            return

        self._scan_paths(valid_paths)

    def _scan_paths(self, paths: list[Path]):
        if self._worker and self._worker.isRunning():
            return
        self._last_paths = paths
        self._clear_results()
        self.status.hide()

        lead = (
            sanitize_name(paths[0].name) if len(paths) == 1 else f"{len(paths)} folders"
        )
        self.drop_zone.set_scanning(
            f"Scanning {lead}",
            f"Scanning {media_mode_summary_label(self._media_mode)} in all folders.",
        )

        self._worker = ScanWorker(paths, include_hidden=self._include_hidden)
        self._worker.folder_ready.connect(self._on_folder_ready)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_scan_progress(self, folder_name: str, dirs_scanned: int):
        self.drop_zone.set_scanning(
            f"Scanning {sanitize_name(folder_name)}",
            f"{dirs_scanned} folders indexed so far.",
        )

    def _on_folder_ready(
        self,
        index: int,
        folder_path: Path,
        ext_counts: dict,
        tree_data: list,
        warnings: list,
    ):
        card = FolderResultCard(
            index,
            folder_path,
            ext_counts,
            tree_data,
            warnings,
            include_hidden=self._include_hidden,
            media_mode=self._media_mode,
        )
        card.rescan_requested.connect(self._on_rescan_requested)
        card.status_requested.connect(self._queue_status)
        self.main_layout.addWidget(card)
        self.results_widgets.append(card)

    def _on_all_done(self):
        self.drop_zone.set_idle(self._media_mode)
        self._worker = None
        if self._pending_status is not None:
            message, tone = self._pending_status
            self._pending_status = None
            self._show_status(message, tone)

    def _queue_status(self, message: str, tone: str):
        self._pending_status = (message, tone)

    def _on_rescan_requested(self, _path: object):
        if self._worker and self._worker.isRunning():
            return
        self._scan_paths(self._last_paths)

    def _clear_results(self):
        for w in self.results_widgets:
            self.main_layout.removeWidget(w)
            w.deleteLater()
        self.results_widgets.clear()


def _clear_layout(layout: QLayout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _filtered_extension_counts(
    ext_counts: dict[str, int], selected_extension: str
) -> dict[str, int]:
    if selected_extension == EXTENSION_FILTER_ALL:
        return dict(ext_counts)
    count = ext_counts.get(selected_extension, 0)
    return {selected_extension: count} if count else {}


def _display_folder_count(stats: SubtreeStats) -> int:
    if not stats.is_dir:
        return 0
    return stats.total_dirs


class TopExtensionBars(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("top_extension_bars")
        self.setStyleSheet(f"""
            QFrame#top_extension_bars {{
                background: {C["surface"]};
                border: 1px solid {C["border"]};
                border-top: 1px solid {C["border_shine"]};
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Extension Counts")
        title.setStyleSheet(
            f"color: {C['heading']}; font-size: 20px; font-weight: 700;"
            f" background: transparent;"
        )
        root.addWidget(title)

        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(10)
        root.addLayout(self._rows)

    def set_counts(self, ext_counts: dict[str, int]):
        _clear_layout(self._rows)
        if not ext_counts:
            empty = QLabel("No extensions in this selection.")
            empty.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 12px; background: transparent;"
            )
            self._rows.addWidget(empty)
            return

        top_items = list(ext_counts.items())[:6]
        max_value = max(count for _, count in top_items) or 1
        for index, (ext, count) in enumerate(top_items):
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            color = extension_color(ext)

            label = QLabel(ext or "no ext")
            label.setFixedWidth(54)
            label.setStyleSheet(
                f"color: {color}; font-size: 14px; font-weight: 700;"
                f" background: transparent;"
            )
            layout.addWidget(label)

            bar = QProgressBar()
            bar.setRange(0, max_value)
            bar.setValue(count)
            bar.setTextVisible(False)
            bar.setFixedHeight(12)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {C["surface_panel"]};
                    border: 1px solid {C["border"]};
                    border-radius: 6px;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 6px;
                }}
            """)
            layout.addWidget(bar, 1)

            count_label = QLabel(f"{count:,}")
            count_label.setFixedWidth(48)
            count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_label.setStyleSheet(
                f"color: {color}; font-size: 14px; font-weight: 700;"
                f" background: transparent;"
            )
            layout.addWidget(count_label)

            self._rows.addWidget(row)

        self._rows.addStretch()


class FolderTreePane(QFrame):
    path_selected = Signal(str)
    DEFAULT_TITLE = "Contents"
    DEFAULT_COPY = "Click any column to sort. Select a row to inspect it."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("folder_tree_pane")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QFrame#folder_tree_pane {{
                background: {C["surface"]};
                border: 1px solid {C["border"]};
                border-top: 1px solid {C["border"]};
                border-radius: 18px;
            }}
        """)

        self._snapshot: ScanSnapshot | None = None
        self._sort_column: int = TREE_COLUMN_TITLE
        self._sort_ascending: bool = True
        self._path_item_map: dict[str, QTreeWidgetItem] = {}
        self._metadata_worker: MetadataWorker | None = None
        self._expansion_workers: list[MetadataWorker] = []
        self._retired_workers: list[MetadataWorker] = []

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_workers)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        root.setSpacing(SPACE_SM)

        eyebrow = QLabel("Structure")
        eyebrow.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 0.6px; background: transparent;"
        )
        root.addWidget(eyebrow)

        self._title = QLabel(self.DEFAULT_TITLE)
        self._title.setStyleSheet(
            f"color: {C['heading']}; font-size: 20px; font-weight: 700;"
            f" background: transparent;"
        )
        root.addWidget(self._title)

        self._path_label = QLabel("Load a folder to browse and sort its items.")
        self._path_label.setWordWrap(True)
        self._path_label.setMaximumWidth(420)
        self._path_label.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px; background: transparent;"
        )
        root.addWidget(self._path_label)

        self._tree = QTreeWidget()
        self._configure_tree_widget()
        root.addWidget(self._tree, 1)

        self._empty = QLabel("Drop or choose one folder to load the Structura workspace.")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setMinimumWidth(320)
        self._empty.setMaximumWidth(380)
        self._empty.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
            f" background: {C['surface_raised']}; border: 1px solid {C['border']};"
            f" border-top: 1px solid {C['border_shine']}; border-radius: 16px;"
            f" padding: 28px 34px;"
        )
        root.addWidget(self._empty, 1, Qt.AlignHCenter | Qt.AlignVCenter)

        self.reset()

    def reset(self):
        self._snapshot = None
        self._title.setText(self.DEFAULT_TITLE)
        self._path_label.setText("Load a folder to browse and sort its items.")
        self._tree.clear()
        self._tree.hide()
        self._empty.show()

    def _retire_worker(self, worker: MetadataWorker | None) -> None:
        if worker is None:
            return
        worker.cancel()
        if worker.isFinished():
            worker.deleteLater()
            return
        self._retired_workers.append(worker)

        def _release_worker() -> None:
            try:
                self._retired_workers.remove(worker)
            except ValueError:
                pass
            worker.deleteLater()

        worker.finished.connect(_release_worker)

    def _shutdown_workers(self) -> None:
        workers: list[MetadataWorker] = []
        if self._metadata_worker is not None:
            workers.append(self._metadata_worker)
            self._metadata_worker = None
        workers.extend(self._expansion_workers)
        self._expansion_workers.clear()
        workers.extend(self._retired_workers)
        self._retired_workers.clear()

        seen: set[int] = set()
        for worker in workers:
            worker_id = id(worker)
            if worker_id in seen:
                continue
            seen.add(worker_id)
            worker.cancel()
            worker.wait(1000)
            worker.deleteLater()

    def set_snapshot(self, snapshot: ScanSnapshot):
        is_new_snapshot = snapshot is not self._snapshot
        self._snapshot = snapshot
        self._title.setText(self.DEFAULT_TITLE)
        self._path_label.setText(self.DEFAULT_COPY)
        self._tree.clear()
        self._empty.hide()
        self._tree.show()
        self._apply_column_widths()

        sorted_data = _sort_tree_data(snapshot.tree_data, self._sort_column, self._sort_ascending)
        # Suppress repaints during bulk item creation to avoid per-insert redraws
        self._tree.setUpdatesEnabled(False)
        try:
            _populate_tree_lazy(self._tree, sorted_data)
        finally:
            self._tree.setUpdatesEnabled(True)
        self._tree.clearSelection()

        # Rebuild path→item map (items are recreated even on re-sort)
        self._path_item_map = {}
        self._build_path_item_map(self._tree.invisibleRootItem())

        # Only cancel/restart metadata workers when a genuinely new folder is loaded.
        # On re-sort the snapshot identity is the same — in-flight workers keep running
        # and will correctly update the new items via the rebuilt path-item map.
        if is_new_snapshot:
            if self._metadata_worker is not None:
                self._retire_worker(self._metadata_worker)
                self._metadata_worker = None
            for w in self._expansion_workers:
                self._retire_worker(w)
            self._expansion_workers.clear()

            file_paths = []
            for path, item in self._path_item_map.items():
                if item.text(TREE_COLUMN_TITLE).startswith("📁"):
                    continue
                ext = Path(path).suffix.lower()
                if ext in VIDEO_EXTENSIONS or ext in IMAGE_EXTENSIONS:
                    file_paths.append((path, ext))
            if file_paths:
                self._metadata_worker = MetadataWorker(file_paths)
                self._metadata_worker.chunk_ready.connect(self._on_metadata_chunk)
                self._metadata_worker.start()
            else:
                self._metadata_worker = None

    def _on_header_clicked(self, column: int):
        if column == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        order = Qt.AscendingOrder if self._sort_ascending else Qt.DescendingOrder
        self._tree.header().setSortIndicator(self._sort_column, order)
        if self._snapshot:
            self.set_snapshot(self._snapshot)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        for index in range(item.childCount()):
            child = item.child(index)
            if child.data(0, Qt.UserRole) == TREE_LAZY_SENTINEL:
                _expand_lazy_placeholder(self._tree, child)
                # Register newly created items and fetch their metadata
                new_paths: list[tuple[str, str]] = []
                for i in range(item.childCount()):
                    c = item.child(i)
                    path = c.data(0, Qt.UserRole)
                    if isinstance(path, str) and path and path != TREE_LAZY_SENTINEL:
                        if path not in self._path_item_map:
                            self._path_item_map[path] = c
                            ext = Path(path).suffix.lower()
                            if ext in VIDEO_EXTENSIONS or ext in IMAGE_EXTENSIONS:
                                new_paths.append((path, ext))
                if new_paths:
                    worker = MetadataWorker(new_paths)
                    worker.chunk_ready.connect(self._on_metadata_chunk)
                    self._expansion_workers.append(worker)
                    worker.start()
                break

    def _build_path_item_map(self, parent_item: QTreeWidgetItem):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            path = child.data(0, Qt.UserRole)
            if isinstance(path, str) and path and path != TREE_LAZY_SENTINEL:
                self._path_item_map[path] = child
            self._build_path_item_map(child)

    def _on_metadata_chunk(self, results: dict):
        for path, exif in results.items():
            item = self._path_item_map.get(path)
            if item is None:
                continue
            item.setText(TREE_COLUMN_GPS, _format_gps_display(exif.gps))
            item.setToolTip(TREE_COLUMN_GPS, exif.gps or "")
            item.setText(TREE_COLUMN_MAKE, _format_make_display(exif.make))
            item.setToolTip(TREE_COLUMN_MAKE, exif.make or "")
            item.setText(TREE_COLUMN_MODEL, _format_model_display(exif.model))
            item.setToolTip(TREE_COLUMN_MODEL, exif.model or "")

    def _on_selection_changed(self):
        if not self._snapshot:
            return
        item = self._tree.currentItem()
        if item is None:
            return
        path_str = item.data(0, Qt.UserRole)
        if isinstance(path_str, str) and path_str and path_str != TREE_LAZY_SENTINEL:
            self.path_selected.emit(path_str)

    def _configure_tree_widget(self) -> None:
        self._tree.setHeaderLabels(list(TREE_HEADERS))
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(14)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setTextElideMode(Qt.ElideRight)

        header = self._tree.header()
        header.setSectionsClickable(True)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setMinimumSectionSize(36)
        header.setStretchLastSection(False)
        header.setSortIndicatorShown(True)
        for column, _ in TREE_COLUMN_WIDTHS:
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        _centered_header_cols = (
            TREE_COLUMN_RESOLUTION, TREE_COLUMN_FRAME_RATE, TREE_COLUMN_EDITED,
            TREE_COLUMN_ORIENTATION, TREE_COLUMN_GPS, TREE_COLUMN_MAKE, TREE_COLUMN_MODEL,
        )
        for col in _centered_header_cols:
            self._tree.headerItem().setTextAlignment(col, Qt.AlignHCenter | Qt.AlignVCenter)

        self._tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._tree.setStyleSheet(tree_style(background=PANEL_BG_SOFT))
        self._tree.setSortingEnabled(False)
        self._tree.header().setSortIndicator(TREE_COLUMN_TITLE, Qt.AscendingOrder)
        self._tree.header().sectionClicked.connect(self._on_header_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

    def _apply_column_widths(self) -> None:
        for column, width in TREE_COLUMN_WIDTHS:
            self._tree.setColumnWidth(column, width)

    def closeEvent(self, event):
        self._shutdown_workers()
        super().closeEvent(event)

    def deleteLater(self):
        self._shutdown_workers()
        super().deleteLater()

    def __del__(self):
        try:
            self._shutdown_workers()
        except Exception:
            pass


class AnalyzerDashboard(QWidget):
    sort_requested = Signal()
    media_mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(DASHBOARD_MIN_WIDTH)
        self._snapshot: ScanSnapshot | None = None
        self._selected_stats: SubtreeStats | None = None
        self._include_hidden = True
        self._media_mode = "both"
        self._suspend_filter_signal = False
        self._sort_preview_cache: "SortPreview | None" = None
        self._sort_preview_cache_key: tuple = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACE_MD)

        self._empty_state = DropZone()
        self._empty_state.setMinimumHeight(236)
        self._empty_state.setMaximumWidth(680)
        root.addWidget(self._empty_state, 0, Qt.AlignHCenter | Qt.AlignVCenter)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)
        root.addWidget(self._content)

        self._header_block = QWidget()
        self._header_block.setStyleSheet("background: transparent;")
        header_layout = QVBoxLayout(self._header_block)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self._selection_title = QLabel("Folder Overview")
        self._selection_title.setStyleSheet(
            f"color: {C['heading']}; font-size: 33px; font-weight: 760;"
        )
        header_layout.addWidget(self._selection_title)

        self._selection_summary = QLabel("")
        self._selection_summary.setTextFormat(Qt.RichText)
        self._selection_summary.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
        )
        self._selection_summary.hide()
        header_layout.addWidget(self._selection_summary)

        self._selection_metrics = QWidget()
        self._selection_metrics.setStyleSheet("background: transparent;")
        metrics_layout = QHBoxLayout(self._selection_metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(SPACE_SM)
        self._files_metric = OverviewStatChip("Files")
        self._size_metric = OverviewStatChip("Space")
        self._folders_metric = OverviewStatChip("Folders")
        metrics_layout.addWidget(self._files_metric)
        metrics_layout.addWidget(self._size_metric)
        metrics_layout.addWidget(self._folders_metric)
        header_layout.addWidget(self._selection_metrics)

        self._selection_subtitle = QLabel("")
        self._selection_subtitle.setWordWrap(True)
        self._selection_subtitle.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px;"
        )
        header_layout.addWidget(self._selection_subtitle)
        content_layout.addWidget(self._header_block)

        self._overview_surface = QFrame()
        self._overview_surface.setObjectName("overview_surface")
        self._overview_surface.setStyleSheet(f"""
            QFrame#overview_surface {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff,
                    stop:1 #f8fbff
                );
                border: 1px solid {C["border_light"]};
                border-radius: 22px;
            }}
            QLabel {{
                background: transparent;
            }}
            QComboBox {{
                min-height: 34px;
                padding: 0 12px;
                background: {C["surface"]};
                border: 1px solid {C["border_light"]};
                border-radius: 10px;
                color: {C["text"]};
                font-size: 13px;
            }}
            QComboBox:hover {{
                border: 1px solid {C["accent_glow"]};
                background: {C["surface_raised"]};
            }}
            QComboBox:focus {{
                border: 1px solid {C["accent"]};
                background: {C["surface_raised"]};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
                background: transparent;
            }}
        """)
        overview_layout = QVBoxLayout(self._overview_surface)
        overview_layout.setContentsMargins(24, 24, 24, 24)
        overview_layout.setSpacing(16)

        analysis_head = QWidget()
        analysis_head.setStyleSheet("background: transparent;")
        analysis_head_layout = QHBoxLayout(analysis_head)
        analysis_head_layout.setContentsMargins(0, 0, 0, 0)
        analysis_head_layout.setSpacing(SPACE_MD)

        analysis_copy_block = QWidget()
        analysis_copy_block.setStyleSheet("background: transparent;")
        analysis_copy_layout = QVBoxLayout(analysis_copy_block)
        analysis_copy_layout.setContentsMargins(0, 0, 0, 0)
        analysis_copy_layout.setSpacing(4)

        analysis_title = QLabel("What's Here")
        analysis_title.setStyleSheet(
            f"color: {C['heading']}; font-size: 25px; font-weight: 760;"
        )
        analysis_copy_layout.addWidget(analysis_title)

        self._analysis_intro = QLabel("")
        self._analysis_intro.setWordWrap(True)
        self._analysis_intro.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 14px;"
        )
        analysis_copy_layout.addWidget(self._analysis_intro)
        analysis_head_layout.addWidget(analysis_copy_block, 1)

        filter_wrap = QWidget()
        filter_wrap.setStyleSheet("background: transparent;")
        filter_layout = QHBoxLayout(filter_wrap)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(SPACE_XS)
        filter_label = QLabel("Filter")
        filter_label.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 0.8px;"
        )
        filter_layout.addWidget(filter_label)
        self._extension_filter = QComboBox()
        self._extension_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._extension_filter.setMinimumWidth(210)
        filter_layout.addWidget(self._extension_filter)
        analysis_head_layout.addWidget(filter_wrap, 0, Qt.AlignTop)
        overview_layout.addWidget(analysis_head)

        self._chart_body = QWidget()
        self._chart_body.setStyleSheet("background: transparent;")
        self._chart_body_layout = QHBoxLayout(self._chart_body)
        self._chart_body_layout.setContentsMargins(0, 0, 0, 0)
        self._chart_body_layout.setSpacing(22)
        overview_layout.addWidget(self._chart_body)

        self._table_divider = QFrame()
        self._table_divider.setFixedHeight(1)
        self._table_divider.setStyleSheet(f"background: {C['border_light']}; border: none;")
        overview_layout.addWidget(self._table_divider)

        self._table_intro = QLabel("Complete file-type list")
        self._table_intro.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px; font-weight: 700;"
            f" letter-spacing: 0.8px;"
        )
        overview_layout.addWidget(self._table_intro)

        self._table_host = QWidget()
        self._table_host.setStyleSheet("background: transparent;")
        self._table_layout = QVBoxLayout(self._table_host)
        self._table_layout.setContentsMargins(0, 0, 0, 0)
        self._table_layout.setSpacing(0)
        overview_layout.addWidget(self._table_host)
        content_layout.addWidget(self._overview_surface)

        self._file_inspector = QFrame()
        self._file_inspector.setObjectName("file_inspector")
        self._file_inspector.setStyleSheet(f"""
            QFrame#file_inspector {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff,
                    stop:1 #f8fbff
                );
                border: 1px solid {C["border_light"]};
                border-radius: 22px;
            }}
            QFrame#inspector_preview_card {{
                background: {C["tbl_header_bg"]};
                border: 1px solid {C["accent_glow"]};
                border-top: 1px solid {C["border_shine"]};
                border-radius: 20px;
            }}
            QFrame#inspector_footer {{
                background: {C["surface"]};
                border: 1px solid {C["border_light"]};
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        inspector_layout = QVBoxLayout(self._file_inspector)
        inspector_layout.setContentsMargins(24, 24, 24, 24)
        inspector_layout.setSpacing(18)

        self._file_header_row = QWidget()
        self._file_header_row.setStyleSheet("background: transparent;")
        file_header_layout = QHBoxLayout(self._file_header_row)
        file_header_layout.setContentsMargins(0, 0, 0, 0)
        file_header_layout.setSpacing(18)

        self._fh_preview_card = QFrame()
        self._fh_preview_card.setObjectName("inspector_preview_card")
        self._fh_preview_card.setFixedWidth(220)
        preview_layout = QVBoxLayout(self._fh_preview_card)
        preview_layout.setContentsMargins(20, 18, 20, 18)
        preview_layout.setSpacing(6)

        preview_eyebrow = QLabel("SELECTED FILE")
        preview_eyebrow.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.2px;"
        )
        preview_layout.addWidget(preview_eyebrow)

        self._fh_preview_badge = QLabel("FILE")
        self._fh_preview_badge.setStyleSheet(
            f"color: {C['heading']}; font-size: 34px; font-weight: 780;"
            f" letter-spacing: 0.4px;"
        )
        preview_layout.addWidget(self._fh_preview_badge)

        self._fh_preview_caption = QLabel("File")
        self._fh_preview_caption.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px; font-weight: 600;"
        )
        preview_layout.addWidget(self._fh_preview_caption)

        self._fh_preview_detail = QLabel("")
        self._fh_preview_detail.setWordWrap(True)
        self._fh_preview_detail.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 12px;"
        )
        preview_layout.addWidget(self._fh_preview_detail)
        preview_layout.addStretch()

        file_header_layout.addWidget(self._fh_preview_card, 0, Qt.AlignTop)

        details_col = QWidget()
        details_col.setStyleSheet("background: transparent;")
        details_layout = QVBoxLayout(details_col)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)

        self._fh_meta_label = QLabel("")
        self._fh_meta_label.setStyleSheet(
            f"color: {C['accent_hover']}; font-size: 12px; font-weight: 700;"
            f" letter-spacing: 0.8px;"
        )
        details_layout.addWidget(self._fh_meta_label)

        self._fh_name_label = QLabel("")
        self._fh_name_label.setWordWrap(True)
        self._fh_name_label.setStyleSheet(
            f"color: {C['heading']}; font-size: 34px; font-weight: 760;"
        )
        details_layout.addWidget(self._fh_name_label)

        self._fh_path_label = QLabel("")
        self._fh_path_label.setWordWrap(True)
        self._fh_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._fh_path_label.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
        )
        details_layout.addWidget(self._fh_path_label)
        details_layout.addStretch()
        file_header_layout.addWidget(details_col, 1)
        inspector_layout.addWidget(self._file_header_row)

        metadata_grid = QGridLayout()
        metadata_grid.setContentsMargins(0, 0, 0, 0)
        metadata_grid.setHorizontalSpacing(10)
        metadata_grid.setVerticalSpacing(10)

        def _make_info_tile(label_text: str) -> tuple[QFrame, QLabel]:
            frame = QFrame()
            frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            frame.setMinimumHeight(76)
            frame.setStyleSheet(f"""
                QFrame {{
                    background: {C['surface']};
                    border: 1px solid {C['border_light']};
                    border-top: 1px solid {C['border_shine']};
                    border-radius: 14px;
                }}
            """)
            tile_layout = QVBoxLayout(frame)
            tile_layout.setContentsMargins(14, 10, 14, 12)
            tile_layout.setSpacing(3)
            lbl = QLabel(label_text.upper())
            lbl.setStyleSheet(
                f"color: {C['text_dim']}; font-size: 10px; font-weight: 700;"
                f" letter-spacing: 1px;"
            )
            val = QLabel("—")
            val.setWordWrap(True)
            val.setMinimumHeight(28)
            val.setStyleSheet(
                f"color: {C['heading']}; font-size: 20px; font-weight: 730;"
            )
            tile_layout.addWidget(lbl)
            tile_layout.addWidget(val)
            return frame, val

        self._fh_tile_frames: list[QFrame] = []

        def _place_tile(row: int, column: int, label_text: str) -> QLabel:
            frame, value_label = _make_info_tile(label_text)
            self._fh_tile_frames.append(frame)
            metadata_grid.addWidget(frame, row, column)
            return value_label

        self._fh_kind_val = _place_tile(0, 0, "Kind")
        self._fh_size_val = _place_tile(0, 1, "Size")
        self._fh_resolution_val = _place_tile(0, 2, "Resolution")
        self._fh_fps_val = _place_tile(1, 0, "Frame Rate")
        self._fh_orientation_val = _place_tile(1, 1, "Orientation")
        self._fh_modified_val = _place_tile(1, 2, "Modified")
        inspector_layout.addLayout(metadata_grid)

        footer_row = QFrame()
        footer_row.setObjectName("inspector_footer")
        action_layout = QHBoxLayout(footer_row)
        action_layout.setContentsMargins(16, 14, 16, 14)
        action_layout.setSpacing(SPACE_SM)

        self._reveal_button = QPushButton("Reveal in Finder")
        self._reveal_button.setCursor(Qt.PointingHandCursor)
        self._reveal_button.setStyleSheet(button_style())
        self._reveal_button.clicked.connect(self._reveal_selected_file)
        action_layout.addWidget(self._reveal_button, 0, Qt.AlignLeft)

        self._inspector_context_label = QLabel("")
        self._inspector_context_label.setWordWrap(True)
        self._inspector_context_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._inspector_context_label.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
        )
        action_layout.addWidget(self._inspector_context_label, 1)
        inspector_layout.addWidget(footer_row)
        content_layout.addWidget(self._file_inspector)

        self._action_section = QWidget()
        self._action_section.setStyleSheet("background: transparent;")
        action_layout = QVBoxLayout(self._action_section)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        action_divider = QFrame()
        action_divider.setFixedHeight(1)
        action_divider.setStyleSheet(f"background: {C['border_light']}; border: none;")
        action_layout.addWidget(action_divider)

        action_eyebrow = QLabel("NEXT STEP")
        action_eyebrow.setStyleSheet(
            f"color: {C['accent']}; font-size: 11px; font-weight: 700;"
            f" letter-spacing: 1.6px;"
        )
        action_layout.addWidget(action_eyebrow)

        sort_title = QLabel("Ready to organize")
        sort_title.setStyleSheet(
            f"color: {C['heading']}; font-size: 22px; font-weight: 700;"
        )
        action_layout.addWidget(sort_title)

        sort_copy = QLabel(
            "Create extension folders throughout the loaded folder."
        )
        sort_copy.setWordWrap(True)
        sort_copy.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px;"
        )
        action_layout.addWidget(sort_copy)

        controls_row = QWidget()
        controls_row.setStyleSheet("background: transparent;")
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(SPACE_SM)

        mode_group = QWidget()
        mode_group.setObjectName("dashboard_mode_group")
        mode_group.setStyleSheet(f"""
            QWidget#dashboard_mode_group {{
                background: {C["surface"]};
                border: 1px solid {C["border_light"]};
                border-radius: 12px;
            }}
        """)
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setContentsMargins(6, 6, 6, 6)
        mode_layout.setSpacing(6)
        self._mode_buttons: dict[str, QPushButton] = {}
        for mode in MEDIA_MODES:
            button = QPushButton(MEDIA_MODE_LABELS[mode])
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked, selected_mode=mode: self.media_mode_changed.emit(
                    selected_mode
                )
            )
            self._mode_buttons[mode] = button
            mode_layout.addWidget(button)
        controls_layout.addWidget(mode_group, 1)

        self._sort_button = QPushButton("Organize Media")
        self._sort_button.setCursor(Qt.PointingHandCursor)
        self._sort_button.setMinimumHeight(40)
        self._sort_button.setStyleSheet(button_style(variant="primary"))
        self._sort_button.clicked.connect(self.sort_requested.emit)
        controls_layout.addWidget(self._sort_button, 0, Qt.AlignRight)
        action_layout.addWidget(controls_row)

        self._sort_preview = QLabel("")
        self._sort_preview.setWordWrap(True)
        self._sort_preview.setStyleSheet(
            f"color: {C['heading']}; font-size: 18px; font-weight: 650;"
        )
        action_layout.addWidget(self._sort_preview)

        self._sort_targets_host = QWidget()
        self._sort_targets_host.setStyleSheet("background: transparent;")
        self._sort_targets_layout = QHBoxLayout(self._sort_targets_host)
        self._sort_targets_layout.setContentsMargins(0, 0, 0, 0)
        self._sort_targets_layout.setSpacing(SPACE_XS)
        action_layout.addWidget(self._sort_targets_host)

        self._sort_note = QLabel("")
        self._sort_note.setWordWrap(True)
        self._sort_note.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 12px;"
        )
        action_layout.addWidget(self._sort_note)
        overview_layout.addWidget(self._action_section)

        content_layout.addStretch()
        self.set_empty()

    def set_empty(self):
        self._snapshot = None
        self._selected_stats = None
        self._sort_targets_host.hide()
        self._content.hide()
        self._empty_state.show()
        self._empty_state.set_idle("both")

    def set_hover(self):
        self._content.hide()
        self._empty_state.show()
        self._empty_state.set_hover("both")

    def set_scanning(self, folder_name: str, detail: str):
        self._content.hide()
        self._empty_state.show()
        self._empty_state.set_scanning(folder_name, detail)

    def set_sorting(self, active: bool):
        self._sort_button.setEnabled(not active)
        self._sort_button.setText("Organizing Media…" if active else "Organize Media")

    def set_snapshot(
        self,
        snapshot: ScanSnapshot,
        selected_stats: SubtreeStats,
        *,
        include_hidden: bool,
        media_mode: str,
        reset_filter: bool = False,
    ):
        new_key = (snapshot.root_path, include_hidden, media_mode)
        if new_key != self._sort_preview_cache_key:
            self._sort_preview_cache = None
            self._sort_preview_cache_key = ()
        self._snapshot = snapshot
        self._selected_stats = selected_stats
        self._include_hidden = include_hidden
        self._media_mode = media_mode
        self._content.show()
        self._empty_state.hide()
        self._refresh_mode_buttons()
        self._rebuild_extension_filter(reset_selection=reset_filter)
        self._refresh_view()
        self.set_sorting(False)

    def _refresh_mode_buttons(self):
        for mode, button in self._mode_buttons.items():
            button.setChecked(mode == self._media_mode)
            button.setStyleSheet(mode_button_style(active=mode == self._media_mode))

    def _rebuild_extension_filter(self, *, reset_selection: bool = False):
        selected_key = (
            EXTENSION_FILTER_ALL
            if reset_selection
            else self._extension_filter.currentData()
        )
        self._suspend_filter_signal = True
        self._extension_filter.clear()
        self._extension_filter.addItem("All Extensions", EXTENSION_FILTER_ALL)
        if self._selected_stats:
            for ext in self._selected_stats.ext_counts:
                self._extension_filter.addItem(extension_display_label(ext), ext)
        target_index = self._extension_filter.findData(selected_key)
        if target_index < 0:
            target_index = 0
        self._extension_filter.setCurrentIndex(target_index)
        self._suspend_filter_signal = False

    def _on_filter_changed(self, index: int):
        if self._suspend_filter_signal:
            return
        self._refresh_view()

    def _refresh_view(self):
        if not self._snapshot or not self._selected_stats:
            return

        stats = self._selected_stats
        filtered_counts = _filtered_extension_counts(
            stats.ext_counts,
            self._extension_filter.currentData() or EXTENSION_FILTER_ALL,
        )
        if stats.is_dir:
            self._show_folder_overview(stats, filtered_counts)
        else:
            self._show_file_inspector(stats)

    def _show_folder_overview(
        self,
        stats: "SubtreeStats",
        filtered_counts: dict[str, int],
    ) -> None:
        self._header_block.show()
        self._overview_surface.show()
        self._action_section.show()
        self._file_inspector.hide()

        folder_count = _display_folder_count(stats)
        self._selection_title.setText(sanitize_name(stats.name))
        self._selection_summary.hide()
        self._files_metric.set_value(f"{stats.total_files:,}")
        self._size_metric.set_value(_human_size(stats.total_size_bytes))
        self._folders_metric.set_value(f"{folder_count:,}")
        if stats.path == str(self._snapshot.root_path):
            subtitle = f"Loaded folder · {self._snapshot.root_path}"
        else:
            stats_path = Path(stats.path)
            try:
                relative_path = stats_path.relative_to(self._snapshot.root_path).as_posix()
            except ValueError:
                relative_path = stats.path
            subtitle = f"Inside {self._snapshot.root_path.name} · {relative_path}"
        self._selection_subtitle.setText(subtitle)
        self._selection_subtitle.setToolTip(stats.path)

        current_filter = self._extension_filter.currentData() or EXTENSION_FILTER_ALL
        if not filtered_counts:
            self._analysis_intro.setText("No files match the current filter in this selection.")
        elif current_filter != EXTENSION_FILTER_ALL:
            self._analysis_intro.setText(
                f"Focused on {extension_display_label(str(current_filter))} files in this selection."
            )
        else:
            top_ext, top_count = next(iter(filtered_counts.items()))
            total = sum(filtered_counts.values()) or 1
            pct = round(top_count / total * 100)
            self._analysis_intro.setText(
                f"{extension_display_label(top_ext)} leads this selection at {pct}%. "
                f"{len(filtered_counts)} file types are visible."
            )

        _clear_layout(self._chart_body_layout)
        if filtered_counts:
            self._chart_body_layout.addWidget(PieChart(filtered_counts), 0, Qt.AlignTop)
            self._chart_body_layout.addWidget(PieChartLegend(filtered_counts), 1)
        else:
            empty = QLabel("No extensions match the current filter.")
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 13px;"
            )
            self._chart_body_layout.addWidget(empty)

        _clear_layout(self._table_layout)
        show_table = len(filtered_counts) > 8
        self._table_divider.setVisible(show_table)
        self._table_intro.setVisible(show_table)
        self._table_host.setVisible(show_table)
        if show_table:
            table = ExtensionTable(
                filtered_counts,
                left_header="Extension",
                label_transform=extension_display_label,
            )
            self._table_layout.addWidget(table)

        self._refresh_sort_section()

    def _show_file_inspector(self, stats: "SubtreeStats") -> None:
        self._header_block.hide()
        self._overview_surface.hide()
        self._action_section.hide()
        self._file_inspector.show()

        ext = Path(stats.path).suffix.lower()
        emoji = file_emoji(ext, is_dir=False) or "•"
        created_ts, modified_ts, video_info = _file_browser_metadata(
            stats.path,
            is_dir=False,
            ext=ext,
        )
        self._fh_meta_label.setText(
            f"{emoji} {extension_display_label(ext)} · {_format_browser_date(created_ts)}"
            if created_ts is not None
            else f"{emoji} {extension_display_label(ext)}"
        )
        preview_label = extension_display_label(ext) if ext else "FILE"
        preview_detail_parts: list[str] = []
        if video_info is not None and video_info.resolution:
            preview_detail_parts.append(video_info.resolution)
        if video_info is not None and video_info.fps_category is not None:
            preview_detail_parts.append(f"{video_info.fps_category} fps")
        if not preview_detail_parts and stats.total_size_bytes:
            preview_detail_parts.append(_human_size(stats.total_size_bytes))
        self._fh_preview_badge.setText(preview_label)
        self._fh_preview_badge.setStyleSheet(
            f"color: {extension_color(ext)}; font-size: 34px; font-weight: 780;"
            f" letter-spacing: 0.4px;"
        )
        self._fh_preview_caption.setText(file_kind_label(ext))
        self._fh_preview_detail.setText(" · ".join(preview_detail_parts) if preview_detail_parts else "Quick file summary")
        self._fh_name_label.setText(sanitize_name(stats.name))
        self._fh_name_label.setToolTip(stats.name)
        set_elided_label_text(self._fh_path_label, stats.path, 720, Qt.ElideMiddle)

        self._fh_kind_val.setText(extension_display_label(ext))
        self._fh_size_val.setText(
            _human_size(stats.total_size_bytes) if stats.total_size_bytes else "—"
        )
        self._fh_resolution_val.setText(
            video_info.resolution if video_info is not None else "—"
        )
        if video_info is not None:
            self._fh_fps_val.setText(_format_frame_rate_display(video_info))
            self._fh_fps_val.setToolTip(_format_frame_rate_tooltip(video_info))
            self._fh_orientation_val.setText(video_info.orientation)
        else:
            self._fh_fps_val.setText("—")
            self._fh_fps_val.setToolTip("")
            self._fh_orientation_val.setText("—")
        self._fh_modified_val.setText(_format_browser_date(modified_ts) or "—")

        root_name = sanitize_name(self._snapshot.root_path.name)
        self._inspector_context_label.setText(
            f"In {root_name} · {self._snapshot.total_files:,} {pluralize(self._snapshot.total_files, 'file')} · "
            f"{_human_size(self._snapshot.total_size_bytes)} · "
            f"{self._snapshot.total_dirs:,} {pluralize(self._snapshot.total_dirs, 'folder')}"
        )
        self._file_header_row.show()

    def _refresh_sort_section(self):
        if not self._snapshot:
            self._sort_button.setEnabled(False)
            self._sort_preview.setText("Choose a folder to organize media.")
            self._sort_note.clear()
            self._sort_targets_host.hide()
            return

        cache_key = (self._snapshot.root_path, self._include_hidden, self._media_mode)
        if self._sort_preview_cache is not None and self._sort_preview_cache_key == cache_key:
            preview = self._sort_preview_cache
        else:
            preview = collect_sortable_extensions(
                self._snapshot.root_path,
                include_hidden=self._include_hidden,
                media_mode=self._media_mode,
            )
            self._sort_preview_cache = preview
            self._sort_preview_cache_key = cache_key
        _clear_layout(self._sort_targets_layout)
        if preview.ext_counts:
            self._sort_button.setEnabled(True)
            preview_copy = {
                "both": f"{preview.total_sortable:,} matching media files ready to organize.",
                "images": f"{preview.total_sortable:,} photos ready to organize.",
                "videos": f"{preview.total_sortable:,} videos ready to organize.",
            }.get(self._media_mode, f"{preview.total_sortable:,} files ready to organize.")
            self._sort_preview.setText(preview_copy)
            for ext, count in preview.ext_counts.items():
                chip = DestinationFolderChip(
                    extension_folder_name(ext),
                    f"{count:,} {pluralize(count, 'item')}",
                    extension_color(ext),
                )
                self._sort_targets_layout.addWidget(chip)
            self._sort_targets_layout.addStretch()
            self._sort_targets_host.show()
            detail_parts = []
            detail_parts.append("Applies throughout the loaded folder")
            if preview.skipped_other:
                detail_parts.append(
                    f"{preview.skipped_other} other file"
                    f"{'' if preview.skipped_other == 1 else 's'} ignored"
                )
            if preview.skipped_dirs:
                detail_parts.append(
                    f"{preview.skipped_dirs} subfolder"
                    f"{'' if preview.skipped_dirs == 1 else 's'} untouched"
                )
            hidden_state = "included" if self._include_hidden else "excluded"
            detail_parts.append(f"hidden files {hidden_state}")
            self._sort_note.setText(" · ".join(detail_parts) + ".")
        else:
            self._sort_button.setEnabled(False)
            self._sort_preview.setText(media_mode_empty_label(self._media_mode))
            self._sort_note.setText(
                "Structura only organizes files that match the current media mode."
            )
            self._sort_targets_host.hide()

    def _reveal_selected_file(self) -> None:
        if self._selected_stats is None or self._selected_stats.is_dir:
            return
        try:
            subprocess.Popen(["open", "-R", self._selected_stats.path])
        except OSError:
            pass


class StructuraWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Structura")
        self.setMinimumSize(1420, 760)
        self.resize(1600, 900)
        self.setAcceptDrops(True)
        self.setUnifiedTitleAndToolBarOnMac(True)
        self._apply_palette()

        self._worker: ScanWorker | None = None
        self._sort_worker: SortWorker | None = None
        self._include_hidden = True
        self._media_mode = "both"
        self._current_root: Path | None = None
        self._snapshot: ScanSnapshot | None = None
        self._selected_path: str | None = None
        self._pending_status: tuple[str, str] | None = None
        self._pending_scan_path: Path | None = None

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._set_root_label(None)
        self._refresh_hidden_button()

    def _build_menu(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(f"""
            QMenuBar {{
                background: {TOOLBAR_BG_GRADIENT};
                color: {C["text"]};
                border-bottom: 1px solid {C["border"]};
                padding: 3px 10px;
                font-size: 12px;
            }}
            QMenuBar::item {{
                padding: 5px 10px;
                border-radius: 6px;
                background: transparent;
            }}
            QMenuBar::item:selected {{
                background: {PANEL_BG_GRADIENT};
            }}
            QMenu {{
                background: {PANEL_BG_GRADIENT};
                color: {C["text"]};
                border: 1px solid {C["border"]};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {ACCENT_PANEL_GRADIENT};
            }}
        """)

        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Choose Folder…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_folder_dialog)
        file_menu.addAction(open_action)

        rescan_action = QAction("Rescan", self)
        rescan_action.setShortcut("Ctrl+R")
        rescan_action.triggered.connect(self._rescan_current_root)
        file_menu.addAction(rescan_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_action)

        view_menu = menu_bar.addMenu("View")
        self._hidden_action = QAction("Show Hidden Files", self)
        self._hidden_action.setCheckable(True)
        self._hidden_action.setChecked(True)
        self._hidden_action.triggered.connect(self._toggle_hidden)
        view_menu.addAction(self._hidden_action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About Structura", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        dlg = AboutDialog(self)
        dlg.exec()

    def _build_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {TOOLBAR_BG_GRADIENT};
                border-bottom: 1px solid {C["border"]};
                spacing: 12px;
                padding: 12px 18px;
            }}
        """)

        title_block = QWidget()
        title_block.setStyleSheet("background: transparent;")
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        app_title = QLabel("Structura")
        app_title.setStyleSheet(
            f"color: {C['heading']}; font-size: 30px; font-weight: 700;"
        )
        title_layout.addWidget(app_title)

        subtitle = QLabel(
            "Scan a folder, review file types, and organize root-level media when needed."
        )
        subtitle.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
        )
        title_layout.addWidget(subtitle)
        toolbar.addWidget(title_block)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        folder_row = QWidget()
        folder_row.setStyleSheet("background: transparent;")
        folder_layout = QHBoxLayout(folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(8)

        self._path_card = QFrame()
        self._path_card.setObjectName("path_card")
        self._path_card.setStyleSheet(path_card_style(loaded=False))
        path_layout = QHBoxLayout(self._path_card)
        path_layout.setContentsMargins(14, 10, 14, 10)
        path_layout.setSpacing(8)
        self._root_path_label = QLabel("")
        self._root_path_label.setFixedWidth(PATH_LABEL_MAX_WIDTH)
        self._root_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._root_path_label.setStyleSheet(
            f"color: {C['text_secondary']}; font-size: 13px;"
        )
        path_layout.addWidget(self._root_path_label)
        folder_layout.addWidget(self._path_card)

        toolbar.addWidget(folder_row)

        choose_button = QPushButton("Choose Folder…")
        choose_button.setCursor(Qt.PointingHandCursor)
        choose_button.setStyleSheet(button_style(variant="primary"))
        choose_button.setMinimumHeight(40)
        choose_button.clicked.connect(self._open_folder_dialog)
        toolbar.addWidget(choose_button)

        self._hidden_button = QPushButton("Show Hidden")
        self._hidden_button.setCursor(Qt.PointingHandCursor)
        self._hidden_button.setCheckable(True)
        self._hidden_button.setStyleSheet(toolbar_toggle_style(active=True))
        self._hidden_button.setMinimumHeight(40)
        self._hidden_button.clicked.connect(self._toggle_hidden)
        toolbar.addWidget(self._hidden_button)

        self.addToolBar(toolbar)

    def _build_body(self):
        self._status = QLabel("")
        self._status.hide()
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color: {C['warning']}; font-size: 13px; background: {C['warning_bg']};"
            f" border: 1px solid {C['warning_border']}; border-radius: 12px;"
            f" padding: 12px 14px;"
        )

        body = QWidget()
        body.setStyleSheet(f"background: {WINDOW_BG_GRADIENT};")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 16, 18, 18)
        body_layout.setSpacing(12)
        body_layout.addWidget(self._status)

        self._workspace_hero = WorkspaceHero()
        body_layout.addWidget(self._workspace_hero, 1, Qt.AlignCenter)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(12)
        self._splitter.setStyleSheet("""
            QSplitter::handle {{
                background: transparent;
            }}
        """)

        self._tree_pane = FolderTreePane()
        self._tree_pane.path_selected.connect(self._on_tree_path_selected)
        self._splitter.addWidget(self._tree_pane)

        self._dashboard_scroll = QScrollArea()
        self._dashboard_scroll.setWidgetResizable(True)
        self._dashboard_scroll.setFrameShape(QFrame.NoFrame)
        self._dashboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._dashboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._dashboard_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            {scroll_bar_style(C["bg"])}
        """)
        self._dashboard = AnalyzerDashboard()
        self._dashboard.media_mode_changed.connect(self._set_media_mode)
        self._dashboard.sort_requested.connect(self._sort_root_folder)
        self._dashboard_scroll.setWidget(self._dashboard)
        self._splitter.addWidget(self._dashboard_scroll)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([620, 680])

        body_layout.addWidget(self._splitter, 1)
        self.setCentralWidget(body)
        self._show_workspace_hero("idle")

    def _apply_palette(self):
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(C["bg"]))
        pal.setColor(QPalette.WindowText, QColor(C["text"]))
        self.setPalette(pal)

    def closeEvent(self, event):
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(1000)
            self._worker.deleteLater()
            self._worker = None
        if self._sort_worker is not None:
            cancel_sort = getattr(self._sort_worker, "cancel", None)
            if callable(cancel_sort):
                cancel_sort()
            self._sort_worker.wait(1000)
            self._sort_worker.deleteLater()
            self._sort_worker = None
        self._tree_pane._shutdown_workers()
        super().closeEvent(event)

    def _status_style(self, tone: str) -> str:
        if tone == "success":
            return (
                f"color: {C['success']}; font-size: 13px; background: {C['success_bg']};"
                f" border: 1px solid {C['success_border']}; border-radius: 12px;"
                f" padding: 12px 14px;"
            )
        return (
            f"color: {C['warning']}; font-size: 13px; background: {C['warning_bg']};"
            f" border: 1px solid {C['warning_border']}; border-radius: 12px;"
            f" padding: 12px 14px;"
        )

    def _show_status(self, message: str, tone: str = "warning"):
        self._status.setStyleSheet(self._status_style(tone))
        self._status.setText(message)
        self._status.show()

    def _set_root_label(self, path: Path | None):
        if path is None:
            self._path_card.setStyleSheet(path_card_style(loaded=False))
            self._root_path_label.setStyleSheet(
                f"color: {C['text_secondary']}; font-size: 13px;"
            )
            set_elided_label_text(
                self._root_path_label,
                "No folder loaded",
                PATH_LABEL_MAX_WIDTH,
            )
        else:
            self._path_card.setStyleSheet(path_card_style(loaded=True))
            self._root_path_label.setStyleSheet(
                f"color: {C['text_dim']}; font-size: 13px;"
            )
            set_elided_label_text(
                self._root_path_label,
                str(path),
                PATH_LABEL_MAX_WIDTH,
                Qt.ElideMiddle,
            )

    def _refresh_hidden_button(self) -> None:
        self._hidden_button.setChecked(self._include_hidden)
        self._hidden_button.setStyleSheet(
            toolbar_toggle_style(active=self._include_hidden)
        )

    def _show_workspace_hero(
        self,
        state: str,
        headline: str | None = None,
        detail: str | None = None,
    ) -> None:
        self._splitter.hide()
        self._workspace_hero.show()
        self._dashboard.set_empty()
        if state == "hover":
            self._workspace_hero.set_hover()
        elif state == "scanning":
            self._workspace_hero.set_scanning(
                headline or "Scanning folder",
                detail or "Preparing the Structura workspace.",
            )
        else:
            self._workspace_hero.set_idle()

    def _show_loaded_workspace(self) -> None:
        self._workspace_hero.hide()
        self._splitter.show()

    def _current_selected_stats(self) -> SubtreeStats | None:
        if not self._snapshot:
            return None
        path_str = self._selected_path or str(self._snapshot.root_path)
        return self._snapshot.stats_by_path.get(path_str) or self._snapshot.stats_by_path.get(
            str(self._snapshot.root_path)
        )

    def _refresh_dashboard(self, *, reset_filter: bool = False):
        stats = self._current_selected_stats()
        if not self._snapshot or stats is None:
            self._dashboard.set_empty()
            return
        self._dashboard.set_snapshot(
            self._snapshot,
            stats,
            include_hidden=self._include_hidden,
            media_mode=self._media_mode,
            reset_filter=reset_filter,
        )

    def _open_folder_dialog(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Choose Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if path:
            resolved = sanitize_path(path)
            if resolved and resolved.is_dir():
                self._scan_path(resolved)

    def _toggle_hidden(self):
        self._include_hidden = not self._include_hidden
        self._hidden_action.setChecked(self._include_hidden)
        self._refresh_hidden_button()
        if self._current_root:
            self._scan_path(self._current_root)

    def _set_media_mode(self, media_mode: str):
        if media_mode not in MEDIA_MODES or media_mode == self._media_mode:
            return
        self._media_mode = media_mode
        self._refresh_dashboard()

    def _rescan_current_root(self):
        if self._current_root:
            self._scan_path(self._current_root)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._worker and self._worker.isRunning():
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if self._snapshot is None:
                self._show_workspace_hero("hover")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        if self._snapshot:
            self._refresh_dashboard()
        else:
            self._show_workspace_hero("idle")

    def dropEvent(self, event: QDropEvent):
        if self._worker and self._worker.isRunning():
            event.ignore()
            return
        mime: QMimeData = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        event.acceptProposedAction()
        valid_paths: list[Path] = []
        errors: list[str] = []

        for url in mime.urls():
            raw = url.toLocalFile()
            path = sanitize_path(raw)
            if path is None:
                errors.append(f"Could not resolve path: {sanitize_name(raw)}")
                continue
            if not path.is_dir():
                errors.append(f"Skipped (not a folder): {sanitize_name(path.name)}")
                continue
            valid_paths.append(path)

        if not valid_paths:
            if self._snapshot is None:
                self._show_workspace_hero("idle")
            self._show_status("\n".join(errors) or "No valid folders were dropped.")
            return

        if len(valid_paths) > 1:
            errors.append(
                f"Structura loads one root folder at a time. Using {valid_paths[0].name}."
            )

        if errors:
            self._show_status("\n".join(errors), "warning")
        else:
            self._status.hide()

        self._scan_path(valid_paths[0])

    def _scan_path(self, path: Path):
        if self._worker and self._worker.isRunning():
            self._pending_scan_path = path
            self._worker.cancel()
            return
        self._current_root = path
        self._snapshot = None
        self._selected_path = None
        self._tree_pane.reset()
        self._set_root_label(path)
        self._status.hide()
        self._show_workspace_hero(
            "scanning",
            f"Scanning {sanitize_name(path.name)}",
            "Building the folder tree, file counts, and extension distribution.",
        )

        self._worker = ScanWorker(path, include_hidden=self._include_hidden)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.snapshot_ready.connect(self._on_snapshot_ready)
        self._worker.all_done.connect(self._on_scan_complete)
        self._worker.start()

    def _on_scan_progress(self, folder_name: str, dirs_scanned: int):
        self._show_workspace_hero(
            "scanning",
            f"Scanning {sanitize_name(folder_name)}",
            f"{dirs_scanned} folders indexed so far.",
        )

    def _on_snapshot_ready(self, snapshot: ScanSnapshot):
        self._snapshot = snapshot
        self._selected_path = str(snapshot.root_path)
        self._show_loaded_workspace()
        self._tree_pane.set_snapshot(snapshot)
        self._refresh_dashboard(reset_filter=True)
        if snapshot.warnings:
            preview = "\n".join(f"• {sanitize_name(w)}" for w in snapshot.warnings[:4])
            self._show_status(preview, "warning")
        else:
            self._status.hide()

    def _on_scan_complete(self):
        self._worker = None
        pending_path = self._pending_scan_path
        self._pending_scan_path = None
        if pending_path is not None:
            self._scan_path(pending_path)
            return
        if self._snapshot is None:
            self._show_workspace_hero("idle")
        if self._pending_status is not None:
            message, tone = self._pending_status
            self._pending_status = None
            self._show_status(message, tone)

    def _on_tree_path_selected(self, path_str: str):
        self._selected_path = path_str
        self._refresh_dashboard()

    def _sort_root_folder(self):
        if not self._current_root or self._sort_worker is not None:
            return
        self._dashboard.set_sorting(True)
        self._sort_worker = SortWorker(
            self._current_root,
            include_hidden=self._include_hidden,
            media_mode=self._media_mode,
        )
        self._sort_worker.sort_done.connect(self._on_sort_done)
        self._sort_worker.start()

    def _on_sort_done(self, moved_counts: dict[str, int], errors: list[str]):
        self._sort_worker = None
        self._dashboard.set_sorting(False)
        pending_status: tuple[str, str] | None = None
        if moved_counts and not errors:
            moved_total = sum(moved_counts.values())
            folder_names = ", ".join(
                extension_folder_name(ext) for ext in sorted(moved_counts)
            )
            pending_status = (
                f"Organized {moved_total} file"
                f"{'' if moved_total == 1 else 's'} into {folder_names}.",
                "success",
            )
        elif moved_counts and errors:
            moved_total = sum(moved_counts.values())
            pending_status = (
                f"Organized {moved_total} file"
                f"{'' if moved_total == 1 else 's'}, but some items could not be moved.",
                "warning",
            )
        elif errors:
            pending_status = (
                "Nothing was organized because the root folder could not be updated.",
                "warning",
            )

        if self._current_root:
            self._pending_status = pending_status
            self._scan_path(self._current_root)
        elif pending_status is not None:
            self._show_status(*pending_status)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _set_macos_dock_name(name: str) -> None:
    """Set the macOS dock name via Cocoa NSProcessInfo (no pyobjc needed)."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))  # type: ignore[arg-type]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        NSBundle = objc.objc_getClass(b"NSBundle")
        sel_main = objc.sel_registerName(b"mainBundle")
        bundle = objc.objc_msgSend(NSBundle, sel_main)

        sel_info = objc.sel_registerName(b"infoDictionary")
        info = objc.objc_msgSend(bundle, sel_info)

        # Create NSString for value
        NSString = objc.objc_getClass(b"NSString")
        sel_str = objc.sel_registerName(b"stringWithUTF8String:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        ns_name = objc.objc_msgSend(NSString, sel_str, name.encode())
        ns_key = objc.objc_msgSend(NSString, sel_str, b"CFBundleName")

        sel_set = objc.sel_registerName(b"setObject:forKey:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        objc.objc_msgSend(info, sel_set, ns_name, ns_key)
    except Exception:
        pass


def main():
    _set_macos_dock_name("Structura")
    app = QApplication(sys.argv)
    app.setApplicationName("Structura")
    app.setApplicationDisplayName("Structura")
    app.setStyle("Fusion")
    app_icon = QIcon(str(resolve_asset_path(APP_ICON_RELATIVE_PATH)))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    font = QFont(APP_FONT_FAMILY, 13)
    font.setStyleStrategy(QFont.PreferAntialias)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(C["bg"]))
    pal.setColor(QPalette.WindowText, QColor(C["text"]))
    pal.setColor(QPalette.Base, QColor(C["surface_panel"]))
    pal.setColor(QPalette.AlternateBase, QColor(C["surface_raised"]))
    pal.setColor(QPalette.Button, QColor(C["surface"]))
    pal.setColor(QPalette.ButtonText, QColor(C["text"]))
    pal.setColor(QPalette.Highlight, QColor(C["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor(C["border_shine"]))
    pal.setColor(QPalette.ToolTipBase, QColor(C["surface_alt"]))
    pal.setColor(QPalette.ToolTipText, QColor(C["text"]))
    pal.setColor(QPalette.Mid, QColor(C["border_light"]))
    pal.setColor(QPalette.Dark, QColor(C["border"]))
    pal.setColor(QPalette.Light, QColor(C["border_shine"]))
    app.setPalette(pal)

    window = StructuraWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
