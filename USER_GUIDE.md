# 微信 macOS 表情包导出工具 — 用户手册

本文档说明如何使用统一命令行工具 `wxemo`，从本机微信中导出**你自己账号**的收藏/自定义表情包图片。

> **适用范围**：macOS（建议 Apple Silicon）+ 微信 4.1.x  
> **用途**：个人账号数据导出  
> **分发安装**：见 [DISTRIBUTE.md](./DISTRIBUTE.md)（`brew tap cv-yushen/wxemo && brew install wxemo`）  
> **不包含**：向小红书/抖音等平台自动导入表情  

---

## 1. 安装方式（推荐：装到系统，不要每次 clone）

### Homebrew（推荐）

```bash
brew tap cv-yushen/wxemo
brew trust cv-yushen/wxemo    # Homebrew 6+：第三方 tap 需先信任
brew install wxemo
xcode-select --install            # 若无 lldb
wxemo --help
```

### 开发者模式（本仓库内，未 brew 安装时）

```bash
cd /path/to/wechat-4.1.10-macos-key
./wxemo --help          # 仅在仓库目录内可用
# 或
python3 cli.py --help
# 或
pipx install .          # 安装后任意目录用 wxemo
```

安装后可在**任意目录**执行 `wxemo ...`（走 PATH，不要写 `./wxemo`）。

需要管理员权限时推荐：

```bash
sudo "$(which wxemo)" hunt
```

（`sudo` 可能读不到 Homebrew 的 PATH，直接写 `sudo wxemo` 有时会找不到命令。）

**用户数据默认写在：**

```text
~/.wxemo/
  hunted_keys.txt
  emoticon_key.txt
  exports/          # 图片与 manifest
```

可用环境变量 `WXEMO_HOME` 修改数据目录。

---

## 2. 你能得到什么

完整跑通后（默认路径）：

```text
~/.wxemo/exports/
  images/                 # 表情图片（按 md5 命名）
  manifest.json
  cdn_urls.csv
  download_report.json

~/.wxemo/emoticon_key.txt
~/.wxemo/hunted_keys.txt
```

---

## 3. 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | macOS |
| 微信 | 已安装，通常在 `/Applications/WeChat.app` |
| 工具 | `python3`、`openssl`、`lldb`、`ditto`、`codesign` |
| 权限 | 猎钥步骤需要管理员密码（`sudo`） |
| Xcode CLT | 若无 `lldb`：`xcode-select --install` |

进入项目目录：

```bash
cd /path/to/wechat-4.1.10-macos-key
chmod +x wxemo          # 首次使用
wxemo --help
```

也可使用：`python3 cli.py <子命令>`。

---

## 3. 总体流程（先看这张图）

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  prep       │ --> │  hunt       │ --> │  verify     │ --> │  export     │
│ 准备可调试微信 │     │ 抓取数据库密钥 │     │ 匹配表情库密钥 │     │ 解密并下图片 │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                              ↑
                     必须在微信里打开表情面板
                     才能抓到 emoticon.db 的密钥

一键替代：wxemo wizard   （控制台逐步提示，内含上述步骤）
随时检查：wxemo status
```

**推荐两种用法：**

1. **新手**：只跑 `wxemo wizard`，按屏幕提示操作。  
2. **熟手**：按 `prep` → `hunt` → `export` 分步执行（`verify` 可单独用，也可由 `export` 自动完成）。

---

## 4. 快速开始（最短路径）

```bash
cd /path/to/wechat-4.1.10-macos-key

# 1. 看当前状态
wxemo status

