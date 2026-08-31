#!/usr/bin/env python3
"""Shared helpers for WeChat WCDB/SQLCipher-4 raw-key page decrypt (via openssl)."""

from __future__ import annotations

import subprocess
from pathlib import Path

PAGE = 4096
RESERVE = 80  # typical SQLCipher-4: 16-byte IV + 64-byte HMAC-SHA512

XWECHAT_ROOT = (
    Path.home()
    / "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
)


def aes_cbc_decrypt(key: bytes, iv: bytes, ct: bytes) -> bytes:
    proc = subprocess.run(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-K",
            key.hex(),
            "-iv",
            iv.hex(),
            "-nopad",
        ],
        input=ct,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode() or "openssl decrypt failed")
    return proc.stdout


def page1_validates(key: bytes, page1: bytes) -> tuple[int, bytes] | None:
    """Return (reserve, iv) if key decrypts page1 to a plausible SQLite header."""
    salt = page1[:16]
    for r in (80, 64, 48, 32):
        ct = page1[16 : PAGE - r]
        ct = ct[: len(ct) // 16 * 16]
        for iv in (page1[PAGE - r : PAGE - r + 16], salt, b"\x00" * 16):
            try:
                pt = aes_cbc_decrypt(key, iv, ct)
            except RuntimeError:
                continue
            if (
                len(pt) >= 85
                and pt[0] == 0x10
                and pt[1] == 0x00
                and pt[2] == pt[3]
                and pt[2] in (1, 2)
                and pt[4] in (32, 48, 64, 80)
                and pt[84] in (2, 5, 10, 13)
            ):
                return r, iv
    return None


def load_hex_keys(path: Path) -> list[bytes]:
    if not path.is_file():
        return []
    out: list[bytes] = []
    for ln in path.read_text().splitlines():
        h = ln.strip()
        if not h:
            continue
        try:
            k = bytes.fromhex(h)
        except ValueError:
            continue
        if len(k) == 32:
            out.append(k)
    return out


def match_key(enc_db: Path, candidates: list[bytes]) -> tuple[bytes, int]:
    page1 = enc_db.read_bytes()[:PAGE]
    for key in candidates:
        hit = page1_validates(key, page1)
        if hit:
            return key, hit[0]
    raise RuntimeError(f"none of {len(candidates)} keys decrypt {enc_db}")


def decrypt_db(enc_path: Path, key: bytes, out_path: Path, reserve: int = RESERVE) -> None:
    data = enc_path.read_bytes()
    n = len(data) // PAGE
    out = bytearray()
    for i in range(n):
        page = data[i * PAGE : (i + 1) * PAGE]
        iv = page[PAGE - reserve : PAGE - reserve + 16]
        if i == 0:
            pt = aes_cbc_decrypt(key, iv, page[16 : PAGE - reserve])
            plain = (b"SQLite format 3\x00" + pt)[: PAGE - reserve].ljust(PAGE, b"\x00")
            if plain[16:18] != b"\x10\x00":
                raise RuntimeError("page1 decrypt failed — wrong key or reserve?")
        else:
            plain = aes_cbc_decrypt(key, iv, page[: PAGE - reserve])[
                : PAGE - reserve
            ].ljust(PAGE, b"\x00")
        out.extend(plain)
    out_path.write_bytes(out)


def find_emoticon_db(explicit: str | Path | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"db not found: {p}")
        return p
    if not XWECHAT_ROOT.is_dir():
        raise FileNotFoundError(f"WeChat data dir not found: {XWECHAT_ROOT}")
    matches = sorted(XWECHAT_ROOT.glob("*/db_storage/emoticon/emoticon.db"))
    if not matches:
        raise FileNotFoundError("emoticon.db not found under xwechat_files")
    return matches[0]
