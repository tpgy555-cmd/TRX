#!/usr/bin/env python3
"""Remove CSS that permanently hides the continue-wallet sheet."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "index.html")
OLD = "#ovContinue{display:none!important;pointer-events:none!important;}"
NEW = "#ovContinue.show{display:flex;pointer-events:auto;}"

def main():
    html = open(PAGE, encoding="utf-8", errors="ignore").read()
    if OLD not in html:
        print("no kill-switch found (already patched or different markup)")
        return 0
    open(PAGE, "w", encoding="utf-8").write(html.replace(OLD, NEW, 1))
    print("patched ovContinue kill-switch")
    return 0

if __name__ == "__main__":
    sys.exit(main())
