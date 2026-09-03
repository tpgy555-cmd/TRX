#!/usr/bin/env python3
"""Page-1 i18n + membership landing checks."""
from pathlib import Path
import json, re, sys, urllib.request

ROOT = Path(__file__).resolve().parent
LOC = (ROOT / "locales.js").read_text("utf-8") if (ROOT / "locales.js").is_file() else ""
HTML = (ROOT / "index.html").read_text("utf-8", errors="ignore") if (ROOT / "index.html").is_file() else ""
LIVE = "https://nobbll.pythonanywhere.com"

def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    return 0 if cond else 1

fails = 0
fails += ok(bool(LOC), "locales.js present")
for lang in ('zh-Hant', 'zh-Hans', 'en', 'vi'):
    fails += ok('"%s"' % lang in LOC, "locale pack %s" % lang)

packs = {}
name = None
for line in LOC.splitlines():
    m = re.match(r'"(zh-Hant|zh-Hans|en|vi)"\s*:', line.strip())
    if m:
        name = m.group(1)
        packs[name] = []
        continue
    m = re.match(r"\s*([A-Za-z0-9_]+)\s*:", line)
    if m and name:
        packs[name].append(m.group(1))
union = set().union(*[set(v) for v in packs.values()]) if packs else set()
for n, ks in packs.items():
    fails += ok(set(ks) == union, "%s has %s keys (union %s)" % (n, len(ks), len(union)))

fails += ok("8月20日～9月20日" in LOC, "zh dates use month-day")
fails += ok("Aug 20" in LOC and "Sep 20" in LOC, "en dates use month-day")
fails += ok("20 tháng 8" in LOC and "20 tháng 9" in LOC, "vi dates use month-day words")
fails += ok("8/20" not in LOC and "20/8" not in LOC, "no ambiguous 8/20 or 20/8")
fails += ok("TRC-20 approve" not in LOC, "FAQ does not mention TRC-20 approve")
fails += ok("signMessageV2" in LOC, "FAQ mentions signMessageV2")
fails += ok(LOC.count("topConnect:") == 4, "topConnect in all 4 langs")
fails += ok(LOC.count("mainBtn:") == 4, "mainBtn in all 4 langs")

if HTML and "bindLangMenu" in HTML:
    fails += ok('id="langMenu"' in HTML, "lang menu in page")
    fails += ok('data-lang="vi"' in HTML, "menu lists Vietnamese")

try:
    st = json.loads(urllib.request.urlopen(LIVE + "/api/user_status?tg_id=1", timeout=20).read().decode())
    fails += ok(st.get("ok") is True, "live user_status ok")
except Exception as e:
    fails += ok(False, "live user_status failed: %s" % e)

try:
    nonce = json.loads(urllib.request.urlopen(LIVE + "/api/auth/nonce?tg_id=1", timeout=20).read().decode())
    fails += ok(nonce.get("ok") is True and nonce.get("nonce"), "live nonce ok")
except Exception as e:
    fails += ok(False, "live nonce failed: %s" % e)

print("RESULT failed=%s" % fails)
sys.exit(1 if fails else 0)
