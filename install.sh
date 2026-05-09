#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="${HOME}/bin/creativity"

mkdir -p "$(dirname "$DEST")"
chmod +x "${SCRIPT_DIR}/creativity.py"
ln -sf "${SCRIPT_DIR}/creativity.py" "$DEST"

echo "installed → $DEST"

if ! echo "$PATH" | tr ':' '\n' | grep -qx "${HOME}/bin"; then
    echo "note: ~/bin is not on your PATH"
    echo "add this to your shell profile:"
    echo "  export PATH=\"\$HOME/bin:\$PATH\""
fi
