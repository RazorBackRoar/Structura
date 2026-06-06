#!/usr/bin/env python3
"""Source entrypoint for the Structura desktop application."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Structura import main as _app_main  # ty: ignore[unresolved-import]  # noqa: E402


def main() -> None:
    _app_main()


if __name__ == "__main__":
    main()
