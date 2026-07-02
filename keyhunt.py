# lldb intercept: log every 32-byte AES key passed to CommonCrypto in WeChat.
# Breakpoints on CCCrypt and CCCryptorCreateWithMode; on arm64 reads the key
# pointer + length from argument registers and appends 32-byte keys (hex) to
# ~/code/_ref/wechat-export-macos/hunted_keys.txt (deduplicated).
#
# Usage (attached to the WeChat copy):
#   sudo lldb -p <PID> -o "command script import .../keyhunt.py" -o "keyhunt_start" -o "continue"
# Then click a chat / scroll in WeChat to trigger DB page decryption. Ctrl-C to stop.

import lldb, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunted_keys.txt")
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
    # CCCryptorCreateWithMode(op,mode,alg,padding,iv,key,keyLength,...) -> key=x5 keyLen=x6
    _log_key(frame, "x5", "x6")
    return False

def keyhunt_start(debugger, command, result, internal_dict):
    open(OUT, "w").close()
    t = debugger.GetSelectedTarget()
    # CCCrypt/CCCryptorCreate: key=x3,len=x4 ; CCCryptorCreateWithMode: key=x5,len=x6
    for name, cb in (("CCCrypt", "keyhunt.on_cccrypt"),
                     ("CCCryptorCreate", "keyhunt.on_cccrypt"),
                     ("CCCryptorCreateWithMode", "keyhunt.on_ccmode")):
        bp = t.BreakpointCreateByName(name)
        bp.SetScriptCallbackFunction(cb)
        print("bp %s -> %d locations" % (name, bp.GetNumLocations()))
    print("keyhunt armed. writing 32-byte keys to", OUT)

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f keyhunt.keyhunt_start keyhunt_start")
