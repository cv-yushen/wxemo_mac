#!/bin/bash
# Attach lldb to the (ad-hoc re-signed) WeChat copy and arm the CCCrypt intercept.
# Usage: sudo ./hunt.sh
cd "$(dirname "$0")"
PID=$(pgrep -x WeChat | head -1)
[ -z "$PID" ] && { echo "WeChat not running"; exit 1; }
echo ">>> attaching lldb to WeChat PID=$PID; arming CCCrypt breakpoints."
echo ">>> after it says 'armed', switch to WeChat and open chats / Moments / favorites to trigger page decryption."
echo ">>> captured 32-byte keys are appended to hunted_keys.txt. Ctrl-C then 'quit' to stop."
exec lldb -p "$PID" \
  -o "command script import $(pwd)/keyhunt.py" \
  -o "keyhunt_start" \
  -o "continue"
