#!/usr/bin/env python3
"""Contract tests for dual member frameworks: new register vs switch wallet."""
from pathlib import Path
import json
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "index.html").read_text("utf-8", errors="ignore") if (ROOT / "index.html").is_file() else ""
JS = (ROOT / "official-handoff.js").read_text("utf-8") if (ROOT / "official-handoff.js").is_file() else ""
BLOB = HTML + "\n" + JS
LIVE = "https://nobbll.pythonanywhere.com"


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    return 0 if cond else 1


def get_json(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode())


fails = 0

# --- page / JS: two member types ---
fails += ok('id="ovSwitch"' in HTML, "index has member hub #ovSwitch")
fails += ok('id="frameNew"' in HTML or "beginNewRegister" in BLOB or "beginRegister" in BLOB,
            "new-register entry exists")
fails += ok('id="frameSwitch"' in HTML or "beginSwitchWallet" in BLOB or "beginSwitch" in BLOB,
            "switch-wallet entry exists")
fails += ok('state.mode = "register"' in BLOB or 'setIntent("register")' in BLOB or 'intent === "register"' in BLOB,
            "register intent is stored")
fails += ok('state.mode = "switch"' in BLOB or 'setIntent("switch")' in BLOB or 'intent === "switch"' in BLOB,
            "switch intent is stored")
fails += ok('intent: state.mode === "switch" ? "switch" : "register"' in BLOB or "intent: intent()" in BLOB or 'intent: intent()' in BLOB,
            "bind payload carries intent")
fails += ok("switch_" in BLOB and "bind_" in BLOB, "bot return uses bind_ / switch_")
fails += ok("/api/user_status" in BLOB, "checks registered status")
fails += ok("/api/bind" in BLOB, "posts bind")
fails += ok("/api/auth/nonce" in BLOB, "fetches nonce")
fails += ok("signMessageV2" in BLOB or "tron_signMessage" in BLOB, "signs membership message")
fails += ok("WalletConnect" in BLOB or "wcConnect" in BLOB or "openOfficial" in BLOB, "connect path present")
fails += ok("tg_id" in BLOB, "carries Telegram id")
fails += ok("showMemberHub" in BLOB or "showSwitchSheet" in BLOB, "registered member opens hub")
fails += ok("checkBound" in BLOB or "registered" in BLOB, "uses server registered flag")

try:
    st = get_json(LIVE + "/api/user_status?tg_id=1")
    fails += ok(st.get("ok") is True, "live user_status ok")
    fails += ok(st.get("registered") is False, "tg_id=1 is unregistered (new-register path)")
except Exception as e:
    fails += ok(False, "live user_status failed: %s" % e)

try:
    nonce = get_json(LIVE + "/api/auth/nonce?tg_id=1")
    fails += ok(nonce.get("ok") is True and nonce.get("nonce"), "live nonce issued for new register")
    fails += ok("TRONIFY Service Authorization" in str(nonce.get("message") or ""),
                "nonce message is membership authorization")
except Exception as e:
    fails += ok(False, "live nonce failed: %s" % e)

print("RESULT failed=%s" % fails)
sys.exit(1 if fails else 0)
