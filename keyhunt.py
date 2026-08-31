# lldb intercept: log every 32-byte AES key passed to CommonCrypto in WeChat.
# Breakpoints on CCCrypt and CCCryptorCreateWithMode; on arm64 reads the key
# pointer + length from argument registers and appends 32-byte keys (hex).
#
# Output path (first match):
#   1) env WXEMO_HUNTED_KEYS
#   2) $WXEMO_HOME/hunted_keys.txt
#   3) ~/.wxemo/hunted_keys.txt
#
# Usage (attached to the WeChat copy):
#   sudo lldb -p <PID> -o "command script import .../keyhunt.py" -o "keyhunt_start" -o "continue"
# Then open emoji panel in WeChat to trigger DB page decryption. Ctrl-C to stop.

import lldb
import os
from pathlib import Path


def _out_path() -> str:
    env = os.environ.get("WXEMO_HUNTED_KEYS", "").strip()
    if env:
        return env
    home = os.environ.get("WXEMO_HOME", "").strip()
    base = Path(home).expanduser() if home else Path.home() / ".wxemo"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "hunted_keys.txt")


OUT = _out_path()
_seen = set()


def _log_key(frame, key_reg, len_reg):
    try:
        klen = frame.FindRegister(len_reg).GetValueAsUnsigned()
    except Exception:
        return
    if klen != 32:
        return
    kptr = frame.FindRegister(key_reg).GetValueAsUnsigned()
    if not kptr:
        return
    err = lldb.SBError()
    data = frame.GetThread().GetProcess().ReadMemory(kptr, 32, err)
    if not err.Success() or not data:
        return
    h = data.hex()
    if h in _seen:
        return
    _seen.add(h)
    with open(OUT, "a") as f:
        f.write(h + "\n")
    print("KEY32:", h)


def on_cccrypt(frame, bp_loc, extra, internal_dict):
    # CCCrypt(op,alg,options,key,keyLength,iv,...) -> arm64 key=x3 keyLen=x4
    _log_key(frame, "x3", "x4")
    return False  # auto-continue


def on_ccmode(frame, bp_loc, extra, internal_dict):
    # CCCryptorCreateWithMode(..., key, keyLength, ...) -> key=x5 keyLen=x6
    _log_key(frame, "x5", "x6")
    return False


def keyhunt_start(debugger, command, result, internal_dict):
    open(OUT, "w").close()
    t = debugger.GetSelectedTarget()
    for name, cb in (
        ("CCCrypt", "keyhunt.on_cccrypt"),
        ("CCCryptorCreate", "keyhunt.on_cccrypt"),
        ("CCCryptorCreateWithMode", "keyhunt.on_ccmode"),
    ):
        bp = t.BreakpointCreateByName(name)
        bp.SetScriptCallbackFunction(cb)
        print("bp %s -> %d locations" % (name, bp.GetNumLocations()))
    print("keyhunt armed. writing 32-byte keys to", OUT)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(
        "command script add -f keyhunt.keyhunt_start keyhunt_start"
    )
