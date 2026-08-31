#!/usr/bin/env python3
"""Install-aware paths: package code vs per-user data (~/.wxemo)."""

from __future__ import annotations

import os
from pathlib import Path


def package_root() -> Path:
    """Directory containing this project's Python modules and helper scripts."""
    return Path(__file__).resolve().parent


def data_dir(*, ensure: bool = True) -> Path:
    """
    Writable per-user data (keys, exports).

    Override with env WXEMO_HOME. Must NOT live under Homebrew Cellar /
    site-packages (those are read-only after install).
    """
    raw = os.environ.get("WXEMO_HOME", "").strip()
    base = Path(raw).expanduser() if raw else Path.home() / ".wxemo"
    if ensure:
        base.mkdir(parents=True, exist_ok=True)
        (base / "exports").mkdir(parents=True, exist_ok=True)
    return base


def keys_file() -> Path:
    return data_dir() / "hunted_keys.txt"


def key_file() -> Path:
    return data_dir() / "emoticon_key.txt"


def exports_dir() -> Path:
    return data_dir() / "exports"


def keyhunt_script() -> Path:
    return package_root() / "keyhunt.py"


def wizard_script() -> Path:
    return package_root() / "run_emoticon_export.sh"


def hunt_script() -> Path:
    return package_root() / "hunt.sh"
