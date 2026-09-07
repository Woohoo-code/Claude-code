#!/usr/bin/env bash
# Build a standalone pcba-builder executable for the current OS.
# On Windows this produces dist/pcba-builder.exe; on Linux/macOS it
# produces dist/pcba-builder (no extension). PyInstaller does not
# cross-compile - run this script on each OS you want a binary for.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pip install --quiet -r requirements-build.txt
pyinstaller --onefile --name pcba-builder --noconfirm \
  --distpath dist --workpath build/pyinstaller --specpath build/pyinstaller \
  pcba_builder_entry.py

echo "Built: dist/pcba-builder$( [ "${OS:-}" = "Windows_NT" ] && echo .exe )"