# 2. 交互向导（推荐）
wxemo wizard
```

向导会依次让你：

1. 确认用途  
2. 准备/启动可调试微信并登录  
3. 用 `sudo` 猎钥（期间打开表情面板）  
4. 自动匹配密钥  
5. 选择是否下载 CDN 图片并导出  

完成后打开：

```bash
open emoticon_exports
```

---

## 5. 子命令详解

### 5.1 `status` — 查看本机状态

**作用**：检查微信安装、进程、`emoticon.db`、密钥文件、已导出图片数量，并给出下一步建议。

**命令：**

```bash
wxemo status
```

**你会看到类似：**

- `WeChat.app` / 微信副本是否存在  
- 微信是否在运行  
- `emoticon.db` 路径  
- `hunted_keys.txt` 有几把密钥  
- `emoticon_key.txt` 是否已有  
- `emoticon_exports/images` 有多少张图  

**何时用：** 每次操作前、排错时先跑一遍。

---

### 5.2 `wizard` — 交互式全流程向导

**作用**：把准备微信、猎钥、匹配、导出串成对话式流程，适合第一次使用。

**命令：**

```bash
wxemo wizard
```

**你需要做的：**

| 阶段 | 屏幕提示 | 你的操作 |
|------|----------|----------|
| 确认 | 是否继续 | 输入 `Y` |
| 准备微信 | 是否重新复制签名 | 一般选 `N`（已有副本）或 `Y`（首次） |
| 登录 | 请登录后回车 | 在微信窗口登录，回到终端按回车 |
| 猎钥 | 准备好后回车开始 hunt | 回车；输入本机密码（sudo） |
| 猎钥中 | 出现 `keyhunt armed` | **切换到微信 → 打开表情面板/收藏表情** |
| 结束猎钥 | 看到若干 `KEY32:` | `Ctrl-C`，输入 `quit` 回车 |
| 匹配 | 自动匹配 emoticon 密钥 | 失败会问是否重试猎钥 |
| 导出 | 是否下载 CDN 图片 | `Y` 下载 / `N` 只导出元数据 |
| 结束 | 是否打开输出目录 | 可选 `Y` |

**注意：** 若已有有效的 `emoticon_key.txt`，向导会询问是否跳过猎钥。

---

### 5.3 `prep` — 准备可调试微信副本

**作用：** macOS 往往不能直接改签 `/Applications/WeChat.app`。本命令把微信复制到用户目录并做 ad-hoc 签名，以便 `lldb` 附加。

**命令：**

```bash
# 仅复制并签名
wxemo prep

# 复制签名后直接打开
wxemo prep --open

# 微信正在跑时强制继续（会先尝试结束微信）
wxemo prep --force --open
```

**常用选项：**

| 选项 | 说明 | 默认 |
|------|------|------|
| `--source` | 正式版微信路径 | `/Applications/WeChat.app` |
| `--copy` | 副本输出路径 | `~/wechat_copy/WeChat.app` |
| `--open` | 完成后启动副本 | 关 |
| `--force` | 少确认 | 关 |

**操作步骤：**

1. 退出正式微信（或按提示允许脚本 `killall`）。  
2. 执行 `wxemo prep --open`。  
3. 在弹出的**副本**微信中扫码登录（与正式版共用同一数据目录）。  
4. 确认登录成功后再进行猎钥。

**环境变量：** 可用 `WECHAT_COPY=/自定义/路径/WeChat.app` 指定副本位置（`status` 也会读该变量）。

---

### 5.4 `hunt` — 抓取数据库密钥

**作用：** 用 `lldb` 在微信进程里拦截 CommonCrypto（`CCCrypt` 等），把经过的 32 字节 AES 密钥写入 `hunted_keys.txt`。

**命令（必须 sudo）：**

```bash
sudo "$(which wxemo)" hunt
```

**操作步骤（务必按顺序）：**

1. 确保**可调试副本**微信已登录并在运行（`wxemo status` 能看到 PID）。  
2. 执行 `sudo "$(which wxemo)" hunt`，输入密码。  
3. 终端会打印完整操作说明；出现 `keyhunt armed` 后：  
   - 切换到微信  
   - 打开任意聊天  
   - **打开表情面板、浏览收藏表情、最好发送或点选一条表情**  
4. 终端陆续出现 `KEY32: <64位十六进制>`。  
5. 出现多行后，按 `Ctrl-C`，再输入 `quit` 回车，退出 lldb。  
6. 执行 `wxemo export`（或先 `wxemo status` / `wxemo verify`）。

**产物：** 项目目录下的 `hunted_keys.txt`（多库密钥列表，去重追加；每次 `keyhunt_start` 会清空重写，以脚本实现为准）。

**失败常见原因：**

- 没有打开表情相关界面 → 抓不到 `emoticon.db` 对应密钥  
- 附加的是未签名/不可调试的正式版 → 附加失败或无断点  
- 未使用 `sudo` → 工具会提示改用 `sudo "$(which wxemo)" hunt`

---

### 5.5 `verify` — 匹配 emoticon.db 密钥

**作用：** 用候选密钥去试解密 `emoticon.db` 第 1 页，找出正确的那一把，并写入 `emoticon_key.txt`。

**命令：**

```bash
# 自动查找本机 emoticon.db + 使用 hunted_keys.txt
wxemo verify

