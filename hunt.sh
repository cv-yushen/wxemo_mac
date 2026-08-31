#!/bin/bash
# Attach lldb to WeChat and arm CCCrypt intercept.
# Keys go to ${WXEMO_HOME:-$HOME/.wxemo}/hunted_keys.txt
#
# Usage: sudo "$(which wxemo)" hunt
set -euo pipefail

PKG_ROOT="$(cd "$(dirname "$0")" && pwd)"
PKG_ROOT="${WXEMO_PKG_ROOT:-$PKG_ROOT}"
export WXEMO_HOME="${WXEMO_HOME:-$HOME/.wxemo}"
mkdir -p "$WXEMO_HOME"
export WXEMO_HUNTED_KEYS="${WXEMO_HUNTED_KEYS:-$WXEMO_HOME/hunted_keys.txt}"

KEYHUNT="$PKG_ROOT/keyhunt.py"
if [[ ! -f "$KEYHUNT" ]]; then
  echo "错误: 找不到 keyhunt.py: $KEYHUNT" >&2
  exit 1
fi

PID=$(pgrep -x WeChat | head -1 || true)
if [[ -z "$PID" ]]; then
  echo "错误: 未检测到正在运行的 WeChat 进程。" >&2
  echo "" >&2
  echo "请先：" >&2
  echo "  1) wxemo prep --open          # 如尚无调试副本" >&2
  echo "  2) 在副本微信中完成登录" >&2
  echo "  3) 再执行: sudo \"\$(which wxemo)\" hunt" >&2
  exit 1
fi

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  wxemo hunt — 抓取 emoticon.db 密钥"
echo "══════════════════════════════════════════════════════════"
echo ""
echo "  WeChat PID : $PID"
echo "  密钥写入   : $WXEMO_HUNTED_KEYS"
echo "  脚本       : $KEYHUNT"
echo ""
echo "【请按下面步骤操作】"
echo ""
echo "  ① 保持本终端在前台，等待出现："
echo "       keyhunt armed"
echo "       bp CCCrypt -> … locations"
echo ""
echo "  ② 切换到微信窗口，务必操作表情相关界面（否则抓不到 emoticon 密钥）："
echo "       • 打开任意聊天"
echo "       • 点开表情面板 / 收藏表情"
echo "       • 最好发送或点选一条表情"
echo ""
echo "  ③ 回到本终端，应陆续出现："
echo "       KEY32: <64位十六进制>"
echo "     看到若干行 KEY32 即可（通常几行到十几行）。"
echo ""
echo "  ④ 结束猎钥："
echo "       按 Ctrl-C"
echo "       再输入 quit 后回车（退出 lldb）"
echo ""
echo "  ⑤ 下一步（无需 sudo）："
echo "       wxemo export"
echo "     或先检查："
echo "       wxemo status"
echo "       wxemo verify"
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  正在附加 lldb …（若首次可能稍慢）"
echo "══════════════════════════════════════════════════════════"
echo ""

exec lldb -p "$PID" \
  -o "command script import $KEYHUNT" \
  -o "keyhunt_start" \
  -o "continue"
