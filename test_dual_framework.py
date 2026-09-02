#!/usr/bin/env python3
"""Contract tests for dual register / switch-wallet frameworks."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
JS = (ROOT / "official-handoff.js").read_text("utf-8")

def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    return 0 if cond else 1

fails = 0
fails += ok("beginRegister" in JS and "beginSwitch" in JS, "js has register + switch entry")
fails += ok("tronify_intent" in JS and "tronify_rebind" in JS, "js persists intent/rebind")
fails += ok('intent === "switch"' in JS, "js branches on switch intent")
fails += ok("Continue in " in JS, "js uses official Continue copy")
fails += ok("tronlinkoutside://pull.activity" in JS, "js uses official TronLink open")
fails += ok("signMessageV2" in JS, "js signs with signMessageV2")
fails += ok("user_status" in JS and "pending_sign" in JS, "js polls status + pending")
fails += ok("switch_" in JS and "bind_" in JS, "js returns to bot with bind_ / switch_")
fails += ok("showSwitchSheet" in JS and "ovSwitch" in JS, "js opens switch confirm sheet")
sys.exit(1 if fails else 0)
