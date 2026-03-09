#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT_NAME="alfred-vscode-cursor-recents.alfredworkflow"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cp "$ROOT/info.plist" "$ROOT/recent_projects.py" "$ROOT/open_in_editor.sh" "$TMP_DIR/"
if [ -f "$ROOT/icon.png" ]; then
  cp "$ROOT/icon.png" "$TMP_DIR/"
fi

(cd "$TMP_DIR" && zip -qr "$ROOT/$OUT_NAME" .)
echo "$ROOT/$OUT_NAME"
