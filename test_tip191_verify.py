#!/usr/bin/env python3
"""TRONIFY TIP-191 / signMessageV2 backend unit tests."""
from __future__ import print_function
import json
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

def load_verify():
    path = os.path.join(ROOT, "wsgi_bind.py")
    if not os.path.isfile(path):
        path = "/home/nobbll/wsgi_bind.py"
    code = open(path, "r", encoding="utf-8").read()
    start = code.find("# ========== TIP-191")
    end = code.find("def issue_auth_nonce")
    if start < 0 or end < 0:
        raise SystemExit("TIP-191 block not found in wsgi_bind.py")
    ns = {
        "DOMAIN": "nobbll.pythonanywhere.com",
        "__name__": "tip191_slice",
    }
    exec(code[start:end], ns)
    if "verify_tron_sign_message_v2" not in ns:
        raise SystemExit("verify_tron_sign_message_v2 missing after exec")
    return ns["verify_tron_sign_message_v2"]

VECTORS = {
  "curve": "secp256k1",
  "hash": "keccak256",
  "vectors": [
    {
      "message": "hello TRONIFY",
      "message_utf8_len": 13,
      "prefix_hex": "1954524f4e205369676e6564204d6573736167653a0a3133",
      "digest_hex": "c24cc8a3ffe43e47931d17ded442dcf562c26f67be7f9bb143c60e3338eaf200",
      "signature": "1ec8f8094397878b6d08c652b13e42bb020ae2740c75c3520d0ee8bffe4bd8727de3526376ff89053d82d22ef4a88c51637162b8add01c1bfac88c034bf838971c",
      "signature_0x": "0x1ec8f8094397878b6d08c652b13e42bb020ae2740c75c3520d0ee8bffe4bd8727de3526376ff89053d82d22ef4a88c51637162b8add01c1bfac88c034bf838971c",
      "v": 28,
      "address": "TATunwEDpE8mCD9Dih5BWyUfShkgVgoH25"
    }
  ]
}

def main():
    verify = load_verify()
    passed = 0
    failed = 0

    def check(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  PASS:", name)
        else:
            failed += 1
            print("  FAIL:", name, detail)

    print("=== TIP-191 CI tests ===")
    v = VECTORS["vectors"][0]
    ok, rec, err = verify(v["message"], v["signature"], v["address"])
    check("valid signature recovers address", ok and rec == v["address"], (ok, rec, err))
    ok2, rec2, err2 = verify(v["message"], v["signature_0x"], v["address"])
    check("0x-prefixed signature accepted", ok2 and rec2 == v["address"], (ok2, rec2, err2))
    ok3, _, err3 = verify(v["message"] + " ", v["signature"], v["address"])
    check("tampered message rejected", not ok3, err3)
    ok4, _, err4 = verify(v["message"], v["signature"], "TXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    check("wrong expected address rejected", not ok4, err4)
    ok5, _, err5 = verify(v["message"], "00" * 65, v["address"])
    check("zero signature rejected", not ok5, err5)
    ok6, _, err6 = verify(v["message"], "ab", v["address"])
    check("short signature rejected", not ok6, err6)

    try:
        from Crypto.Hash import keccak
        def k256(d):
            x = keccak.new(digest_bits=256); x.update(d); return x.digest()
        msg_b = v["message"].encode("utf-8")
        prefix = b"\x19TRON Signed Message:\n" + str(len(msg_b)).encode("ascii")
        digest = k256(prefix + msg_b).hex()
        check("digest matches vector", digest == v["digest_hex"], digest)
        check("prefix matches vector", prefix.hex() == v["prefix_hex"], prefix.hex())
    except Exception as e:
        print("  SKIP digest:", e)

    print("RESULT: %d passed, %d failed" % (passed, failed))
    if failed:
        sys.exit(1)
    print("ALL OK")

if __name__ == "__main__":
    main()
