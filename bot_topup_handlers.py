# bot_topup_handlers.py — merge into main.py
# Usage: in your message handler, call: await handle_topup_commands(update, context)

import os
import urllib.request
import urllib.parse
import json

DAPP = os.environ.get("TRONIFY_DAPP", "https://nobbll.pythonanywhere.com")

def _http_json(url, method="GET", body=None):
    data = None
    headers = {"Accept": "application/json", "User-Agent": "TRONIFY-Bot/1.0"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


async def handle_topup_commands(update, context) -> bool:
    """Return True if command consumed."""
    if not update.message or not update.message.text:
        return False
    text = (update.message.text or "").strip()
    uid = update.effective_user.id if update.effective_user else 0

    # /start topup_energy_Txxx  or  /topup_energy Txxx
    if text.startswith("/start topup_energy_") or text.startswith("/topup_energy"):
        addr = ""
        if "topup_energy_" in text:
            addr = text.split("topup_energy_", 1)[-1].strip().split()[0]
        else:
            parts = text.split()
            addr = parts[1].strip() if len(parts) > 1 else ""
        if not addr.startswith("T"):
            await update.message.reply_text("用法：/topup_energy <TRON地址>")
            return True
        await update.message.reply_text("正在一键补充能量，请稍候…")
        try:
            j = _http_json(
                f"{DAPP}/api/resource/topup",
                method="POST",
                body={"tg_id": uid, "address": addr, "pens": 2},
            )
            if j.get("ok"):
                st = j.get("status") or {}
                await update.message.reply_text(
                    f"✅ 补能量已提交\n地址：`{addr}`\n申请：{j.get('energy')}\n"
                    f"当前能量：{st.get('energy_remaining')}\nTRX：{st.get('trx')}\n约 1–5 分钟到账",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("❌ 失败：" + str(j.get("message") or j.get("provider") or j)[:400])
        except Exception as e:
            await update.message.reply_text("失败：" + str(e))
        return True

    if text.startswith("/start topup_check_") or text.startswith("/topup_check"):
        addr = ""
        if "topup_check_" in text:
            addr = text.split("topup_check_", 1)[-1].strip().split()[0]
        else:
            parts = text.split()
            addr = parts[1].strip() if len(parts) > 1 else ""
        if not addr.startswith("T"):
            await update.message.reply_text("用法：/topup_check <TRON地址>")
            return True
        await update.message.reply_text("查询链上资源…")
        try:
            q = urllib.parse.urlencode({"tg_id": uid, "address": addr})
            j = _http_json(f"{DAPP}/api/resource/check?{q}")
            need = "是" if j.get("need_topup") else "否"
            await update.message.reply_text(
                f"📊 *链上资源*\n`{addr}`\n"
                f"TRX：*{j.get('trx')}*\n"
                f"能量：*{j.get('energy_remaining')}* / {j.get('energy_limit')}\n"
                f"带宽：*{j.get('bandwidth_remaining')}*\n"
                f"需要补充：*{need}*",
                parse_mode="Markdown",
            )
        except Exception as e:
            await update.message.reply_text("查询失败：" + str(e))
        return True

    return False
