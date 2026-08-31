#!/usr/bin/env python3
"""Post-hunt pipeline for emoticon.db:

  1) Match emoticon.db key from hunted_keys.txt  →  emoticon_key.txt
  2) Decrypt emoticon.db
  3) Export CDN metadata + download images       →  emoticon_exports/

This is the step that runs AFTER `sudo ./hunt.sh` (and browsing the emoji panel
so the emoticon key appears in hunted_keys.txt).

Usage:
  python3 emoticon_pipeline.py
  python3 emoticon_pipeline.py --metadata-only
  ./emoticon_pipeline.sh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from export_emoticons import DEFAULT_KEY_FILE, DEFAULT_KEYS_FILE, DEFAULT_OUT, export_from_db
from wcdb_crypto import find_emoticon_db, load_hex_keys, match_key

ROOT = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", help="encrypted emoticon.db path (auto-detect if omitted)")
    ap.add_argument(
        "--keys-file",
        type=Path,
        default=DEFAULT_KEYS_FILE,
        help="keys captured by hunt.sh / keyhunt.py",
    )
    ap.add_argument(
        "--key-file",
        type=Path,
        default=DEFAULT_KEY_FILE,
        help="where to save the matched emoticon.db key",
    )
    ap.add_argument("--key", help="skip matching; use this 64-hex key directly")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--metadata-only", action="store_true")
    ap.add_argument("--keep-decrypted", action="store_true")
    args = ap.parse_args()

    print("=== emoticon pipeline (after key hunt) ===")
    try:
        db_path = find_emoticon_db(args.db)
    except FileNotFoundError as e:
        sys.exit(str(e))
    print(f"[1/3] db: {db_path}")

    key: bytes | None = None
    reserve = 80

    if args.key:
        key = bytes.fromhex(args.key.strip())
        print("[2/3] using --key")
    elif args.key_file.is_file() and load_hex_keys(args.key_file):
        print(f"[2/3] trying existing {args.key_file}")
        try:
            key, reserve = match_key(db_path, load_hex_keys(args.key_file))
            print(f"      ok reserve={reserve}")
        except RuntimeError:
            print("      stale key file; will match from hunted_keys.txt")
            key = None

    if key is None:
        if not args.keys_file.is_file():
            sys.exit(
                f"missing {args.keys_file}\n"
                "Run first:\n"
                "  sudo ./hunt.sh\n"
                "Then open WeChat emoji panel / favorites so emoticon.db is decrypted,\n"
                "Ctrl-C + quit lldb, then re-run this pipeline."
            )
        cands = load_hex_keys(args.keys_file)
        if not cands:
            sys.exit(f"no keys in {args.keys_file}; re-run hunt.sh and trigger emoji UI")
        print(f"[2/3] matching emoticon key from {args.keys_file} ({len(cands)} keys)...")
        try:
            key, reserve = match_key(db_path, cands)
        except RuntimeError:
            sys.exit(
                "no hunted key matches emoticon.db.\n"
                "Re-run sudo ./hunt.sh and open the emoji / sticker panel in WeChat,\n"
                "then quit lldb and run this pipeline again."
            )
        print(f"      MATCH key={key.hex()}  reserve={reserve}")

    args.key_file.write_text(key.hex() + "\n", encoding="utf-8")
    print(f"      saved {args.key_file}")

    print(f"[3/3] decrypt + export CDN images -> {args.out}")
    summary = export_from_db(
        db_path,
        key,
        reserve,
        args.out,
        metadata_only=args.metadata_only,
        keep_decrypted=args.keep_decrypted,
        workers=args.workers,
        timeout=args.timeout,
    )
    print("=== pipeline done ===")
    print(
        f"items={summary['count']}  "
        f"downloaded_ok={summary['ok']}  "
        f"skipped={summary['skipped']}  "
        f"errors={summary['error']}"
    )
    print(f"output: {args.out}")


if __name__ == "__main__":
    main()
