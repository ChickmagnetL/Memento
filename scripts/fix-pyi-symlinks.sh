#!/usr/bin/env bash
# Fix absolute symlinks in PyInstaller --onedir output to be relative.
# PyInstaller creates absolute symlinks in Python.framework that break
# when the app is moved to a different machine.
set -euo pipefail

DIST_DIR="${1:?Usage: $0 <dist-dir>}"
FW_DIR="$DIST_DIR/_internal/Python.framework"

if [ ! -d "$FW_DIR" ]; then
  echo "No Python.framework found in $DIST_DIR, skipping symlink fix"
  exit 0
fi

fix_link() {
  local link="$1"
  local relative_target="$2"

  if [ -L "$link" ]; then
    local target
    target=$(readlink "$link")
    # Only fix if it's an absolute path
    if [[ "$target" == /* ]]; then
      rm "$link"
      ln -s "$relative_target" "$link"
      echo "Fixed: $(basename "$(dirname "$link")")/$(basename "$link") -> $relative_target"
    fi
  fi
}

# Fix Versions/Current -> 3.12 (or whatever version directory is there)
CURRENT_LINK="$FW_DIR/Versions/Current"
if [ -L "$CURRENT_LINK" ]; then
  TARGET=$(readlink "$CURRENT_LINK")
  if [[ "$TARGET" == /* ]]; then
    VERSION_DIR=$(basename "$TARGET")
    rm "$CURRENT_LINK"
    ln -s "$VERSION_DIR" "$CURRENT_LINK"
    echo "Fixed: Versions/Current -> $VERSION_DIR"
  fi
fi

# Fix Python -> Versions/Current/Python
fix_link "$FW_DIR/Python" "Versions/Current/Python"

# Fix Resources -> Versions/Current/Resources
fix_link "$FW_DIR/Resources" "Versions/Current/Resources"

# Fix _internal/Python symlink (points to Python.framework/Versions/Current/Python)
PYTHON_BIN="$DIST_DIR/_internal/Python"
if [ -L "$PYTHON_BIN" ]; then
  TARGET=$(readlink "$PYTHON_BIN")
  if [[ "$TARGET" == /* ]]; then
    rm "$PYTHON_BIN"
    ln -s "Python.framework/Versions/Current/Python" "$PYTHON_BIN"
    echo "Fixed: _internal/Python -> Python.framework/Versions/Current/Python"
  fi
fi

echo "PyInstaller symlinks fixed in $DIST_DIR"