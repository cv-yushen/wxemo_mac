# WeChat 4.1.10 (macOS) DB key extraction: memory-scan and `sqlite3_key` both fail — hook `CCCrypt` instead

> **用户手册（逐步操作）**：[USER_GUIDE.md](./USER_GUIDE.md) · **命令入口**：`wxemo` / `./wxemo`  
> **如何 Homebrew 分发（用户免 clone）**：[DISTRIBUTE.md](./DISTRIBUTE.md)

**TL;DR** — On WeChat **4.1.10** for macOS (Apple Silicon, macOS 26), the two publicly documented ways to recover the per-database SQLCipher keys **both stop working**:

1. **Memory scanning for `x'<64hex key><32hex salt>'`** (used by `ydotdog/wechat-export-macos`, `Thearas/wechat-db-decrypt-macos`, WxEcho, etc.) — the cached key string is **no longer present in process memory**.
2. **lldb breakpoint on `sqlite3_key`** (the ac0d3r/imipy approach) — WeChat 4.1.10 **fully strips the SQLCipher symbols**, so `breakpoint set -n sqlite3_key` resolves to **0 locations**.

A working method on 4.1.10: **set an lldb breakpoint on CommonCrypto's `CCCrypt` / `CCCryptorCreate`** (WeChat's WCDB uses CommonCrypto as its AES backend; `_CCCrypt` is a dynamically-imported public symbol that survives stripping) and capture the 32-byte key argument at the moment a page is decrypted. You get one distinct key **per database**.

This is not a novel key-recovery technique in general (runtime hooking is well known) — it's a **version-specific fix**: the existing tooling breaks on 4.1.10 and this is what still works.

---

## Evidence

### 1. The `x'...'` key string is gone from memory on 4.1.10
Exhaustive scan of the WeChat process's readable memory (**7.6 GB, ~565M candidate 32-byte windows**) found **no** value that decrypts `message_0.db` page 1 to a valid SQLite header, testing:
- raw 32-byte windows (8-byte aligned + unaligned near salt),
- 64-char hex-string form,
- salt-anchored windows (±16 KB around every occurrence of the DB's 16-byte salt),
- a **cipher-parameter-agnostic** validator (AES-256-CBC decrypt of page 1 → check `page_size==4096`, `write_ver==read_ver`, reserved-bytes ∈ {32,48,64,80}, page-1 b-tree type ∈ {0x02,0x05,0x0a,0x0d}), sweeping reserve ∈ {48,64,80} and multiple IV positions.

Result: **KEY NOT FOUND**. The salt itself *is* resident (it's the first 16 bytes of the cached page-1 image), but the derived key is never held adjacent to it as plaintext. Conclusion: on 4.1.10 the derived SQLCipher key is **not resident in scannable memory** — it only transits the AES primitive per page-decrypt.

`Thearas/wechat-db-decrypt-macos/find_key_memscan.py` uses `HEX_PATTERN = re.compile(rb"x'([0-9a-fA-F]{64,192})'")` and its README states it was tested on **4.1.2.241** — i.e., the memory-scan era. 4.1.10 is past it.

### 2. SQLCipher symbols are fully stripped on 4.1.10
```
# across every Mach-O in /Applications/WeChat.app:
nm -a <each binary> | grep -iE "sqlite3_key|sqlite3_rekey|sqlcipher|codec_set_cipher"
→ (nothing)
nm -a Contents/Frameworks/wechat.dylib | grep -c sqlite3     → 0
```
So the documented `breakpoint set -n sqlite3_key` cannot resolve. But the main binary imports the AES primitive:
```
nm -u Contents/MacOS/WeChat | grep _CCCrypt   → _CCCrypt
```

### 3. Hooking `CCCrypt` yields the keys
lldb breakpoints (arm64 arg registers), auto-logging any 32-byte key then continuing:
- `CCCrypt(op, alg, options, key, keyLength, iv, …)` → key=`x3`, keyLength=`x4`
- `CCCryptorCreate(op, alg, options, key, keyLength, iv, …)` → key=`x3`, keyLength=`x4`
- `CCCryptorCreateWithMode(op, mode, alg, padding, iv, key, keyLength, …)` → key=`x5`, keyLength=`x6`

Browsing chats / Moments / favorites in the app triggers page decryption; each DB surfaces its own 32-byte key (observed **one key per DB**, consistent with the "24 per-DB keys" reported for 4.1.x). Verified offline: the captured key for `message_0.db` decrypts page 1 to a valid SQLite header with the **standard** SQLCipher-4 params (AES-256-CBC, HMAC-SHA512, reserve=80, page 4096, raw-key mode). So only *key delivery* changed on 4.1.10, not the cipher.

### macOS 26 prerequisite: you can't re-sign `/Applications/WeChat.app` in place
App Management protection means even `sudo codesign --force --deep --sign - /Applications/WeChat.app` returns `Operation not permitted`. Work around it by copying the bundle to a user-owned dir first:
```
ditto /Applications/WeChat.app ~/wechat_copy/WeChat.app
codesign --force --deep --sign - ~/wechat_copy/WeChat.app   # ad-hoc, clears hardened runtime
open -n ~/wechat_copy/WeChat.app                            # same container → same login/data
```
Then `sudo lldb -p <copy pid>` and arm the CCCrypt breakpoints.

---

## CLI（推荐入口）

统一命令行：`./wxemo`（或 `python3 cli.py`）

```bash
./wxemo status          # 查看本机微信/密钥/导出状态
./wxemo wizard          # 交互式全流程（控制台逐步提示）
./wxemo prep --open     # 复制并签名微信，然后启动
sudo ./wxemo hunt       # 猎钥（打开表情面板后 Ctrl-C / quit）
./wxemo verify          # 匹配 emoticon.db 密钥 → emoticon_key.txt
./wxemo export          # 解密 + 下载 CDN 表情图 → emoticon_exports/
./wxemo export --metadata-only
./wxemo --help
```

| Step | Command | Output |
|------|---------|--------|
| 一键向导 | `./wxemo wizard` | 全程交互 → `emoticon_exports/` |
| 分步 | `prep` → `hunt` → `export` | 同上 |
| 旧脚本仍可用 | `./run_emoticon_export.sh` / `hunt.sh` / `emoticon_pipeline.sh` | 同上 |

`emoticon_exports/` 含 `manifest.json`、`cdn_urls.csv`、`images/`、`download_report.json`。  
依赖：Python 3 + openssl（无需 PyCrypto）。仅用于个人账号导出。

---

## Honest scope
- **Not** a first-ever WeChat-on-macOS key extraction; runtime hooking and per-DB keys are already documented for 4.1.2.
- **Is** a working path for **4.1.10**, where the `x'...'` memory-scan and the `sqlite3_key` breakpoint both fail, by hooking the CommonCrypto primitive instead.
- Tested on one machine: WeChat 4.1.10, macOS 26.5.1, Apple Silicon.

Environment: for personal export of one's own account.
