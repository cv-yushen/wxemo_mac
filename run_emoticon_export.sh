#!/bin/bash
# 交互式一键导出：微信 emoticon.db 密钥 → 解密 → CDN 表情图
#
# Usage:
#   ./run_emoticon_export.sh
#
# 全程在控制台提示每一步该做什么；需要你手动操作微信时会暂停等待回车。

set -euo pipefail
PKG_ROOT="$(cd "$(dirname "$0")" && pwd)"
PKG_ROOT="${WXEMO_PKG_ROOT:-$PKG_ROOT}"
cd "$PKG_ROOT"
ROOT="$PKG_ROOT"

export WXEMO_HOME="${WXEMO_HOME:-$HOME/.wxemo}"
mkdir -p "$WXEMO_HOME/exports"

WECHAT_COPY="${WECHAT_COPY:-$HOME/wechat_copy/WeChat.app}"
KEYS_FILE="${WXEMO_HUNTED_KEYS:-$WXEMO_HOME/hunted_keys.txt}"
KEY_FILE="$WXEMO_HOME/emoticon_key.txt"
OUT_DIR="$WXEMO_HOME/exports"

# --- UI helpers ---
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
  BOLD="$(tput bold 2>/dev/null || true)"
  DIM="$(tput dim 2>/dev/null || true)"
  RED="$(tput setaf 1 2>/dev/null || true)"
  GREEN="$(tput setaf 2 2>/dev/null || true)"
  YELLOW="$(tput setaf 3 2>/dev/null || true)"
  CYAN="$(tput setaf 6 2>/dev/null || true)"
  RESET="$(tput sgr0 2>/dev/null || true)"
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; RESET=""
fi

banner() {
  echo
  echo "${CYAN}══════════════════════════════════════════════════════════${RESET}"
  echo "${BOLD}$1${RESET}"
  echo "${CYAN}══════════════════════════════════════════════════════════${RESET}"
}

step() {
  echo
  echo "${BOLD}${GREEN}▶ 步骤 $1${RESET}  $2"
  echo "${DIM}──────────────────────────────────────────────────────────${RESET}"
}

info()  { echo "  ${DIM}•${RESET} $*"; }
ok()    { echo "  ${GREEN}✓${RESET} $*"; }
warn()  { echo "  ${YELLOW}!${RESET} $*"; }
err()   { echo "  ${RED}✗${RESET} $*" >&2; }

pause() {
  local msg="${1:-按回车继续}"
  echo
  read -r -p "  ${YELLOW}${msg}${RESET} " _
}

ask_yn() {
  # ask_yn "问题" "Y"|"N"  → sets REPLY to y/n
  local prompt="$1"
  local def="${2:-Y}"
  local hint
  if [[ "$def" == "Y" || "$def" == "y" ]]; then
    hint="[Y/n]"
  else
    hint="[y/N]"
  fi
  while true; do
    read -r -p "  ${prompt} ${hint} " ans || true
    ans="${ans:-$def}"
    case "$ans" in
      Y|y|yes|YES) REPLY=y; return 0 ;;
      N|n|no|NO)   REPLY=n; return 0 ;;
      *) echo "  请输入 y 或 n" ;;
    esac
  done
}

wechat_pid() {
  pgrep -x WeChat 2>/dev/null | head -1 || true
}

