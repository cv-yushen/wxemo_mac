# 如何像「插件」一样分发 wxemo（用户无需每次 clone）

目标：用户通过 Homebrew 安装一次后，任意目录直接运行：

```bash
wxemo status
wxemo wizard
sudo wxemo hunt
wxemo export
```

敏感步骤（猎钥、读库、解密）**仍在用户本机**；安装只是把 CLI 放进 PATH。

当前仓库：**https://github.com/cv-yushen/wxemo_mac**（private）  
Tap 仓库：**https://github.com/cv-yushen/homebrew-wxemo**（private）

---

## 已落地（v0.1.0）

| 步骤 | 状态 | 地址 |
|------|------|------|
| GitHub Release | ✅ | https://github.com/cv-yushen/wxemo_mac/releases/tag/v0.1.0 |
| Homebrew Tap | ✅ | https://github.com/cv-yushen/homebrew-wxemo |
| 用户数据目录 | ✅ | `~/.wxemo/` |

---

## 用户怎么装（私有仓库）

因为源码与 tap 都是 **private**，用户需要：

1. 被加入仓库协作者（或同属有权限的 org）  
2. 本机已登录 `gh`（或配置 GitHub token）  
3. 安装前导出 Homebrew 用的 API Token：

```bash
# 登录 GitHub CLI（若尚未登录）
gh auth login

# 私有源码下载需要 token
export HOMEBREW_GITHUB_API_TOKEN="$(gh auth token)"

brew tap cv-yushen/wxemo
brew install wxemo

xcode-select --install   # 若无 lldb
wxemo status
wxemo wizard
```

升级：

```bash
export HOMEBREW_GITHUB_API_TOKEN="$(gh auth token)"
brew update && brew upgrade wxemo
```

数据目录：

```text
~/.wxemo/
  hunted_keys.txt
  emoticon_key.txt
  exports/
```

---

## 维护者怎么发新版

在 `wxemo_mac` 仓库：

```bash
# 1. 合并改动并保证工作区干净
git push origin main

# 2. 一键：打 tag + Release + 更新 tap 的 sha256
bash scripts/release.sh 0.1.1
```

脚本会：

1. `git tag v0.1.1` 并 push  
2. 创建 GitHub Release  
3. 下载 archive 计算 `sha256`  
4. 更新 `homebrew/wxemo.rb`  
5. 推送到 `homebrew-wxemo` 的 `Formula/wxemo.rb`  

---

## 架构

```text
维护者
  wxemo_mac @ tag/Release
  homebrew-wxemo / Formula/wxemo.rb   ← url + sha256 指向该 tag
        ↓
用户
  brew tap cv-yushen/wxemo && brew install wxemo
        ↓
本机
  /opt/homebrew/bin/wxemo
  ~/.wxemo/   ← 密钥与导出（不在 Cellar）
```

---

## 可选：PyPI / pipx

适合已装 Python 的环境；私有 Git 安装示例：

```bash
brew install pipx && pipx ensurepath
pipx install "git+https://github.com/cv-yushen/wxemo_mac.git@v0.1.0"
```

私有仓库同样需要 GitHub 认证。公开到 PyPI 需另配账号与 `twine`，当前以 Homebrew 为主。

---

## 私有 vs 公开

| | 私有（当前） | 若改为公开 |
|--|-------------|------------|
| `brew tap/install` | 需要 token + 仓库权限 | 一般用户可直接装 |
| 安全 | 源码不公开 | 需接受代码公开 |

若以后希望任意人 `brew install` 而无需授权，把 `wxemo_mac` 与 `homebrew-wxemo` 设为 **public**，并去掉文档里对 `HOMEBREW_GITHUB_API_TOKEN` 的强制要求即可。

---

## 本地试装（维护者自测）

```bash
export HOMEBREW_GITHUB_API_TOKEN="$(gh auth token)"
brew untap cv-yushen/wxemo 2>/dev/null || true
brew tap cv-yushen/wxemo
brew install wxemo
wxemo --help
wxemo status
```
