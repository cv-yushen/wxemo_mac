#!/usr/bin/env python3
"""统一命令行入口：微信 emoticon.db 猎钥 → 校验 → 解密 → CDN 下载。

用法:
  wxemo <子命令> [选项]
  python3 cli.py <子命令> [选项]

子命令:
  wizard   交互式全流程（推荐新手）
  prep     复制并 ad-hoc 签名微信 App
  hunt     附加 lldb，抓取 CCCrypt 密钥（需 sudo）
  verify   用 hunted_keys 匹配某库密钥
  export   匹配密钥并解密 emoticon.db、下载 CDN 图
  status   查看本机密钥/导出状态
  cleanup  清理微信副本和/或 ~/.wxemo
  uninstall  清理本地数据并卸载 brew 包

示例:
  wxemo wizard
  wxemo prep
  sudo "$(which wxemo)" hunt
  wxemo verify --db ~/.../emoticon.db --write-key emoticon_key.txt
  wxemo export
  wxemo export --metadata-only
  wxemo status
  wxemo cleanup --copy
  wxemo uninstall
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from wxemo_paths import (
    data_dir,
    exports_dir,
    hunt_script,
    key_file,
    keyhunt_script,
    keys_file,
    package_root,
    wizard_script,
)

ROOT = package_root()
DEFAULT_WECHAT_APP = Path("/Applications/WeChat.app")
DEFAULT_WECHAT_COPY = Path.home() / "wechat_copy" / "WeChat.app"
KEYS_FILE = keys_file()
KEY_FILE = key_file()
OUT_DIR = exports_dir()


def _run(cmd: list[str], *, check: bool = True, env: dict | None = None) -> int:
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT), env=env)
    if check and r.returncode != 0:
        sys.exit(r.returncode)
    return r.returncode


def _child_env() -> dict:
    env = os.environ.copy()
    env["WXEMO_HOME"] = str(data_dir())
    env["WXEMO_PKG_ROOT"] = str(ROOT)
    env["WXEMO_HUNTED_KEYS"] = str(keys_file())
    return env


def cmd_wizard(_: argparse.Namespace) -> None:
    script = wizard_script()
    if not script.is_file():
        sys.exit(f"missing {script}")
    os.execve("/bin/bash", ["bash", str(script)], _child_env())


def cmd_prep(args: argparse.Namespace) -> None:
    src = Path(args.source).expanduser()
    dst = Path(args.copy).expanduser()
    if not src.is_dir():
        sys.exit(f"未找到微信安装: {src}")

    pid = subprocess.run(
        ["pgrep", "-x", "WeChat"], capture_output=True, text=True
    ).stdout.strip()
    if pid and not args.force:
        print(f"检测到 WeChat 正在运行 (PID={pid.splitlines()[0]})。")
        print("将先退出再复制。可用 --force 跳过确认。")
        ans = input("继续并 killall WeChat? [Y/n] ").strip() or "Y"
        if ans[0] not in "Yy":
            sys.exit("已取消")
        subprocess.run(["killall", "WeChat"], check=False)
        import time

        time.sleep(1)

    print(f"复制 {src} → {dst} ...")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    _run(["ditto", str(src), str(dst)])
    print("ad-hoc 签名 ...")
    _run(["codesign", "--force", "--deep", "--sign", "-", str(dst)])
    print(f"完成: {dst}")
    if args.open:
        _run(["open", "-n", str(dst)], check=False)
        print('已启动微信副本，请登录后执行: sudo "$(which wxemo)" hunt')


def cmd_hunt(_: argparse.Namespace) -> None:
    script = hunt_script()
    if not script.is_file():
        sys.exit(f"missing {script}")
    if not keyhunt_script().is_file():
        sys.exit(f"missing {keyhunt_script()}")
    if os.geteuid() != 0:
        print("")
        print("hunt 需要管理员权限以附加微信进程。")
        print("")
        print("请执行：")
        print('  sudo "$(which wxemo)" hunt')
        print("")
        print("执行前请确认：")
        print("  • 可调试微信副本已启动并登录（可用: wxemo prep --open）")
        print("  • wxemo status 能看到 WeChat process")
        print("")
        print(f"用户数据目录: {data_dir()}")
        sys.exit(1)
    # sudo 下仍写入调用者的 ~/.wxemo（通过环境变量传递）
    env = _child_env()
    if os.environ.get("SUDO_USER"):
        # 若 sudo 未保留 WXEMO_HOME，按真实用户主目录重算
        import pwd

        home = Path(pwd.getpwnam(os.environ["SUDO_USER"]).pw_dir)
        data = Path(os.environ.get("WXEMO_HOME") or (home / ".wxemo"))
        data.mkdir(parents=True, exist_ok=True)
        env["WXEMO_HOME"] = str(data)
        env["WXEMO_HUNTED_KEYS"] = str(data / "hunted_keys.txt")
    os.execve("/bin/bash", ["bash", str(script)], env)


def cmd_verify(args: argparse.Namespace) -> None:
    from wcdb_crypto import find_emoticon_db, load_hex_keys, match_key

    try:
        db = (
            Path(args.db).expanduser().resolve()
            if args.db
            else find_emoticon_db()
        )
    except FileNotFoundError as e:
        sys.exit(str(e))
    if not db.is_file():
        sys.exit(f"db not found: {db}")

    keys_path = Path(args.keys).expanduser() if args.keys else KEYS_FILE
    cands = load_hex_keys(keys_path)
    if not cands:
        sys.exit('no keys in {keys_path}; run: sudo "$(which wxemo)" hunt'.format(keys_path=keys_path))

    print(f"testing {len(cands)} keys against {db}...")
    try:
        key, reserve = match_key(db, cands)
    except RuntimeError:
        print("none of the hunted keys decrypt page1")
        sys.exit(1)

    print(f"MATCH! key= {key.hex()}  reserve= {reserve}")
    if not args.no_write_key and args.write_key:
        write_to = Path(args.write_key).expanduser()
        write_to.write_text(key.hex() + "\n", encoding="utf-8")
        print(f"wrote {write_to}")


def cmd_export(args: argparse.Namespace) -> None:
    # Reuse pipeline module
    argv = ["emoticon_pipeline.py"]
    if args.db:
        argv += ["--db", args.db]
    if args.key:
        argv += ["--key", args.key]
    if args.key_file:
        argv += ["--key-file", str(args.key_file)]
    if args.keys_file:
        argv += ["--keys-file", str(args.keys_file)]
    if args.out:
        argv += ["--out", str(args.out)]
    if args.workers:
        argv += ["--workers", str(args.workers)]
    if args.timeout:
        argv += ["--timeout", str(args.timeout)]
    if args.metadata_only:
        argv.append("--metadata-only")
    if args.keep_decrypted:
        argv.append("--keep-decrypted")

    import emoticon_pipeline

    sys.argv = argv
    emoticon_pipeline.main()


def cmd_status(_: argparse.Namespace) -> None:
    from wcdb_crypto import find_emoticon_db, load_hex_keys

    # Refresh paths in case WXEMO_HOME changed
    global KEYS_FILE, KEY_FILE, OUT_DIR
    KEYS_FILE = keys_file()
    KEY_FILE = key_file()
    OUT_DIR = exports_dir()

    print("=== wxemo status ===")
    print(f"package:  {ROOT}")
    print(f"data dir: {data_dir()}  (override: WXEMO_HOME)")

    app = DEFAULT_WECHAT_APP
    copy = Path(os.environ.get("WECHAT_COPY", DEFAULT_WECHAT_COPY))
    print(f"WeChat.app:     {'OK' if app.is_dir() else 'MISSING'}  {app}")
    print(f"WeChat copy:    {'OK' if copy.is_dir() else 'MISSING'}  {copy}")

    pid = subprocess.run(
        ["pgrep", "-x", "WeChat"], capture_output=True, text=True
    ).stdout.strip()
    print(f"WeChat process: {pid.splitlines()[0] if pid else '(not running)'}")

    try:
        db = find_emoticon_db()
        print(f"emoticon.db:    OK  {db}  ({db.stat().st_size} bytes)")
    except FileNotFoundError as e:
        print(f"emoticon.db:    MISSING  ({e})")

    n_hunt = len(load_hex_keys(KEYS_FILE))
    print(f"hunted_keys:    {n_hunt} key(s)  {KEYS_FILE}")
    if KEY_FILE.is_file():
        k = KEY_FILE.read_text().strip().splitlines()[0][:16]
        print(f"emoticon_key:   OK  {k}…  {KEY_FILE}")
    else:
        print(f"emoticon_key:   MISSING  {KEY_FILE}")

    img_dir = OUT_DIR / "images"
    if img_dir.is_dir():
        n = sum(1 for _ in img_dir.iterdir() if _.is_file())
        print(f"exports:        {n} image(s)  {OUT_DIR}")
    else:
        print(f"exports:        (empty)  {OUT_DIR}")

    print()
    print("下一步提示:")
    if n_hunt == 0 and not KEY_FILE.is_file():
        print("  1) wxemo prep --open")
        print("  2) sudo \"$(which wxemo)\" hunt   # 打开表情面板后 Ctrl-C / quit")
        print("  3) wxemo export")
    elif not (OUT_DIR / "images").is_dir() or not any((OUT_DIR / "images").glob("*")):
        print("  wxemo export")
    else:
        print("  已有导出；可再跑 wxemo export（已存在图片会 skip）")
        print("  或 wxemo wizard 走交互流程")
        print("  导出完成后可清理: wxemo cleanup --copy")
        print("  完全卸载: wxemo uninstall")


def _confirm(prompt: str, *, yes: bool) -> bool:
    if yes:
        return True
    ans = input(f"  {prompt} [y/N] ").strip().lower()
    return ans in ("y", "yes")


def _remove_path(path: Path, label: str) -> bool:
    if not path.exists():
        print(f"  · {label}: 不存在，跳过  ({path})")
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"  ✓ 已删除 {label}: {path}")
    return True


def _do_cleanup(*, do_copy: bool, do_data: bool) -> None:
    copy_path = Path(os.environ.get("WECHAT_COPY", DEFAULT_WECHAT_COPY)).expanduser()
    data_path = data_dir(ensure=False)

    if do_copy:
        _remove_path(copy_path, "微信调试副本")
        parent = copy_path.parent
        if parent.name == "wechat_copy" and parent.is_dir() and not any(parent.iterdir()):
            _remove_path(parent, "空的 wechat_copy 目录")
        if subprocess.run(["pgrep", "-x", "WeChat"], capture_output=True).returncode == 0:
            print("  ! 仍有 WeChat 进程在运行。若它是调试副本，可手动退出：killall WeChat")

    if do_data:
        _remove_path(data_path, "wxemo 用户数据 (~/.wxemo)")


def cmd_cleanup(args: argparse.Namespace) -> None:
    """Remove WeChat debug copy and/or ~/.wxemo data."""
    do_copy = args.copy or args.all
    do_data = args.data or args.all
    if not do_copy and not do_data:
        print("请指定清理范围，例如：")
        print("  wxemo cleanup --copy     # 只删微信调试副本")
        print("  wxemo cleanup --data     # 只删 ~/.wxemo（含密钥与导出图）")
        print("  wxemo cleanup --all      # 两者都删")
        print("  wxemo uninstall          # 清理后提示 brew uninstall")
        sys.exit(2)

    copy_path = Path(os.environ.get("WECHAT_COPY", DEFAULT_WECHAT_COPY)).expanduser()
    data_path = data_dir(ensure=False)

    print("=== wxemo cleanup ===")
    if do_copy:
        print(f"微信副本: {copy_path}  ({'存在' if copy_path.exists() else '不存在'})")
    if do_data:
        print(f"用户数据: {data_path}  ({'存在' if data_path.exists() else '不存在'})")
    print("")
    if do_data:
        print("注意: --data 会删除密钥和已导出的表情图片。")
    if not _confirm("确认删除以上内容？", yes=args.yes):
        print("已取消。")
        sys.exit(0)

    _do_cleanup(do_copy=do_copy, do_data=do_data)

    print("")
    print("清理完成。CLI 本身仍在；若要卸载命令行工具：")
    print("  brew uninstall wxemo")
    print("  brew untap cv-yushen/wxemo    # 可选")


def cmd_uninstall(args: argparse.Namespace) -> None:
    """Clean local artifacts and print / run brew uninstall."""
    print("=== wxemo uninstall ===")
    print("将依次：")
    print("  1) 删除微信调试副本（若存在）")
    print("  2) 删除用户数据 ~/.wxemo（密钥 + 导出图）")
    print("  3) 卸载 Homebrew 包 wxemo（若已 brew 安装）")
    print("")
    print("注意: 第 2 步会删除已导出的表情图片。若要保留，请先备份：")
    print(f"  cp -R {data_dir(ensure=False)}/exports ~/Desktop/wxemo_exports_backup")
    print("")
    if not _confirm("确认完全卸载？", yes=args.yes):
        print("已取消。")
        sys.exit(0)

    _do_cleanup(do_copy=True, do_data=True)

    print("")
    brew = shutil.which("brew")
    wxemo_path = shutil.which("wxemo")
    if brew and wxemo_path and "Cellar/wxemo" in os.path.realpath(wxemo_path):
        print("正在执行: brew uninstall wxemo")
        r = subprocess.run([brew, "uninstall", "wxemo"])
        if r.returncode == 0:
            print("  ✓ brew uninstall wxemo 完成")
        else:
            print("  ! brew uninstall 失败，请手动执行: brew uninstall wxemo")
        if args.untap:
            print("正在执行: brew untap cv-yushen/wxemo")
            subprocess.run([brew, "untap", "cv-yushen/wxemo"], check=False)
    else:
        print("未检测到 Homebrew 安装的 wxemo。若从源码使用，删除仓库即可。")
        print("若曾 brew 安装，请手动：")
        print("  brew uninstall wxemo")
        print("  brew untap cv-yushen/wxemo")

    print("")
    print("卸载流程结束。")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wxemo",
        description="微信 macOS 表情包导出 CLI（猎钥 → 解密 → CDN 下载）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("wizard", help="交互式全流程向导")
    p.set_defaults(func=cmd_wizard)

    p = sub.add_parser("prep", help="复制并签名微信副本")
    p.add_argument("--source", default=str(DEFAULT_WECHAT_APP))
    p.add_argument("--copy", default=str(DEFAULT_WECHAT_COPY))
    p.add_argument("--open", action="store_true", help="完成后启动副本")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_prep)

    p = sub.add_parser("hunt", help="lldb 抓取密钥（需 sudo）")
    p.set_defaults(func=cmd_hunt)

    p = sub.add_parser("verify", help="匹配 emoticon.db 密钥")
    p.add_argument("--db", help="加密库路径（默认自动查找）")
    p.add_argument("--keys", help="候选密钥文件", default=str(KEYS_FILE))
    p.add_argument(
        "--write-key",
        default=str(KEY_FILE),
        help=f"写入匹配密钥的路径（默认 {KEY_FILE.name}；传空字符串可跳过写入）",
    )
    p.add_argument(
        "--no-write-key",
        action="store_true",
        help="只打印 MATCH，不写文件",
    )
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("export", help="解密并下载 CDN 表情图")
    p.add_argument("--db")
    p.add_argument("--key")
    p.add_argument("--key-file", type=Path, default=KEY_FILE)
    p.add_argument("--keys-file", type=Path, default=KEYS_FILE)
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--workers", type=int, default=12)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--metadata-only", action="store_true")
    p.add_argument("--keep-decrypted", action="store_true")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("status", help="查看本机状态")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("cleanup", help="清理微信副本和/或 ~/.wxemo 数据")
    p.add_argument("--copy", action="store_true", help="删除微信调试副本")
    p.add_argument("--data", action="store_true", help="删除 ~/.wxemo（密钥与导出）")
    p.add_argument("--all", action="store_true", help="删除副本 + 用户数据")
    p.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("uninstall", help="清理本地数据并卸载 brew 包")
    p.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    p.add_argument("--untap", action="store_true", help="同时 brew untap cv-yushen/wxemo")
    p.set_defaults(func=cmd_uninstall)

    return ap


def main(argv: list[str] | None = None) -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    data_dir()
    ap = build_parser()
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
