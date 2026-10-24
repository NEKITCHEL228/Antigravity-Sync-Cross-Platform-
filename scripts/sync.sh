#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find python3 or python
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif [ -x "$HOME/Library/Application Support/Antigravity/bin/agy-node" ]; then
  # Fallback if needed
  PYTHON_BIN="python3"
else
  echo "[Antigravity Sync Error] Python 3 не найден в PATH."
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/sync_manager.py" "$@"
