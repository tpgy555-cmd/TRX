#!/usr/bin/env python3
"""
TRONIFY TIP-191 / signMessageV2 backend unit tests
Run on PythonAnywhere:
  cd ~
  python3.10 test_tip191_verify.py

Requires: pycryptodome base58 ecdsa
  pip3.10 install --user pycryptodome base58 ecdsa
"""
from __future__ import print_function
import json
import sys
import os

# load verify from deployed wsgi_bind
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
        raise SystemExit("TIP-191 block not found in wsgi_bind.py — redeploy backend")
    ns = {}
    exec(code[start:end], ns)
    return ns["verify_tron_sign_message_v2"]

VECTORS = {
  "curve": "secp256k1",
  "hash": "keccak256",
  "prefix": "\\x19TRON Signed Message:\\n{len}",
  "address_version": "0x41",
  "note": "private_key is TEST ONLY — never fund this key",
  "vectors": [
    {
      "message": "hello TRONIFY",
      "message_utf8_len": 13,
      "prefix_hex": "1954524f4e205369676e6564204d6573736167653a0a3133",
      "digest_hex": "c24cc8a3ffe43e47931d17ded442dcf562c26f67be7f9bb143c60e3338eaf200",
      "signature": "1ec8f8094397878b6d08c652b13e42bb020ae2740c75c3520d0ee8bffe4bd8727de3526376ff89053d82d22ef4a88c51637162b8add01c1bfac88c034bf838971c",
      "signature_0x": "0x1ec8f8094397878b6d08c652b13e42bb020ae2740c75c3520d0ee8bffe4bd8727de3526376ff89053d82d22ef4a88c51637162b8add01c1bfac88c034bf838971c",
      "v": 28,
      "address": "TATunwEDpE8mCD9Dih5BWyUfShkgVgoH25",
      "private_key_hex_TEST_ONLY": "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
    },
    {
      "message": "TRONIFY Service Authorization\n\nThis signature verifies your account for TRONIFY membership and platform services.\nBy signing, you confirm this session and allow TRONIFY to process service requests for your account.\n\nPermissions requested:\n- Owner: prove sole control of this TRON wallet address\n- Membership: bind this address to your Telegram account as member identity\n- Token usage: authorize TRONIFY to read balances and request energy-rental related signatures for TRX/TRC-10/TRC-20 service flows you initiate\n- No unlimited transfer: this message does NOT grant unlimited token transfer rights\n\nWallet Address: TATunwEDpE8mCD9Dih5BWyUfShkgVgoH25\nTelegram ID: 8313520468\nDomain: https://nobbll.pythonanywhere.com\nIssued At: 2026-08-24T06:00:00Z\nExpiration: 2026-08-24T06:10:00Z\nNonce: fixedtestnonce0000111122223333\nChain: TRON Mainnet (tron:0x2b6653dc)",
      "message_utf8_len": 858,
      "prefix_hex": "1954524f4e205369676e6564204d6573736167653a0a383538",
      "digest_hex": "7babae706f8319037642d562848519ce7a237d769299b09a0c7fa076c7981610",
      "signature": "9ab4fc70e64b7ca87e03053c88e09a86c24f61166a78e3ecc2e7d748044c04a153bbfbace71ae7b8471ccfd5e97bb4447b5f068a1f67d1c676bbf053a1b005bf1b",
      "signature_0x": "0x9ab4fc70e64b7ca87e03053c88e09a86c24f61166a78e3ecc2e7d748044c04a153bbfbace71ae7b8471ccfd5e97bb4447b5f068a1f67d1c676bbf053a1b005bf1b",
      "v": 27,
      "address": "TATunwEDpE8mCD9Dih5BWyUfShkgVgoH25",
      "private_key_hex_TEST_ONLY": "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
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

    print("=== TIP-191 fixed vector tests ===")
    print("curve:", VECTORS.get("curve"), "hash:", VECTORS.get("hash"))
    print("TEST address:", VECTORS["vectors"][0]["address"])
    print()

    for i, v in enumerate(VECTORS["vectors"], 1):
        print("Vector", i, "msg_len=", v["message_utf8_len"])
        ok, rec, err = verify(v["message"], v["signature"], v["address"])
        check("valid signature recovers address", ok and rec == v["address"], (ok, rec, err))

        ok2, rec2, err2 = verify(v["message"], v["signature_0x"], v["address"])
        check("0x-prefixed signature accepted", ok2 and rec2 == v["address"], (ok2, rec2, err2))

        ok3, _, err3 = verify(v["message"] + " ", v["signature"], v["address"])
        check("tampered message rejected", not ok3, err3)

        ok4, _, err4 = verify(v["message"], v["signature"], "TXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        check("wrong expected address rejected", not ok4, err4)

        # broken signature
        bad = "00" * 65
        ok5, _, err5 = verify(v["message"], bad, v["address"])
        check("zero signature rejected", not ok5, err5)

        # short signature
        ok6, _, err6 = verify(v["message"], "ab", v["address"])
        check("short signature rejected", not ok6, err6)
        print()

    # prefix / digest self-check for vector 1 (optional; needs pycryptodome)
    v = VECTORS["vectors"][0]
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
        print("  SKIP: digest self-check — run in Bash console:")
        print("    pip3.10 install --user pycryptodome base58 ecdsa")
        print("   ", e)

    print()
    print("RESULT: %d passed, %d failed" % (passed, failed))
    if failed:
        sys.exit(1)
    print("ALL OK")

if __name__ == "__main__":
    main()
