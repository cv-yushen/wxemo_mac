#!/bin/bash
# Attach lldb to WeChat and arm CCCrypt intercept.
# Keys go to ${WXEMO_HOME:-$HOME/.wxemo}/hunted_keys.txt
#
# Usage: sudo ./hunt.sh
#    or: sudo wxemo hunt
set -euo pipefail

PKG_ROOT="$(cd "$(dirname "$0")" && pwd)"
# When installed, caller may set WXEMO_PKG_ROOT
PKG_ROOT="${WXEMO_PKG_ROOT:-$PKG_ROOT}"
export WXEMO_HOME="${WXEMO_HOME:-$HOME/.wxemo}"
mkdir -p "$WXEMO_HOME"
export WXEMO_HUNTED_KEYS="${WXEMO_HUNTED_KEYS:-$WXEMO_HOME/hunted_keys.txt}"

KEYHUNT="$PKG_ROOT/keyhunt.py"
if [[ ! -f "$KEYHUNT" ]]; then
  echo "keyhunt.py not found at $KEYHUNT" >&2
  exit 1
fi

PID=$(pgrep -x WeChat | head -1 || true)
[ -z "$PID" ] && { echo "WeChat not running"; exit 1; }

echo ">>> attaching lldb to WeChat PID=$PID"
echo ">>> keys -> $WXEMO_HUNTED_KEYS"
echo ">>> after 'armed', open WeChat emoji panel / favorite stickers"
echo ">>> Ctrl-C then type 'quit' to stop; next: wxemo export"
exec lldb -p "$PID" \
  -o "command script import $KEYHUNT" \
  -o "keyhunt_start" \
  -o "continue"
