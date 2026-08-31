#!/bin/bash
# 在本机已执行 `gh auth login` 之后运行本脚本：
#   bash scripts/create_and_push_wxemo_mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."

REPO_NAME="wxemo_mac"
OWNER="$(gh api user -q .login)"
echo "GitHub user: $OWNER"
echo "Creating private repo: $OWNER/$REPO_NAME"

if gh repo view "$OWNER/$REPO_NAME" >/dev/null 2>&1; then
  echo "Repo already exists: https://github.com/$OWNER/$REPO_NAME"
else
  gh repo create "$REPO_NAME" --private --description "wxemo: WeChat macOS emoticon export CLI"
fi

# Keep previous origin as wechat-key if present
if git remote get-url origin >/dev/null 2>&1; then
  OLD="$(git remote get-url origin)"
  if [[ "$OLD" != *"${REPO_NAME}"* ]]; then
    if git remote get-url wechat-key >/dev/null 2>&1; then
      echo "remote wechat-key already set"
    else
      git remote rename origin wechat-key
      echo "renamed origin -> wechat-key ($OLD)"
    fi
  fi
fi

URL="https://github.com/${OWNER}/${REPO_NAME}.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$URL"
else
  git remote add origin "$URL"
fi
echo "origin = $URL"

git push -u origin main
echo "Done: https://github.com/${OWNER}/${REPO_NAME}"
