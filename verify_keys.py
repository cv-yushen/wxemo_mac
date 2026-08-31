#!/usr/bin/env python3
"""Verify hunted 32-byte keys against an encrypted WeChat DB (page-1 probe).

Uses openssl (no PyCrypto dependency).

Usage:
  python3 verify_keys.py /path/to/emoticon.db [hunted_keys.txt]
  python3 verify_keys.py --db emoticon.db --keys hunted_keys.txt --write-key emoticon_key.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wcdb_crypto import load_hex_keys, match_key


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db_pos", nargs="?", help="encrypted .db path")
    ap.add_argument("keys_pos", nargs="?", help="hex keys file (default: hunted_keys.txt)")
    ap.add_argument("--db", help="encrypted .db path")
    ap.add_argument("--keys", type=Path, help="hex keys file")
    ap.add_argument(
        "--write-key",
        type=Path,
        help="if matched, write the 64-hex key to this file",
    )
    args = ap.parse_args()

    db = Path(args.db or args.db_pos or "")
    if not db.is_file():
        sys.exit("usage: verify_keys.py <encrypted.db> [hunted_keys.txt]")
    keys_path = Path(
        args.keys
        or args.keys_pos
        or Path(__file__).resolve().parent / "hunted_keys.txt"
    )
    cands = load_hex_keys(keys_path)
    if not cands:
        sys.exit(f"no 32-byte hex keys in {keys_path}")

    print(f"testing {len(cands)} hunted keys against {db}...")
    try:
        key, reserve = match_key(db, cands)
    except RuntimeError:
        print("none of the hunted keys decrypt page1")
        sys.exit(1)

    print(f"MATCH! key= {key.hex()}  reserve= {reserve}")
    if args.write_key:
        args.write_key.write_text(key.hex() + "\n", encoding="utf-8")
        print(f"wrote {args.write_key}")


if __name__ == "__main__":
    main()
