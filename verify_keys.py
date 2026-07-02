#!/usr/bin/env python3
"""Verify hunted keys against a WeChat DB page 1 (param-agnostic, HMAC-independent).
Usage: python3 verify_keys.py /path/to/message_0.db [hunted_keys.txt]"""
import sys
from Crypto.Cipher import AES
if len(sys.argv) < 2:
    sys.exit("usage: verify_keys.py <encrypted.db> [hunted_keys.txt]")
DB = sys.argv[1]
KEYS = sys.argv[2] if len(sys.argv) > 2 else "hunted_keys.txt"
p1 = open(DB, "rb").read(4096); salt = p1[:16]
def ok(key):
    for r in (80, 64, 48, 32):
        ct = p1[16:4096-r]; ct = ct[:len(ct)//16*16]
        for iv in (p1[4096-r:4096-r+16], salt, b"\0"*16):
            pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
            if pt[0]==0x10 and pt[1]==0x00 and pt[2]==pt[3] and pt[2] in (1,2) \
               and pt[4] in (32,48,64,80) and pt[84] in (2,5,10,13):
                return (r, iv.hex()[:8])
    return None
lines = [l.strip() for l in open(KEYS) if l.strip()]
print(f"testing {len(lines)} hunted keys against {DB}...")
for h in lines:
    try: k = bytes.fromhex(h)
    except ValueError: continue
    if len(k) != 32: continue
    r = ok(k)
    if r: print("MATCH! key=", h, " reserve=", r[0], " iv=", r[1]); break
else:
    print("none of the hunted keys decrypt page1")
