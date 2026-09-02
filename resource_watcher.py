#!/usr/bin/env python3
"""
TRONIFY member resource watcher
- Scan registered users
- On-chain energy/TRX check via TronGrid
- TG notify when low + one-click topup deep links

Cron (PythonAnywhere Tasks, every 30 min):
  python3.10 /home/nobbll/resource_watcher.py

Or:
  cd /home/nobbll && python3.10 resource_watcher.py
"""
from __future__ import print_function
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

def main():
    # import from wsgi_bind
    import importlib.util
    path = os.path.join(ROOT, "wsgi_bind.py")
    if not os.path.isfile(path):
        path = "/home/nobbll/wsgi_bind.py"
    spec = importlib.util.spec_from_file_location("wsgi_bind", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    conn = mod.db()
    cur = conn.execute(
        "SELECT tg_id, wallet FROM users WHERE is_registered=1 AND wallet IS NOT NULL AND wallet != ''"
    )
    rows = cur.fetchall()
    conn.close()
    print("members:", len(rows))
    notified = 0
    for row in rows:
        try:
            tg_id = int(row["tg_id"] if hasattr(row, "keys") else row[0])
            address = (row["wallet"] if hasattr(row, "keys") else row[1]) or ""
        except Exception:
            continue
        if not address.startswith("T"):
            continue
        try:
            st = mod.check_and_notify_member(tg_id, address)
            if st.get("need_topup") and st.get("notified"):
                notified += 1
            print(tg_id, address[:8], "trx=", st.get("trx"), "energy=", st.get("energy_remaining"), "need=", st.get("need_topup"))
            time.sleep(0.35)  # rate limit TronGrid
        except Exception as e:
            print("err", tg_id, e)
    print("done notified=", notified)

if __name__ == "__main__":
    main()
