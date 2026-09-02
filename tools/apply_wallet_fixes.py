#!/usr/bin/env python3
"""CI-only patch: do not restyle landing page. Only wallet flow."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "official-handoff.js")
OLD = "#ovContinue{display:none!important;pointer-events:none!important;}"
NEW = (
    "#ovContinue{display:none;pointer-events:none;}"
    "#ovContinue.show{display:flex!important;visibility:visible!important;"
    "pointer-events:auto!important;z-index:2147483646!important;}"
)

def main():
    if not os.path.isfile(PAGE):
        print("index.html missing")
        return 1
    html = open(PAGE, encoding="utf-8", errors="ignore").read()
    if OLD in html:
        html = html.replace(OLD, NEW, 1)
        print("unhid ovContinue for wallet flow")
    else:
        print("ovContinue kill-switch already absent")
    html = html.replace("setInterval(hideCont, 800);", "/* hideCont disabled for official Continue sheet */")
    if not os.path.isfile(JS):
        print("official-handoff.js missing")
        return 1
    js = open(JS, encoding="utf-8").read().strip()
    if "__TRONIFY_OFFICIAL_HANDOFF" not in html:
        block = "\n<script>\n" + js + "\n</script>\n"
        html = html.replace("</html>", block + "</html>", 1) if "</html>" in html else html + block
        print("injected official-handoff.js")
    else:
        print("handoff already present")
    open(PAGE, "w", encoding="utf-8").write(html)
    return 0

if __name__ == "__main__":
    sys.exit(main())