count_keys() {
  if [[ -f "$KEYS_FILE" ]]; then
    grep -cE '^[0-9a-fA-F]{64}$' "$KEYS_FILE" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

# --- main ---
banner "微信表情包导出向导（本机个人账号）"

echo
info "工作目录(代码): $ROOT"
info "用户数据目录:   $WXEMO_HOME"
info "产出目录:       $OUT_DIR"
info "说明: 仅用于导出你自己登录账号下的 emoticon.db / CDN 表情资源。"
echo
ask_yn "确认继续？" "Y"
[[ "$REPLY" == "y" ]] || { echo "已取消。"; exit 0; }

# ─── 前置检查 ─────────────────────────────────────────────
step "0/4" "检查本机依赖"

missing=0
for cmd in python3 openssl lldb ditto codesign; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd"
  else
    err "缺少命令: $cmd"
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  err "请先安装缺失依赖（lldb 通常随 Xcode Command Line Tools）。"
  exit 1
fi

# ─── 步骤 1：可调试微信副本 ───────────────────────────────
step "1/4" "准备可调试的微信副本（绕过系统目录签名限制）"

info "正式版路径: /Applications/WeChat.app"
info "副本路径:   $WECHAT_COPY"
echo
info "macOS 通常不能直接改签 /Applications 里的微信，需要先复制到用户目录再 ad-hoc 签名。"

need_prep=1
if [[ -d "$WECHAT_COPY" ]]; then
  ok "已发现微信副本"
  ask_yn "是否重新复制并签名？（一般选 N）" "N"
  [[ "$REPLY" == "y" ]] || need_prep=0
fi

if [[ "$need_prep" -eq 1 ]]; then
  if [[ ! -d /Applications/WeChat.app ]]; then
    err "未找到 /Applications/WeChat.app，请先安装微信。"
    exit 1
  fi
  info "正在退出可能正在运行的微信…"
  killall WeChat 2>/dev/null || true
  sleep 1
  info "复制微信到 $WECHAT_COPY …"
  mkdir -p "$(dirname "$WECHAT_COPY")"
  ditto /Applications/WeChat.app "$WECHAT_COPY"
  info "ad-hoc 签名中…"
  codesign --force --deep --sign - "$WECHAT_COPY"
  ok "副本已准备好"
fi

pid="$(wechat_pid)"
if [[ -z "$pid" ]]; then
  info "正在启动微信副本…"
  open -n "$WECHAT_COPY"
  echo
  warn "请在弹出的微信窗口中完成登录（与正式版共用同一数据容器）。"
  pause "登录完成后，回到本终端按回车"
else
  ok "微信已在运行 (PID=$pid)"
  ask_yn "是否改用副本重新打开微信？" "N"
  if [[ "$REPLY" == "y" ]]; then
    killall WeChat 2>/dev/null || true
    sleep 1
    open -n "$WECHAT_COPY"
    pause "登录完成后，回到本终端按回车"
  fi
fi

pid="$(wechat_pid)"
if [[ -z "$pid" ]]; then
  err "仍未检测到 WeChat 进程。请手动打开副本后再运行本脚本。"
  exit 1
fi
ok "当前 WeChat PID=$pid"

# ─── 步骤 2：猎钥 ─────────────────────────────────────────
step "2/4" "抓取 emoticon.db 密钥（lldb hook CCCrypt）"

skip_hunt=0
if [[ -f "$KEY_FILE" ]] && grep -qE '^[0-9a-fA-F]{64}$' "$KEY_FILE"; then
  ok "已存在 emoticon_key.txt: $(tr -d '\n' < "$KEY_FILE" | head -c 16)…"
  ask_yn "是否跳过猎钥，直接用已有密钥导出？" "Y"
  [[ "$REPLY" == "y" ]] && skip_hunt=1
fi

if [[ "$skip_hunt" -eq 0 ]]; then
  nkeys="$(count_keys)"
  if [[ "$nkeys" -gt 0 ]]; then
    info "当前 hunted_keys.txt 已有 ${nkeys} 把候选密钥"
    ask_yn "是否重新猎钥覆盖/追加？（建议：若之前没开过表情面板，选 Y）" "Y"
    [[ "$REPLY" == "y" ]] || skip_hunt=1
  fi
fi

if [[ "$skip_hunt" -eq 0 ]]; then
  banner "即将开始猎钥 — 请仔细阅读"
  echo
  info "接下来会请求管理员权限并附加 lldb 到微信进程。"
  info "出现 ${BOLD}keyhunt armed${RESET} 后，请立刻切换到微信并操作："
  echo
  echo "      ${BOLD}1) 打开任意聊天窗口${RESET}"
  echo "      ${BOLD}2) 点开表情面板 / 收藏表情 / 发送一条表情${RESET}"
  echo "      ${BOLD}3) 终端应陆续出现 KEY32: …${RESET}"
  echo
  info "看到若干 KEY32 后：按 ${BOLD}Ctrl-C${RESET}，再输入 ${BOLD}quit${RESET} 回车，退出 lldb。"
  echo
  pause "准备好后按回车开始 sudo ./hunt.sh"

  # hunt.sh 使用 exec lldb，退出后回到本脚本
  set +e
  sudo ./hunt.sh
  hunt_rc=$?
  set -e
  echo
  if [[ "$hunt_rc" -ne 0 ]]; then
    warn "hunt.sh 退出码=$hunt_rc（若你是手动 quit，一般可忽略）"
  fi

  nkeys="$(count_keys)"
  if [[ "$nkeys" -eq 0 ]]; then
    err "hunted_keys.txt 为空，没有抓到密钥。"
    err "请确认：微信在跑、表情面板已打开、lldb 曾显示 KEY32。"
    ask_yn "是否立即重试猎钥？" "Y"
    if [[ "$REPLY" == "y" ]]; then
      pause "按回车再次启动 hunt.sh"
      set +e
      sudo ./hunt.sh
      set -e
      nkeys="$(count_keys)"
    fi
  fi
  if [[ "$nkeys" -eq 0 ]]; then
    err "仍无密钥，退出。可稍后重新运行: ./run_emoticon_export.sh"
    exit 1
  fi
  ok "已捕获 ${nkeys} 把候选密钥 → hunted_keys.txt"
else
  ok "跳过猎钥"
fi

# ─── 步骤 3：匹配密钥 ─────────────────────────────────────
step "3/4" "从候选密钥中匹配 emoticon.db"

info "正在自动查找本机 emoticon.db 并验证密钥…"
set +e
match_out="$(python3 - <<'PY' 2>&1
from pathlib import Path
from wcdb_crypto import find_emoticon_db, load_hex_keys, match_key
root = Path(".").resolve()
db = find_emoticon_db()
keys = load_hex_keys(root / "hunted_keys.txt")
key_file = root / "emoticon_key.txt"
# prefer existing key file if it validates
cands = []
if key_file.is_file():
    cands.extend(load_hex_keys(key_file))
cands.extend(keys)
# dedupe preserve order
seen=set(); ordered=[]
for k in cands:
    if k not in seen:
        seen.add(k); ordered.append(k)
key, reserve = match_key(db, ordered)
key_file.write_text(key.hex() + "\n")
print(f"DB={db}")
print(f"KEY={key.hex()}")
print(f"RESERVE={reserve}")
PY
)"
match_rc=$?
set -e

