#!/bin/zsh
set -euo pipefail

EDITOR_KEY="${1:-code}"
TARGET="${2:-}"

if [[ -z "$TARGET" ]]; then
  exit 0
fi

if [[ "$EDITOR_KEY" == "cursor" ]]; then
  open -a "Cursor" "$TARGET" >/dev/null 2>&1 || open "$TARGET"
else
  open -a "Visual Studio Code" "$TARGET" >/dev/null 2>&1 || open "$TARGET"
fi
