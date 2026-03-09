#!/bin/zsh
set -euo pipefail
APP_NAME="$1"
TARGET="$2"
if [ -z "$TARGET" ]; then
  exit 0
fi

if [ -d "/Applications/${APP_NAME}.app" ]; then
  open -a "$APP_NAME" "$TARGET"
else
  open "$TARGET"
fi