if [[ "$match_rc" -ne 0 ]]; then
  err "未能匹配到 emoticon.db 密钥。"
  echo "$match_out" | sed 's/^/  /'
  echo
  warn "最常见原因：猎钥时没有打开表情面板，emoticon 密钥未进内存。"
  ask_yn "是否回到猎钥步骤重试？（脚本将重新启动 hunt）" "Y"
  if [[ "$REPLY" == "y" ]]; then
    pause "切换到微信打开表情面板的准备好后，按回车开始猎钥"
    set +e
    sudo ./hunt.sh
    set -e
    set +e
    match_out="$(python3 - <<'PY' 2>&1
from pathlib import Path
from wcdb_crypto import find_emoticon_db, load_hex_keys, match_key
root = Path(".").resolve()
db = find_emoticon_db()
keys = load_hex_keys(root / "hunted_keys.txt")
key, reserve = match_key(db, keys)
(root / "emoticon_key.txt").write_text(key.hex() + "\n")
print(f"DB={db}")
print(f"KEY={key.hex()}")
print(f"RESERVE={reserve}")
PY
)"
    match_rc=$?
    set -e
  fi
fi

if [[ "$match_rc" -ne 0 ]]; then
  err "仍然匹配失败，退出。"
  echo "$match_out" | sed 's/^/  /'
  exit 1
fi

db_path="$(echo "$match_out" | sed -n 's/^DB=//p')"
key_hex="$(echo "$match_out" | sed -n 's/^KEY=//p')"
ok "数据库: $db_path"
ok "密钥已写入: $KEY_FILE"
ok "key 前缀: ${key_hex:0:16}…"

# ─── 步骤 4：解密 + CDN 下载 ───────────────────────────────
step "4/4" "解密 emoticon.db 并下载 CDN 表情图"

echo
info "将写入:"
info "  $OUT_DIR/manifest.json"
info "  $OUT_DIR/cdn_urls.csv"
info "  $OUT_DIR/images/<md5>.gif|png|…"
echo
ask_yn "是否同时下载 CDN 图片？（选 N 则只导出元数据）" "Y"
meta_flag=()
if [[ "$REPLY" != "y" ]]; then
  meta_flag=(--metadata-only)
  info "仅导出元数据，跳过图片下载"
fi

pause "按回车开始导出"
python3 emoticon_pipeline.py --key "$key_hex" --out "$OUT_DIR" "${meta_flag[@]+"${meta_flag[@]}"}"

# ─── 完成 ─────────────────────────────────────────────────
banner "完成"

img_count=0
if [[ -d "$OUT_DIR/images" ]]; then
  img_count="$(find "$OUT_DIR/images" -type f | wc -l | tr -d ' ')"
fi
ok "表情图文件数: $img_count"
ok "输出目录:     $OUT_DIR"
ok "密钥文件:     $KEY_FILE"
echo
info "下次若密钥仍有效，可直接运行:"
echo "      ${BOLD}./run_emoticon_export.sh${RESET}  （会询问是否跳过猎钥）"
echo "  或: ${BOLD}./emoticon_pipeline.sh${RESET}"
echo
info "在 Finder 中打开输出目录:"
echo "      open \"$OUT_DIR\""
echo
ask_yn "现在打开输出目录？" "Y"
if [[ "$REPLY" == "y" ]]; then
  open "$OUT_DIR" 2>/dev/null || true
fi

echo
ok "全部流程结束。"
echo
