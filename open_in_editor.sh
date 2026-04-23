#!/bin/zsh
set -euo pipefail

EDITOR_KEY="${1:-code}"
TARGET="${2:-}"

if [[ -z "$TARGET" ]]; then
  exit 0
fi

if [[ "$EDITOR_KEY" == "cursor" ]]; then
  APP_CANDIDATES=("Cursor" "Cursor - Insiders")
else
  APP_CANDIDATES=("Visual Studio Code" "Visual Studio Code - Insiders")
fi

for APP_NAME in "${APP_CANDIDATES[@]}"; do
  if open -a "$APP_NAME" "$TARGET" >/dev/null 2>&1; then
    exit 0
  fi
done

echo "Could not open '$TARGET' in ${APP_CANDIDATES[*]}." >&2
exit 1
