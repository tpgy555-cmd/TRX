#!/usr/bin/env python3
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "official-handoff.js")
OLD = "#ovContinue{display:none!important;pointer-events:none!important;}"
NEW = "#ovContinue.show{display:flex;pointer-events:auto;}"

def main():
    if not os.path.isfile(PAGE):
        print("index.html missing"); return 1
    html = open(PAGE, encoding="utf-8", errors="ignore").read()
    if OLD in html:
        html = html.replace(OLD, NEW, 1)
        print("patched ovContinue kill-switch")
    else:
        print("kill-switch already absent")
    if not os.path.isfile(JS):
        print("official-handoff.js missing"); return 1
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
