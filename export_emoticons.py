#!/usr/bin/env python3
"""Decrypt emoticon.db with a raw key, export CDN metadata, download images.

Key resolution order:
  1) --key HEX
  2) --key-file / emoticon_key.txt
  3) match against --keys-file / hunted_keys.txt

Usage:
  python3 export_emoticons.py
  python3 export_emoticons.py --key-file emoticon_key.txt
  python3 export_emoticons.py --metadata-only
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from wcdb_crypto import (
    RESERVE,
    decrypt_db,
    find_emoticon_db,
    load_hex_keys,
    match_key,
)
from wxemo_paths import exports_dir, key_file, keys_file, package_root

ROOT = package_root()
DEFAULT_OUT = exports_dir()
DEFAULT_KEY_FILE = key_file()
DEFAULT_KEYS_FILE = keys_file()
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def resolve_key(
    db: Path,
    key_arg: str | None,
    key_file: Path,
    keys_file: Path,
) -> tuple[bytes, int]:
    if key_arg:
        key = bytes.fromhex(key_arg.strip())
        if len(key) != 32:
            sys.exit("--key must be 32 bytes (64 hex chars)")
        return key, RESERVE
    if key_file.is_file():
        lines = [ln.strip() for ln in key_file.read_text().splitlines() if ln.strip()]
        if lines:
            key = bytes.fromhex(lines[0])
            print(f"using key from {key_file}")
            return key, RESERVE
    cands = load_hex_keys(keys_file)
    if not cands:
        sys.exit(
            f"no key found; pass --key / --key-file, or populate {keys_file} via hunt.sh"
        )
    print(f"matching key against {db} using {keys_file} ({len(cands)} candidates)...")
    key, reserve = match_key(db, cands)
    print(f"matched key: {key.hex()}  (reserve={reserve})")
    return key, reserve


def ext_from_bytes(blob: bytes, content_type: str | None) -> str:
    if blob.startswith(b"GIF8"):
        return ".gif"
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if blob[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return ".webp"
    ct = (content_type or "").split(";")[0].strip().lower()
    return {
        "image/gif": ".gif",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(ct, ".bin")


def download_one(md5: str, url: str, images_dir: Path, timeout: float) -> dict:
    dest_probe = list(images_dir.glob(f"{md5}.*"))
    if dest_probe:
        return {
            "md5": md5,
            "url": url,
            "status": "skipped",
            "path": str(dest_probe[0].relative_to(images_dir.parent)),
        }
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            blob = resp.read()
            ctype = resp.headers.get("Content-Type")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"md5": md5, "url": url, "status": "error", "error": str(e)}
    if not blob or len(blob) < 16:
        return {"md5": md5, "url": url, "status": "error", "error": "empty body"}
    ext = ext_from_bytes(blob, ctype)
    if ext == ".bin":
        return {
            "md5": md5,
            "url": url,
            "status": "error",
            "error": f"not an image (ctype={ctype!r}, head={blob[:8].hex()})",
        }
    path = images_dir / f"{md5}{ext}"
    path.write_bytes(blob)
    return {
        "md5": md5,
        "url": url,
        "status": "ok",
        "path": str(path.relative_to(images_dir.parent)),
        "bytes": len(blob),
        "ext": ext,
    }


def export_from_db(
    db_path: Path,
    key: bytes,
    reserve: int,
    out_dir: Path,
    *,
    metadata_only: bool = False,
    keep_decrypted: bool = False,
    workers: int = 8,
    timeout: float = 20.0,
) -> dict:
    images_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        plain = Path(td) / "emoticon.db"
        print("decrypting emoticon.db ...")
        decrypt_db(db_path, key, plain, reserve=reserve)
        if keep_decrypted:
            kept = out_dir / "emoticon_decrypted.db"
            kept.write_bytes(plain.read_bytes())
            print(f"kept decrypted db: {kept}")

        conn = sqlite3.connect(f"file:{plain}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT type, md5, caption, product_id, aes_key,
                   thumb_url, tp_url, auth_key, cdn_url,
                   extern_url, extern_md5, encrypt_url,
                   designer_id, activity_id
            FROM kNonStoreEmoticonTable
            ORDER BY md5
            """
        ).fetchall()
        fav = [
            r[0]
            for r in conn.execute("SELECT md5 FROM kFavEmoticonOrderTable").fetchall()
        ]
        conn.close()

    records = []
    for r in rows:
        item = {k: r[k] for k in r.keys()}
        item["download_url"] = (
            item.get("cdn_url") or item.get("encrypt_url") or item.get("extern_url")
        )
        records.append(item)

    manifest = {
        "source_db": str(db_path),
        "key_hex": key.hex(),
        "reserve": reserve,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(records),
        "fav_order_count": len(fav),
        "items": records,
        "fav_order": fav,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    csv_path = out_dir / "cdn_urls.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("md5,caption,cdn_url,encrypt_url,extern_url,aes_key,download_url\n")

        def esc(v: object) -> str:
            s = "" if v is None else str(v)
            return '"' + s.replace('"', '""') + '"'

        for it in records:
            f.write(
                ",".join(
                    esc(it.get(k))
                    for k in (
                        "md5",
                        "caption",
                        "cdn_url",
                        "encrypt_url",
                        "extern_url",
                        "aes_key",
                        "download_url",
                    )
                )
                + "\n"
            )

    print(f"wrote {out_dir / 'manifest.json'} ({len(records)} items)")
    print(f"wrote {csv_path}")

    summary = {"count": len(records), "ok": 0, "skipped": 0, "error": 0}
    if metadata_only:
        return summary

    jobs = [
        (it["md5"], it["download_url"])
        for it in records
        if it.get("md5") and it.get("download_url")
    ]
    print(f"downloading {len(jobs)} CDN images -> {images_dir} ...")
    results = []
    ok = err = skip = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = {
            pool.submit(download_one, md5, url, images_dir, timeout): md5
            for md5, url in jobs
        }
        done = 0
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            st = res["status"]
            if st == "ok":
                ok += 1
            elif st == "skipped":
                skip += 1
            else:
                err += 1
            if done % 25 == 0 or done == len(futs):
                print(f"  progress {done}/{len(futs)} ok={ok} skip={skip} err={err}")

    (out_dir / "download_report.json").write_text(
        json.dumps(
            {"ok": ok, "skipped": skip, "error": err, "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"done: ok={ok} skipped={skip} error={err}")
    print(f"report: {out_dir / 'download_report.json'}")
    summary.update({"ok": ok, "skipped": skip, "error": err})
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", help="path to encrypted emoticon.db")
    ap.add_argument("--key", help="32-byte hex key")
    ap.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    ap.add_argument("--keys-file", type=Path, default=DEFAULT_KEYS_FILE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--metadata-only", action="store_true")
    ap.add_argument(
        "--keep-decrypted",
        action="store_true",
        help="also save emoticon_decrypted.db under --out",
    )
    ap.add_argument(
        "--save-key",
        action="store_true",
        help="write matched/used key to --key-file",
    )
    args = ap.parse_args()

    try:
        db_path = find_emoticon_db(args.db)
    except FileNotFoundError as e:
        sys.exit(str(e))

    key, reserve = resolve_key(db_path, args.key, args.key_file, args.keys_file)
    if args.save_key or (not args.key and not args.key_file.is_file()):
        args.key_file.write_text(key.hex() + "\n", encoding="utf-8")
        print(f"wrote {args.key_file}")

    export_from_db(
        db_path,
        key,
        reserve,
        args.out,
        metadata_only=args.metadata_only,
        keep_decrypted=args.keep_decrypted,
        workers=args.workers,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
