#!/usr/bin/env bash
# TRONIFY local CI — run before deploy
set -euo pipefail
cd "$(dirname "$0")"

echo "== deps =="
python3 -m pip install -q pycryptodome base58 ecdsa || pip3 install -q pycryptodome base58 ecdsa

echo "== TIP-191 unit tests =="
python3 test_tip191_verify.py

echo "== py_compile wsgi_bind.py =="
python3 -m py_compile wsgi_bind.py

echo "== optional live smoke (set SMOKE=1) =="
if [ "${SMOKE:-0}" = "1" ]; then
  HOST="${HOST:-nobbll.pythonanywhere.com}"
  curl -sS "https://${HOST}/api/auth/nonce?tg_id=1&address=TATunwEDpE8mCD9Dih5BWyUfShkgVgoH25" | head -c 300
  echo
  curl -sS -X POST "https://${HOST}/api/bind" \
    -H "Content-Type: application/json" \
    -d '{"tg_id":1,"address":"TATunwEDpE8mCD9Dih5BWyUfShkgVgoH25","signature":"00","nonce":"x","message":"x"}' | head -c 200
  echo
fi

echo "CI LOCAL OK"
