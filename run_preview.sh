#!/usr/bin/env zsh
emulate -L zsh
set -euo pipefail

if [[ ! -d ".venv" ]]; then
  print -u2 "Missing .venv in $(pwd). Run: uv sync"
  exit 1
fi

if ! uv run python - <<'PY' >/dev/null 2>&1
import importlib
importlib.import_module("PySide6")
PY
then
  print -u2 "Dependencies missing in .venv; running uv sync..."
  uv sync
fi

exec uv run -- python src/structura/main.py "$@"
