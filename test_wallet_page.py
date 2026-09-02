#!/usr/bin/env python3
"""Static checks for the DApp wallet page. Fail CI if the connect/sign UI is missing."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(ROOT, "index.html")

REQUIRED_IDS = [
    "ovWallet",
    "ovContinue",
    "ovSign",
    "ovSuccess",
    "walletList",
    "btnOpenWallet",
    "doSign",
    "signMsgText",
]
REQUIRED_WALLETS = ["tronlink", "tokenpocket", "imtoken"]
REQUIRED_APIS = ["/api/bind", "/api/pending_sign", "/api/auth/nonce"]


def main():
    failed = 0
    if not os.path.isfile(PAGE):
        print("FAIL: index.html missing")
        sys.exit(1)
    html = open(PAGE, encoding="utf-8", errors="ignore").read()
    print("index.html bytes", len(html.encode("utf-8", errors="ignore")))

    def check(name, cond):
        nonlocal failed
        print(("PASS" if cond else "FAIL") + ":", name)
        if not cond:
            failed += 1

    for eid in REQUIRED_IDS:
        check("has #" + eid, ('id="%s"' % eid) in html or ("id='%s'" % eid) in html)
    for w in REQUIRED_WALLETS:
        check("mentions " + w, re.search(w, html, re.I) is not None)
    for api in REQUIRED_APIS:
        check("calls " + api, api in html)
    check("ovContinue not force-hidden", not re.search(r"#ovContinue\s*\{[^}]*display\s*:\s*none\s*!important", html, re.I))
    check("signMessage present", "signMessage" in html)
    print("RESULT failed=", failed)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
