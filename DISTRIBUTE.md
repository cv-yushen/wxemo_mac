# 如何像「插件」一样分发 wxemo（用户无需每次 clone）

目标：用户通过 Homebrew / pipx 安装一次后，系统任意目录都能直接运行：

```bash
wxemo status
wxemo wizard
sudo wxemo hunt
wxemo export
```

敏感步骤（猎钥、读微信库、解密）**仍在用户本机执行**；安装只是把命令行工具放进 PATH。

---

## 架构要点

| 内容 | 位置 |
|------|------|
| 程序代码（cli、keyhunt、脚本） | Homebrew `libexec` 或 Python site-packages |
| 用户数据（密钥、导出图） | **`~/.wxemo/`**（可用 `WXEMO_HOME` 覆盖） |
| 微信 / emoticon.db | 仍在用户机器上的微信沙盒 |

安装后用户**不必**再 clone 仓库。

数据目录示例：

```text
~/.wxemo/
  hunted_keys.txt
  emoticon_key.txt
  exports/
    images/
    manifest.json
    ...
```

---

## 方案 A：Homebrew（macOS 推荐）

### 维护者要做的事

1. 把代码推到 GitHub 公开仓库（或私有 + 授权 tap）。  
2. 打 tag / Release，例如 `v0.1.0`。  
3. 计算源码包 SHA256：

```bash
curl -sL -o /tmp/wxemo.tar.gz \
  https://github.com/YOUR_USER/YOUR_REPO/archive/refs/tags/v0.1.0.tar.gz
shasum -a 256 /tmp/wxemo.tar.gz
```

4. 新建 tap 仓库：`homebrew-wxemo`（Homebrew 约定：`brew tap USER/wxemo` 对应 `USER/homebrew-wxemo`）。  
5. 将本仓库中的 `homebrew/wxemo.rb` 拷到 tap 的 `Formula/wxemo.rb`，替换：
   - `EXAMPLE` → 你的 GitHub 用户/仓库名  
   - `sha256` → 上一步算出的值  
   - `version` / `url` 与 tag 一致  

6. 本地试装：

```bash
brew tap YOUR_USER/wxemo
brew install wxemo
wxemo --help
wxemo status
```

### 终端用户怎么用

```bash
brew tap YOUR_USER/wxemo
brew install wxemo

# 若缺 lldb
xcode-select --install

wxemo status
wxemo wizard
```

升级：

```bash
brew update && brew upgrade wxemo
```

---

## 方案 B：pipx（跨 Python 项目常用）

适合已装 Python 的用户；同样进入 PATH，与 clone 工作副本分离。

### 维护者

1. 完善 `pyproject.toml`（本仓库已提供）。  
2. （可选）发布到 PyPI：`pip publish` / `twine`。  
3. 或仅从 Git 安装。

### 用户

```bash
brew install pipx
pipx ensurepath

# 从 Git 安装（无需长期保留 clone）
pipx install git+https://github.com/YOUR_USER/YOUR_REPO.git

wxemo status
```

从 PyPI（发布后）：

```bash
pipx install wxemo
```

> 注意：pip 安装时需保证 `hunt.sh` / `run_emoticon_export.sh` / `keyhunt.py` 与 `cli.py` 同目录可用。当前以 **Homebrew libexec 整树安装** 最稳；pipx 若遇脚本缺失，优先用 Homebrew。

---

## 方案 C：一键 install 脚本（可选）

在你的域名提供：

```bash
curl -fsSL https://your.domain/install.sh | bash
```

脚本内部实质仍是调用 `brew tap && brew install` 或 `pipx install`，不要把密钥提取放到服务器。

---

## 发布检查清单

- [ ] `wxemo_paths.py`：代码在包内，数据在 `~/.wxemo`  
- [ ] `sudo wxemo hunt` 时密钥仍写入**真实用户**的 `~/.wxemo`（已用 `SUDO_USER` / 环境变量处理）  
- [ ] Release 附带 `USER_GUIDE.md`  
- [ ] Formula `caveats` 提示 Xcode CLT、数据目录  
- [ ] 微信大版本变更时发新版 CLI（钩子可能失效）  
- [ ] README / 官网只教 `brew install`，不再要求日常 clone  

---

## 用户侧完整示例（安装后）

```bash
brew install YOUR_USER/wxemo/wxemo

wxemo status
wxemo prep --open          # 准备可调试微信并登录
sudo wxemo hunt            # 打开表情面板 → Ctrl-C → quit
wxemo export               # 图片在 ~/.wxemo/exports/images/

open ~/.wxemo/exports
```

---

## 和「公有服务器代提取」的区别

| | Homebrew / pipx 安装 | 公有服务器代提取 |
|--|----------------------|------------------|
| 用户是否 clone | 否 | 否 |
| 猎钥发生位置 | 用户本机 | 无法替代本机 |
| 密钥是否出本机 | 默认否（在 `~/.wxemo`） | 若上传则有风险 |
| 推荐 | ✅ | ❌ |

结论：用 Homebrew/pipx 实现「像装插件一样获得 `wxemo` 命令」是正确路径；服务器只适合托管 tap/Release/文档，不适合代跑猎钥。
