#!/bin/bash
# Helper script to launch the Tkinter app on macOS by double-clicking in Finder.
# It assumes the virtual environment lives at ./.venv relative to this file.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_BIN="$PROJECT_DIR/.venv/bin"
PYTHON_BIN="$VENV_BIN/python"

if [ ! -x "$PYTHON_BIN" ]; then
  osascript -e 'display dialog "Python virtual environment not found. Run setup steps in README first." buttons {"OK"} default button 1 with icon caution'
  exit 1
fi

source "$VENV_BIN/activate"
exec python -m app