# 指定库与密钥文件
wxemo verify --db "/path/to/emoticon.db" --keys hunted_keys.txt

# 只打印，不写文件
wxemo verify --no-write-key

# 写入自定义路径
wxemo verify --write-key /tmp/my_emoticon_key.txt
```

**选项：**

| 选项 | 说明 |
|------|------|
| `--db` | 加密库路径；省略则自动在 `~/Library/Containers/com.tencent.xinWeChat/.../xwechat_files/*/db_storage/emoticon/emoticon.db` 查找 |
| `--keys` | 候选密钥文件，默认 `hunted_keys.txt` |
| `--write-key` | 匹配成功后写入路径，默认 `emoticon_key.txt` |
| `--no-write-key` | 不写文件 |

**成功输出示例：**

```text
MATCH! key= 27932513...d30b  reserve= 80
wrote .../emoticon_key.txt
```

**说明：** 日常可直接跑 `wxemo export`，内部会自动做匹配；需要单独确认密钥时用 `verify`。

**多账号注意：** 自动查找时若有多个账号目录，会取排序后的第一个；不确定时请用 `--db` 指定路径。

---

### 5.6 `export` — 解密并下载表情图

**作用：**

1. 解析密钥（`--key` / `emoticon_key.txt` / `hunted_keys.txt` 匹配）  
2. 解密 `emoticon.db`  
3. 读取 `kNonStoreEmoticonTable` 的 CDN 地址  
4. 下载图片到 `emoticon_exports/images/`（已存在同 md5 文件则跳过）  

**命令：**

```bash
# 最常用：自动找库、自动匹配密钥、下载图片
wxemo export

# 已有密钥
wxemo export --key 279325130a03af55d130efb22bdaea464a7e2fb45793a817cac6f6ef575ed30b

# 只用本地密钥文件
wxemo export --key-file emoticon_key.txt

# 只导出元数据，不下载图片
wxemo export --metadata-only

# 额外保留解密后的明文 SQLite
wxemo export --keep-decrypted

# 指定输出目录 / 并发
wxemo export --out ./my_exports --workers 8 --timeout 30
```

**选项：**

| 选项 | 说明 | 默认 |
|------|------|------|
| `--db` | 加密 `emoticon.db` | 自动查找 |
| `--key` | 64 位 hex 密钥 | 无 |
| `--key-file` | 密钥文件 | `emoticon_key.txt` |
| `--keys-file` | 候选密钥列表 | `hunted_keys.txt` |
| `--out` | 输出目录 | `emoticon_exports/` |
| `--workers` | 下载并发数 | 12 |
| `--timeout` | 单张下载超时（秒） | 20 |
| `--metadata-only` | 不下载图片 | 关 |
| `--keep-decrypted` | 保留 `emoticon_decrypted.db` | 关 |

**密钥解析顺序：**

1. `--key`  
2. `--key-file`（存在且能解开库）  
3. 从 `--keys-file` / `hunted_keys.txt` 暴力匹配  

**操作步骤：**

1. 确认已猎钥成功，或已有 `emoticon_key.txt`。  
2. 执行 `wxemo export`。  
3. 等待进度打印至 `done: ok=...`。  
4. 查看 `emoticon_exports/images/` 与 `download_report.json`。  

**再次导出：** 可重复执行；已下载成功的文件会 `skipped`，失败项可重试。

---

## 6. 推荐操作剧本

### 剧本 A：第一次完整导出

```bash
cd /path/to/wechat-4.1.10-macos-key
wxemo status
wxemo prep --open
# → 在副本微信登录

sudo "$(which wxemo)" hunt
# → 打开表情面板，看到 KEY32 后 Ctrl-C / quit

wxemo export
open emoticon_exports/images
```

或：

```bash
wxemo wizard
```

### 剧本 B：密钥还在，只想再下一次 / 补失败项

```bash
wxemo status
wxemo export
```

### 剧本 C：只更新 CDN 元数据，不重新下图

```bash
wxemo export --metadata-only
```

### 剧本 D：换账号 / 指定库

```bash
wxemo verify --db "$HOME/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/<你的账号目录>/db_storage/emoticon/emoticon.db"
wxemo export --db "同上路径"
```

---

## 7. 输出文件说明

| 文件 | 含义 |
|------|------|
| `emoticon_exports/images/<md5>.*` | 表情原图 |
| `emoticon_exports/manifest.json` | 库内字段全量导出 + 收藏顺序 |
| `emoticon_exports/cdn_urls.csv` | 便于 Excel 筛选的 CDN 表 |
| `emoticon_exports/download_report.json` | 每张图 ok / skipped / error |
| `emoticon_key.txt` | 当前匹配的 emoticon 密钥 |
| `hunted_keys.txt` | 猎钥得到的全部候选密钥 |

敏感文件已在 `.gitignore` 中忽略，**请勿提交到公开仓库**。

---

## 8. 路径是怎么找的（不必手写死）

| 内容 | 方式 |
|------|------|
| 微信安装 | 默认 `/Applications/WeChat.app`，可用 `--source` 改 |
| 调试副本 | 默认 `~/wechat_copy/WeChat.app`，可用 `--copy` / `WECHAT_COPY` |
| 用户数据 | `~/Library/Containers/com.tencent.xinWeChat/.../xwechat_files` |
| `emoticon.db` | 在上述目录下 `*/db_storage/emoticon/emoticon.db` 自动扫描 |
| 账号目录名 | 不写死 `wxid_...`，由扫描得到 |

---

## 9. 常见问题

### Q1：`none of the hunted keys decrypt emoticon.db`

猎钥时没有触发表情库解密。解决：重新 `sudo "$(which wxemo)" hunt`，并**明确打开表情面板/收藏表情**。

### Q2：`WeChat not running`

先 `wxemo prep --open` 或手动打开副本微信并登录。

### Q3：`codesign ... Operation not permitted`

不要改签 `/Applications` 里的包，只用 `prep` 生成的用户目录副本。

### Q4：下载部分失败

再执行一次 `wxemo export`；看 `download_report.json` 里的 `error`。CDN 偶发超时属正常。

### Q5：多账号导出错了库

用 `wxemo status` 看当前自动选中的路径，再用 `--db` 指定正确账号下的 `emoticon.db`。

### Q6：是否需要每次都猎钥？

不需要。只要 `emoticon_key.txt` 仍能解开当前库，直接 `wxemo export` 即可。微信大版本更新或换机后再猎钥。

### Q7：和旧脚本是什么关系？

| 旧脚本 | 现 CLI |
|--------|--------|
| `run_emoticon_export.sh` | `wxemo wizard` |
| `hunt.sh` | `sudo "$(which wxemo)" hunt` |
| `emoticon_pipeline.sh` | `wxemo export` |
| `verify_keys.py` | `wxemo verify` |

旧脚本仍可单独使用；日常推荐统一用 `wxemo`。

---

## 10. 清理与卸载

导出成功后，建议收尾（**不会**因退出终端自动删除副本）。

### 只删微信调试副本（保留导出图与密钥）

```bash
wxemo cleanup --copy
```

### 只删用户数据 `~/.wxemo`（含密钥与导出图）

```bash
# 若要保留图片，先备份
cp -R ~/.wxemo/exports ~/Desktop/wxemo_exports_backup
wxemo cleanup --data
```

### 副本 + 数据都清

```bash
wxemo cleanup --all
```

### 完全卸载（清理 + 卸 brew 包）

```bash
wxemo uninstall              # 会确认；可加 -y 跳过确认
wxemo uninstall -y --untap   # 同时 brew untap
```

等价手动步骤：

```bash
wxemo cleanup --all -y
brew uninstall wxemo
brew untap cv-yushen/wxemo   # 可选
```

---

## 11. 命令速查表

```bash
wxemo --help
wxemo status
wxemo wizard
wxemo prep [--source PATH] [--copy PATH] [--open] [--force]
sudo "$(which wxemo)" hunt
wxemo verify [--db PATH] [--keys FILE] [--write-key FILE] [--no-write-key]
wxemo export [--db PATH] [--key HEX] [--key-file FILE] [--keys-file FILE] \
               [--out DIR] [--workers N] [--timeout SEC] \
               [--metadata-only] [--keep-decrypted]
wxemo cleanup --copy|--data|--all [-y]
wxemo uninstall [-y] [--untap]
```

---

## 12. 安全与合规提醒

- 仅导出**你自己登录账号**的数据。  
- 不要分享 `emoticon_key.txt` / `hunted_keys.txt` / 解密后的数据库。  
- 商店表情可能涉及版权，导出后请仅自用，勿公开分发。  
- 本工具通过调试本机已登录客户端捕获密钥，不用于未授权访问他人账号。

---

*文档对应工具入口：`wxemo` / `python3 cli.py`。若命令行为有更新，以 `wxemo --help` 为准。*
