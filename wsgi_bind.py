import json
import uuid
import os
import sqlite3
import urllib.request
from urllib.parse import parse_qs
from datetime import datetime, timedelta
import secrets
import hashlib

BOT_TOKEN = "7995732464:AAFfk0dWr1R960hKOhn5cVpnKdfRxcbaHSU"
DB_PATH = "/home/nobbll/tronify.db"
INDEX = "/home/nobbll/index.html"

def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_user(tg_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (tg_id, is_registered, created_at, updated_at) VALUES (?,0,?,?)",
            (tg_id, now_str(), now_str())
        )
        conn.commit()
    conn.close()

def set_registered(tg_id, wallet):
    ensure_user(tg_id)
    conn = db()
    conn.execute(
        "UPDATE users SET is_registered=1, wallet=?, updated_at=? WHERE tg_id=?",
        (wallet, now_str(), tg_id)
    )
    conn.commit()
    conn.close()


def ensure_pending_table():
    conn = db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pending_sign (
        tg_id INTEGER PRIMARY KEY,
        address TEXT NOT NULL,
        wallet TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def set_pending_sign(tg_id, address, wallet=""):
    ensure_pending_table()
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO pending_sign (tg_id, address, wallet, updated_at) VALUES (?,?,?,?)",
        (int(tg_id), address, wallet or "", now_str())
    )
    conn.commit()
    conn.close()

def get_pending_sign(tg_id):
    ensure_pending_table()
    conn = db()
    cur = conn.execute("SELECT address, wallet FROM pending_sign WHERE tg_id=?", (int(tg_id),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"address": row["address"], "wallet": row["wallet"]}

def clear_pending_sign(tg_id):
    ensure_pending_table()
    conn = db()
    conn.execute("DELETE FROM pending_sign WHERE tg_id=?", (int(tg_id),))
    conn.commit()
    conn.close()

DOMAIN = "nobbll.pythonanywhere.com"
NONCE_TTL_SEC = 1800  # 30 min — mobile wallet leave/return


def ensure_nonce_table():
    conn = db()
    conn.execute(
        """
    CREATE TABLE IF NOT EXISTS auth_nonces (
        nonce TEXT PRIMARY KEY,
        tg_id INTEGER NOT NULL,
        address TEXT,
        message TEXT,
        used INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """
    )
    conn.commit()
    conn.close()



# ========== TIP-191 / signMessageV2 verification ==========
def _keccak256(data: bytes) -> bytes:
    try:
        from Crypto.Hash import keccak
        k = keccak.new(digest_bits=256)
        k.update(data)
        return k.digest()
    except Exception as e:
        raise RuntimeError("pycryptodome required for TRON verify: pip install --user pycryptodome") from e


def _tron_message_hash(message: str) -> bytes:
    msg = message.encode("utf-8")
    prefix = b"\x19TRON Signed Message:\n" + str(len(msg)).encode("ascii")
    return _keccak256(prefix + msg)


def _pubkey_to_tron_address(pubkey: bytes) -> str:
    import base58
    import hashlib
    if len(pubkey) == 65 and pubkey[0] == 0x04:
        body = pubkey[1:]
    elif len(pubkey) == 64:
        body = pubkey
    else:
        body = pubkey[1:] if len(pubkey) == 65 else pubkey
    h = _keccak256(body)
    addr = b"\x41" + h[-20:]
    chk = hashlib.sha256(hashlib.sha256(addr).digest()).digest()[:4]
    return base58.b58encode(addr + chk).decode()


def verify_tron_sign_message_v2(message: str, signature: str, expect_address: str = "") -> tuple:
    """
    TIP-191 / signMessageV2 verify.
    Returns (ok, recovered_address, error)
    Accepts: hex 65-byte (with/without 0x), base64 65-byte, some wallets put v as 0/1/27/28.
    """
    try:
        import base58  # noqa: F401
        import hashlib
        from ecdsa import SECP256k1, ellipticcurve, numbertheory
    except Exception as e:
        return False, "", "deps missing: " + str(e)

    if not message or not signature:
        return False, "", "missing message or signature"

    raw = str(signature).strip()
    sig_bytes = b""

    # hex
    hx = raw[2:] if raw.lower().startswith("0x") else raw
    try:
        if all(c in "0123456789abcdefABCDEF" for c in hx) and len(hx) in (128, 130):
            sig_bytes = bytes.fromhex(hx)
    except Exception:
        sig_bytes = b""

    # base64
    if len(sig_bytes) not in (64, 65):
        try:
            import base64
            sig_bytes = base64.b64decode(raw)
        except Exception:
            pass

    if len(sig_bytes) == 64:
        # missing v — try both later with synthetic v
        r = int.from_bytes(sig_bytes[0:32], "big")
        s = int.from_bytes(sig_bytes[32:64], "big")
        v_candidates = [0, 1]
    elif len(sig_bytes) == 65:
        r = int.from_bytes(sig_bytes[0:32], "big")
        s = int.from_bytes(sig_bytes[32:64], "big")
        v = sig_bytes[64]
        if v >= 27:
            rid = v - 27
        else:
            rid = v
        v_candidates = [rid % 2, 1 - (rid % 2)]
    else:
        return False, "", "signature length must be 64 or 65 bytes (got %d)" % len(sig_bytes)

    msg_hash = _tron_message_hash(message)
    z = int.from_bytes(msg_hash, "big")
    curve = SECP256k1.curve
    G = SECP256k1.generator
    n = SECP256k1.order
    p = curve.p()

    recovered = []
    for rid in v_candidates:
        try:
            x = r
            y_sq = (pow(x, 3, p) + 7) % p
            y = pow(y_sq, (p + 1) // 4, p)
            if (y % 2) != (rid % 2):
                y = p - y
            R = ellipticcurve.Point(curve, x, y, n)
            r_inv = numbertheory.inverse_mod(r, n)
            Q = r_inv * (s * R + (n - (z % n)) * G)
            if Q == ellipticcurve.INFINITY:
                continue
            pub = b"\x04" + int(Q.x()).to_bytes(32, "big") + int(Q.y()).to_bytes(32, "big")
            addr = _pubkey_to_tron_address(pub)
            recovered.append(addr)
        except Exception:
            continue

    if not recovered:
        return False, "", "recover failed"

    if expect_address:
        for a in recovered:
            if a == expect_address:
                return True, a, "ok"
        return False, recovered[0], "address mismatch: got %s want %s" % (recovered[0], expect_address)

    return True, recovered[0], "ok"




# ========== Deep Link (TronLink / TokenPocket) + callback ==========
DOMAIN_HTTPS = "https://" + DOMAIN
CALLBACK_URL = DOMAIN_HTTPS + "/api/deeplink/callback"
DAPP_ICON = DOMAIN_HTTPS + "/favicon.ico"
DAPP_NAME = "TRONIFY"


def ensure_deeplink_table():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deeplink_actions (
            action_id TEXT PRIMARY KEY,
            tg_id INTEGER,
            wallet TEXT,
            kind TEXT,
            address TEXT,
            nonce TEXT,
            message TEXT,
            signature TEXT,
            status TEXT,
            raw TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _new_action_id():
    return str(uuid.uuid4())


def create_deeplink_action(tg_id, wallet, kind, address="", nonce="", message=""):
    ensure_deeplink_table()
    action_id = _new_action_id()
    now = now_str()
    conn = db()
    conn.execute(
        "INSERT INTO deeplink_actions (action_id, tg_id, wallet, kind, address, nonce, message, signature, status, raw, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (action_id, int(tg_id or 0), wallet or "", kind, address or "", nonce or "", message or "", "", "pending", "", now, now),
    )
    conn.commit()
    conn.close()
    return action_id


def update_deeplink_action(action_id, **kwargs):
    ensure_deeplink_table()
    if not action_id:
        return
    cols = []
    vals = []
    for k, v in kwargs.items():
        if k in ("address", "signature", "status", "raw", "nonce", "message", "tg_id", "wallet"):
            cols.append(k + "=?")
            vals.append(v)
    if not cols:
        return
    cols.append("updated_at=?")
    vals.append(now_str())
    vals.append(action_id)
    conn = db()
    conn.execute("UPDATE deeplink_actions SET " + ", ".join(cols) + " WHERE action_id=?", vals)
    conn.commit()
    conn.close()


def get_deeplink_action(action_id):
    ensure_deeplink_table()
    conn = db()
    cur = conn.execute("SELECT * FROM deeplink_actions WHERE action_id=?", (action_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def build_tronlink_login_param(action_id, callback_url=None):
    """官方: action=login, protocol=TronLink, chainId=0x2b6653dc"""
    return {
        "url": DOMAIN_HTTPS + "/",
        "callbackUrl": callback_url or CALLBACK_URL,
        "dappName": DAPP_NAME,
        "dappIcon": DAPP_ICON,
        "protocol": "TronLink",
        "version": "1.0",
        "chainId": "0x2b6653dc",
        "action": "login",
        "actionId": action_id,
    }


def build_tronlink_sign_param(action_id, message, address="", callback_url=None):
    """官方: action=sign, signType=signStr (= signMessageV2 TIP-191), 必填 loginAddress"""
    p = {
        "url": DOMAIN_HTTPS + "/",
        "callbackUrl": callback_url or CALLBACK_URL,
        "dappIcon": DAPP_ICON,
        "dappName": DAPP_NAME,
        "protocol": "TronLink",
        "version": "1.0",
        "chainId": "0x2b6653dc",
        "signType": "signStr",
        "message": message or "",
        "action": "sign",
        "actionId": action_id,
    }
    if address:
        p["loginAddress"] = address
    return p


def build_tp_login_param(action_id, callback_url=None):
    """TokenPocket 授权 — TRON mainnet chainId=728126428, network=tron"""
    import time as _time
    return {
        "protocol": "TokenPocket",
        "version": "1.0",
        "dappName": DAPP_NAME,
        "dappIcon": DAPP_ICON,
        "action": "login",
        "actionId": action_id,
        "callbackUrl": callback_url or CALLBACK_URL,
        "expired": int(_time.time()) + 1800,
        "memo": DAPP_NAME,
        "blockchains": [{"chainId": "728126428", "network": "tron"}],
    }


def build_tp_sign_param(action_id, message, address="", callback_url=None):
    """TokenPocket 字符串签名 — TRON; action=sign"""
    import time as _time
    p = {
        "protocol": "TokenPocket",
        "version": "1.0",
        "dappName": DAPP_NAME,
        "dappIcon": DAPP_ICON,
        "action": "sign",
        "actionId": action_id,
        "callbackUrl": callback_url or CALLBACK_URL,
        "expired": int(_time.time()) + 1800,
        "message": message or "",
        "blockchains": [{"chainId": "728126428", "network": "tron"}],
        "blockchain": "tron",
    }
    if address:
        p["address"] = address
        p["from"] = address
    return p


def build_imtoken_open_dapp(url=None):
    """imToken: 无通用 TRON signStr deeplink；打开内置 DApp 浏览器"""
    from urllib.parse import quote
    target = url or (DOMAIN_HTTPS + "/?from=bot&wallet=imtoken")
    return "imtokenv2://navigate/DappView?url=" + quote(target, safe="")


def encode_deeplink(scheme_prefix, param_obj):
    from urllib.parse import quote
    param = quote(json.dumps(param_obj, ensure_ascii=False, separators=(",", ":")), safe="")
    return scheme_prefix + param


def tronlink_deeplink(param_obj):
    return encode_deeplink("tronlinkoutside://pull.activity?param=", param_obj)


def tokenpocket_deeplink(param_obj):
    return encode_deeplink("tpoutside://pull.activity?param=", param_obj)



def normalize_wallet_id(wallet: str) -> str:
    w = (wallet or "").strip().lower()
    if w in ("tp", "tokenpocket", "token-pocket"):
        return "tokenpocket"
    if w in ("im", "imtoken", "im-token"):
        return "imtoken"
    if w in ("tl", "tronlink", "tron-link"):
        return "tronlink"
    return "tronlink"


def assert_wallet_param_isolated(wallet: str, param: dict) -> None:
    """拒绝错误协议字段混入（微米级隔离）"""
    if not isinstance(param, dict):
        return
    proto = str(param.get("protocol") or "")
    if wallet == "tronlink":
        if proto and proto != "TronLink":
            raise ValueError("TronLink param protocol must be TronLink")
        if "blockchains" in param:
            raise ValueError("TronLink must not use TokenPocket blockchains field")
    if wallet == "tokenpocket":
        if proto and proto != "TokenPocket":
            raise ValueError("TokenPocket param protocol must be TokenPocket")
        if param.get("signType") == "signStr":
            raise ValueError("signStr is TronLink-only; TP uses action=sign")
        if param.get("chainId") == "0x2b6653dc" and "blockchains" not in param:
            raise ValueError("TokenPocket TRON must use blockchains chainId 728126428")
    if wallet == "imtoken":
        if "protocol" in param and param.get("note") != "imtoken_dappview":
            raise ValueError("imToken must not use TronLink/TP protocol param")


def build_wallet_deeplink(wallet: str, kind: str, action_id: str, message: str = "", address: str = "", tg_id: int = 0):
    """
    唯一入口：按钱包隔离生成 deep_link。
    返回 (deep_link, param_dict)
    """
    wallet = normalize_wallet_id(wallet)
    kind = (kind or "login").strip().lower()
    if kind not in ("login", "sign"):
        kind = "login"

    if wallet == "tronlink":
        param = build_tronlink_login_param(action_id) if kind == "login" else build_tronlink_sign_param(action_id, message, address)
        assert_wallet_param_isolated(wallet, param)
        return tronlink_deeplink(param), param

    if wallet == "tokenpocket":
        param = build_tp_login_param(action_id) if kind == "login" else build_tp_sign_param(action_id, message, address)
        assert_wallet_param_isolated(wallet, param)
        return tokenpocket_deeplink(param), param

    # imToken only
    land = DOMAIN_HTTPS + "/?from=bot&tg_id=%s&wallet=imtoken&address=%s" % (int(tg_id or 0), address or "")
    deep = build_imtoken_open_dapp(land)
    param = {"note": "imtoken_dappview", "url": land, "wallet": "imtoken"}
    assert_wallet_param_isolated(wallet, param)
    return deep, param


def parse_callback_payload(body, qs):
    """Normalize TronLink / TP callback body into address, signature, action_id."""
    data = dict(body or {})
    for k, v in (qs or {}).items():
        if k not in data and v:
            data[k] = v[0] if isinstance(v, list) else v

    # nested data
    inner = data.get("data")
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except Exception:
            inner = {"raw": inner}
    if isinstance(inner, dict):
        for k, v in inner.items():
            if k not in data:
                data[k] = v

    action_id = str(
        data.get("actionId")
        or data.get("action_id")
        or data.get("id")
        or ""
    ).strip()

    addr = ""
    for key in ("address", "loginAddress", "wallet", "account", "from"):
        v = data.get(key)
        if isinstance(v, str) and v.startswith("T") and 30 <= len(v) <= 36:
            addr = v.strip()
            break
    if not addr:
        import re as _re
        m = _re.search(r"T[1-9A-HJ-NP-Za-km-z]{30,34}", json.dumps(data, ensure_ascii=False))
        if m:
            addr = m.group(0)

    # TronLink 官方回调用 signedData；TP 可能用 signature / sign
    sig = (
        data.get("signedData")
        or data.get("signature")
        or data.get("sign")
        or data.get("messageSignature")
        or ""
    )
    if isinstance(sig, dict):
        sig = sig.get("signature") or sig.get("signedData") or ""
    sig = str(sig).strip() if sig else ""

    return {
        "action_id": action_id,
        "address": addr,
        "signature": sig,
        "raw": data,
    }



def issue_auth_nonce(tg_id, address=""):
    ensure_nonce_table()
    nonce = secrets.token_hex(16)
    issued = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = (datetime.utcnow() + timedelta(seconds=NONCE_TTL_SEC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        "TRONIFY Service Authorization",
        "",
        "This signature verifies your account for TRONIFY membership and platform services.",
        "By signing, you confirm this session and allow TRONIFY to process service requests for your account.",
        "",
        "Permissions requested:",
        "- Owner: prove sole control of this TRON wallet address",
        "- Membership: bind this address to your Telegram account as member identity",
        "- Token usage: authorize TRONIFY to read balances and request energy-rental related signatures for TRX/TRC-10/TRC-20 service flows you initiate",
        "- No unlimited transfer: this message does NOT grant unlimited token transfer rights",
        "",
    ]
    if address:
        parts.append("Wallet Address: " + str(address))
    parts.extend(
        [
            "Telegram ID: " + str(int(tg_id)),
            "Domain: https://" + DOMAIN,
            "Issued At: " + issued,
            "Expiration: " + exp,
            "Nonce: " + nonce,
            "Chain: TRON Mainnet (tron:0x2b6653dc)",
        ]
    )
    msg = "\n".join(parts)
    conn = db()
    conn.execute(
        "INSERT INTO auth_nonces (nonce, tg_id, address, message, used, created_at) VALUES (?,?,?,?,0,?)",
        (nonce, int(tg_id), address or "", msg, now_str()),
    )
    conn.commit()
    conn.close()
    return {
        "nonce": nonce,
        "message": msg,
        "issued_at": issued,
        "expiration": exp,
        "domain": DOMAIN,
        "ttl_sec": NONCE_TTL_SEC,
    }


def consume_auth_nonce(nonce, tg_id):
    ensure_nonce_table()
    if not nonce or not tg_id:
        return False, "missing nonce", None
    conn = db()
    cur = conn.execute(
        "SELECT nonce, tg_id, message, used, created_at FROM auth_nonces WHERE nonce=?",
        (str(nonce),),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "invalid nonce", None
    if int(row["used"] or 0) == 1:
        conn.close()
        return False, "nonce already used", None
    if int(row["tg_id"]) != int(tg_id):
        conn.close()
        return False, "nonce tg mismatch", None
    try:
        created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        if (datetime.utcnow() - created).total_seconds() > NONCE_TTL_SEC:
            conn.close()
            return False, "nonce expired — 请重新获取挑战并签名", None
    except Exception:
        pass
    msg = row["message"] or ""
    conn.execute("UPDATE auth_nonces SET used=1 WHERE nonce=?", (str(nonce),))
    conn.commit()
    conn.close()
    return True, "ok", msg



def tg_send(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read()
    except Exception as e:
        return str(e).encode()


# ========== TRON resource monitor + one-click topup ==========
# Thresholds (can tune)
ENERGY_MIN = 65000          # ~1 pen
ENERGY_TOPUP = 65000 * 2    # default topup 2 pens
TRX_MIN_SUN = 5_000_000     # 5 TRX in sun
BANDWIDTH_MIN = 300         # free net roughly; below => warn
TRONGRID = "https://api.trongrid.io"
FEEE_API_KEY = os.environ.get("FEEE_API_KEY", "3c6f2aa5-7bd5-4378-90b0-52ab777853ba")
FEEE_USER_AGENT = "SC-TRX-BOX/1.0"
FEEE_BASE = "https://feee.io/open"
PAYMENT_ADDRESS = "TPzUyHMDv4ceVgq8jWjJ6hfoDzdLWQrt2b"


def _http_json(url, method="GET", body=None, headers=None, timeout=25):
    h = {"User-Agent": "TRONIFY/1.0", "Accept": "application/json"}
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def fetch_tron_account(address: str) -> dict:
    """On-chain TRX + energy/bandwidth via TronGrid."""
    out = {
        "address": address,
        "trx": 0.0,
        "trx_sun": 0,
        "energy_remaining": 0,
        "energy_limit": 0,
        "bandwidth_remaining": 0,
        "ok": False,
        "error": "",
    }
    if not address or not str(address).startswith("T"):
        out["error"] = "invalid address"
        return out
    try:
        j = _http_json(f"{TRONGRID}/v1/accounts/{address}")
        data = (j.get("data") or [None])[0] or {}
        bal = int(data.get("balance") or 0)
        out["trx_sun"] = bal
        out["trx"] = bal / 1_000_000.0
        # resource fields vary by API version
        res = data.get("account_resource") or {}
        energy_used = int((res.get("energy_usage") or data.get("energy_usage") or 0) or 0)
        energy_limit = int((res.get("EnergyLimit") or res.get("energy_limit") or data.get("energy_limit") or 0) or 0)
        # fallback: dedicated wallet/getaccountresource style via trongrid
        try:
            r2 = _http_json(
                f"{TRONGRID}/wallet/getaccountresource",
                method="POST",
                body={"address": address, "visible": True},
            )
            energy_limit = int(r2.get("EnergyLimit") or energy_limit or 0)
            energy_used = int(r2.get("EnergyUsed") or energy_used or 0)
            net_limit = int(r2.get("freeNetLimit") or 0) + int(r2.get("NetLimit") or 0)
            net_used = int(r2.get("freeNetUsed") or 0) + int(r2.get("NetUsed") or 0)
            out["bandwidth_remaining"] = max(0, net_limit - net_used)
        except Exception:
            pass
        out["energy_limit"] = energy_limit
        out["energy_remaining"] = max(0, energy_limit - energy_used)
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)
    return out


def resource_status(address: str) -> dict:
    info = fetch_tron_account(address)
    energy_low = info.get("energy_remaining", 0) < ENERGY_MIN
    trx_low = info.get("trx_sun", 0) < TRX_MIN_SUN
    info["energy_low"] = energy_low
    info["trx_low"] = trx_low
    bw_low = info.get("bandwidth_remaining", 0) < BANDWIDTH_MIN
    info["bandwidth_low"] = bw_low
    info["need_topup"] = bool(info.get("ok") and (energy_low or trx_low or bw_low))
    info["thresholds"] = {"energy_min": ENERGY_MIN, "trx_min": TRX_MIN_SUN / 1_000_000.0, "bandwidth_min": BANDWIDTH_MIN}
    return info


def feee_create_energy(receive_address: str, resource_value: int) -> dict:
    headers = {
        "key": FEEE_API_KEY,
        "User-Agent": FEEE_USER_AGENT,
        "Content-Type": "application/json",
    }
    try:
        return _http_json(
            f"{FEEE_BASE}/v3/order/create",
            method="POST",
            body={
                "resource_type": 1,
                "receive_address": receive_address,
                "resource_value": int(resource_value),
            },
            headers=headers,
            timeout=35,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}


def notify_resource_low(tg_id: int, address: str, status: dict) -> bool:
    """TG notice with one-click callback hints (user taps bot menu / deep link)."""
    if not tg_id:
        return False
    lines = [
        "⚠️ *资源不足提醒*",
        f"钱包：`{address}`",
        f"TRX：*{status.get('trx', 0):.4f}*",
        f"能量剩余：*{status.get('energy_remaining', 0)}*",
        f"带宽剩余：*{status.get('bandwidth_remaining', 0)}*",
        "",
    ]
    if status.get("energy_low"):
        lines.append("• 能量不足，合约交互可能失败")
    if status.get("trx_low"):
        lines.append("• TRX 不足，无法支付带宽/手续费")
    if status.get("bandwidth_low"):
        lines.append("• 带宽不足，普通转账可能消耗 TRX")
    lines.extend([
        "",
        "一键补充：",
        "• 能量：机器人发送「⚡️ 能量闪租」或点击下方指令",
        "• TRX：向收款地址转入 TRX 后回机器人确认",
        f"收款地址：`{PAYMENT_ADDRESS}`",
        "",
        f"快速指令：`/topup_energy {address}`",
        f"快速指令：`/topup_check {address}`",
    ])
    # Inline-style via bot deep link (works without callback server)
    kb = {
        "inline_keyboard": [
            [
                {"text": "⚡️ 一键补能量", "url": f"https://t.me/SC_TRX_BOXbot?start=topup_energy_{address}"},
                {"text": "💎 查询资源", "url": f"https://t.me/SC_TRX_BOXbot?start=topup_check_{address}"},
            ],
            [
                {"text": "💰 充值TRX指引", "url": f"https://t.me/SC_TRX_BOXbot?start=topup_trx_{address}"},
            ],
            [
                {"text": "打开会员页", "url": "https://nobbll.pythonanywhere.com/?from=bot"},
            ],
        ]
    }
    return bool(tg_send(tg_id, "\n".join(lines), reply_markup=kb))


def check_and_notify_member(tg_id: int, address: str) -> dict:
    st = resource_status(address)
    notified = False
    if st.get("need_topup"):
        notified = notify_resource_low(int(tg_id), address, st)
    st["notified"] = notified
    return st


def one_click_topup_energy(tg_id: int, address: str, pens: int = 2) -> dict:
    """Delegate energy via Feee; notify user result. TRX topup remains deposit-based."""
    pens = max(1, min(int(pens or 2), 20))
    energy = pens * 65000
    st = resource_status(address)
    res = feee_create_energy(address, energy)
    ok = False
    # Feee response shapes vary
    if isinstance(res, dict):
        ok = bool(res.get("ok") or res.get("code") in (0, 200, "0", "200") or res.get("data") or res.get("order_no"))
        if res.get("error"):
            ok = False
    msg_lines = [
        "⚡️ *一键补能量结果*",
        f"钱包：`{address}`",
        f"申请能量：*{energy}*（约 {pens} 笔）",
        f"当前能量：*{st.get('energy_remaining', 0)}*",
        f"当前 TRX：*{st.get('trx', 0):.4f}*",
        "",
        ("✅ 下单成功，能量将在约 1–5 分钟到账" if ok else "❌ 下单失败，请稍后重试或联系客服"),
        f"`{json.dumps(res, ensure_ascii=False)[:300]}`",
    ]
    try:
        tg_send(int(tg_id), "\n".join(msg_lines))
    except Exception:
        pass
    # admin ping on failure
    if not ok:
        try:
            for aid in (8313520468, 7885062002, 8107372042, 8564084677):
                tg_send(aid, f"补能量失败 tg={tg_id} addr={address}\n{res}")
        except Exception:
            pass
    return {"ok": ok, "energy": energy, "pens": pens, "status": st, "provider": res}





def maybe_check_and_notify_member(tg_id: int, address: str) -> dict:
    """注册/绑定成功后：链上查能量与 TRX，不足则 TG 通知并给一键补入口。"""
    try:
        return check_and_notify_member(int(tg_id), address)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def read_body(environ):
    try:
        n = int(environ.get("CONTENT_LENGTH") or 0)
    except Exception:
        n = 0
    return environ["wsgi.input"].read(n) if n else b""

def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO") or "/"

    # CORS
    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])
        return [b""]

    # ========== /api/auth/nonce ==========
    if path.rstrip("/") == "/api/auth/nonce" and method == "GET":
        qs = environ.get("QUERY_STRING") or ""
        params = {}
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
        try:
            tg_id = int(params.get("tg_id") or params.get("telegram_id") or "0")
        except Exception:
            tg_id = 0
        from urllib.parse import unquote
        address = unquote((params.get("address") or "")).strip()
        if not tg_id:
            data = json.dumps({"ok": False, "message": "tg_id required"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        payload = issue_auth_nonce(tg_id, address)
        data = json.dumps({"ok": True, **payload}).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]

    # ========== /api/bind ==========
    if path.rstrip("/") == "/api/bind" and method == "POST":
        try:
            body = json.loads(read_body(environ).decode() or "{}")
        except Exception:
            body = {}

        tg_id = body.get("telegram_id") or body.get("tg_id")
        address = (body.get("address") or body.get("wallet") or "").strip()
        signature = (body.get("signature") or "").strip()
        nonce = (body.get("nonce") or "").strip()
        message = (body.get("message") or "").strip()

        try:
            tg_id = int(tg_id)
        except Exception:
            tg_id = 0

        if not tg_id or not address.startswith("T") or not (30 <= len(address) <= 36):
            data = json.dumps({"ok": False, "message": "参数错误"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        if not nonce or not signature or len(signature) < 20:
            data = json.dumps({"ok": False, "message": "需要有效签名与 nonce"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        ok_n, err_n, server_msg = consume_auth_nonce(nonce, tg_id)
        if not ok_n:
            data = json.dumps({"ok": False, "message": err_n}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        # 必須用伺服器存檔原文做密碼學驗證（防客戶端篡改 message）
        check_msg = server_msg or message or ""
        if not check_msg:
            data = json.dumps({"ok": False, "message": "server message missing"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        if nonce not in check_msg or str(tg_id) not in check_msg:
            data = json.dumps({"ok": False, "message": "message 与 nonce 不匹配"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        if address not in check_msg:
            data = json.dumps({"ok": False, "message": "message 地址不匹配"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        # TIP-191 / signMessageV2 cryptographic verification (server_msg)
        ok_sig, recovered, err_sig = verify_tron_sign_message_v2(check_msg, signature, address)
        if not ok_sig:
            data = json.dumps({
                "ok": False,
                "message": "签名验证失败: " + (err_sig or "invalid"),
                "recovered": recovered or "",
                "hint": "请确认钱包对服务器原文 signMessageV2，且 nonce 未过期"
            }).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        set_registered(tg_id, address)
        try:
            clear_pending_sign(tg_id)
        except Exception:
            pass

        tg_send(
            tg_id,
            f"✅ *钱包绑定成功*\n\n`{address}`\n\n已开通专属会员，请在机器人点击任意菜单开始使用。"
        )
        try:
            check_and_notify_member(tg_id, address)
        except Exception:
            pass

        
        try:
            maybe_check_and_notify_member(tg_id, address)
        except Exception:
            pass

        data = json.dumps({"ok": True, "address": address}).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]


    # ========== /api/pending_sign ==========

    # ---------- TronLink DeepLink callback ----------
    if path.rstrip("/") == "/api/tron_callback":
        try:
            raw = read_body(environ)
            body = {}
            if raw:
                try:
                    body = json.loads(raw.decode() or "{}")
                except Exception:
                    body = {"raw": raw.decode(errors="replace")[:500]}
            # 兼容 query
            qs = parse_qs(environ.get("QUERY_STRING") or "")
            for k, v in qs.items():
                if k not in body and v:
                    body[k] = v[0]
            # 尝试取出地址（兼容多种 TronLink 回调格式）
            addr = ""
            for key in ("address", "loginAddress", "wallet", "account"):
                v = body.get(key)
                if isinstance(v, str) and v.startswith("T"):
                    addr = v.strip()
                    break
            if not addr and isinstance(body.get("data"), str):
                d = body.get("data") or ""
                if d.startswith("T"):
                    addr = d.strip()
                else:
                    try:
                        d2 = json.loads(d)
                        for key in ("address", "loginAddress"):
                            if isinstance(d2.get(key), str) and d2[key].startswith("T"):
                                addr = d2[key].strip()
                                break
                    except Exception:
                        pass
            if not addr and isinstance(body.get("data"), dict):
                for key in ("address", "loginAddress"):
                    v = body["data"].get(key)
                    if isinstance(v, str) and v.startswith("T"):
                        addr = v.strip()
                        break
            # 从任意字符串里抓 T 开头地址
            if not addr:
                import re as _re
                blob = json.dumps(body, ensure_ascii=False)
                m = _re.search(r"T[1-9A-HJ-NP-Za-km-z]{30,34}", blob)
                if m:
                    addr = m.group(0)
            tg_id = body.get("tg_id") or body.get("telegram_id") or 0
            try:
                tg_id = int(tg_id)
            except Exception:
                tg_id = 0
            # query 已在上面合并进 body
            # 签名结果
            sig = (
                body.get("signedData")
                or body.get("signature")
                or body.get("sign")
                or ""
            )
            if isinstance(sig, dict):
                sig = sig.get("signature") or sig.get("signedData") or ""
            sig = str(sig).strip() if sig else ""

            bound_ok = False
            if addr.startswith("T") and 30 <= len(addr) <= 36 and tg_id:
                set_pending_sign(tg_id, addr, "tronlink")
                # 加固：必须 nonce + TIP-191 验证通过才绑定（不信任裸 signature）
                nonce_cb = str(body.get("nonce") or "").strip()
                msg_cb = str(body.get("message") or body.get("msg") or "").strip()
                if sig and len(sig) > 20 and nonce_cb:
                    ok_n, err_n, server_msg = consume_auth_nonce(nonce_cb, tg_id)
                    check_msg = msg_cb or server_msg or ""
                    if ok_n and check_msg and nonce_cb in check_msg and str(tg_id) in check_msg and addr in check_msg:
                        ok_sig, recovered, err_sig = verify_tron_sign_message_v2(check_msg, sig, addr)
                        if ok_sig:
                            try:
                                set_registered(tg_id, addr)
                                bound_ok = True
                                try:
                                    clear_pending_sign(tg_id)
                                except Exception:
                                    pass
                                try:
                                    tg_send(
                                        tg_id,
                                        "✅ *钱包绑定成功*\n`" + addr + "`\n\n已开通专属会员，请返回机器人使用服务。",
                                    )
                                    try:
                                        check_and_notify_member(tg_id, addr)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            except Exception:
                                pass
            # TronLink 期望可访问；返回 JSON
            data = json.dumps({
                "ok": True,
                "received": True,
                "address": addr or None,
                "bound": bool(sig and addr and tg_id),
            }).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        except Exception as e:
            data = json.dumps({"ok": False, "error": str(e)}).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]



    # ---------- user status ----------
    

    # ========== /api/deeplink/go ==========
    # 手机浏览器直接打开即可唤醒钱包（免复制长 deep_link）
    # 例: /api/deeplink/go?tg_id=8313520468&wallet=tronlink&kind=login
    if path.rstrip("/") == "/api/deeplink/go" and method == "GET":
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        try:
            tg_id = int((qs.get("tg_id") or qs.get("telegram_id") or ["0"])[0])
        except Exception:
            tg_id = 0
        wallet = normalize_wallet_id((qs.get("wallet") or ["tronlink"])[0])
        kind = ((qs.get("kind") or ["login"])[0] or "login").strip().lower()
        address = ((qs.get("address") or [""])[0] or "").strip()
        if kind not in ("login", "sign"):
            kind = "login"
        if not tg_id:
            data = "<h1>tg_id required</h1><p>Example: /api/deeplink/go?tg_id=YOUR_ID&wallet=tronlink&kind=login</p>".encode("utf-8")
            start_response("400 Bad Request", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        nonce = ""
        message = ""
        if kind == "sign":
            payload = issue_auth_nonce(tg_id, address)
            nonce = payload.get("nonce") or ""
            message = payload.get("message") or ""
        action_id = create_deeplink_action(tg_id, wallet, kind, address, nonce, message)
        try:
            deep_link, param = build_wallet_deeplink(wallet, kind, action_id, message, address, tg_id)
        except Exception as _iso_err:
            data = json.dumps({"ok": False, "message": "wallet isolation: " + str(_iso_err)}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        # scheme 隔离校验
        if wallet == "tronlink" and not str(deep_link).startswith("tronlinkoutside://"):
            data = json.dumps({"ok": False, "message": "isolation: TronLink scheme mismatch"}).encode()
            start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Content-Length", str(len(data)))])
            return [data]
        if wallet == "tokenpocket" and not str(deep_link).startswith("tpoutside://"):
            data = json.dumps({"ok": False, "message": "isolation: TokenPocket scheme mismatch"}).encode()
            start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Content-Length", str(len(data)))])
            return [data]
        if wallet == "imtoken" and not str(deep_link).startswith("imtokenv2://"):
            data = json.dumps({"ok": False, "message": "isolation: imToken scheme mismatch"}).encode()
            start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Content-Length", str(len(data)))])
            return [data]

        # 短链 → 落地页（由首页自动唤起钱包）
        from urllib.parse import urlencode as _ue
        q = _ue({
            "from": "deeplink",
            "tg_id": str(tg_id),
            "wallet": wallet,
            "autodl": kind,
            "action_id": action_id,
            "address": address or "",
        })
        loc = DOMAIN_HTTPS + "/?" + q
        # 同时把 deep_link 写入 action.raw 供前端按需拉取
        try:
            update_deeplink_action(action_id, raw=json.dumps({"deep_link": deep_link}, ensure_ascii=False))
        except Exception:
            pass
        start_response("302 Found", [
            ("Location", loc),
            ("Content-Length", "0"),
        ])
        return [b""]


    # ========== /api/deeplink/prepare ==========
    # POST { tg_id, wallet: tronlink|tokenpocket, kind: login|sign, address? }
    if path.rstrip("/") == "/api/deeplink/prepare" and method == "POST":
        try:
            body = json.loads(read_body(environ).decode() or "{}")
        except Exception:
            body = {}
        try:
            tg_id = int(body.get("tg_id") or body.get("telegram_id") or 0)
        except Exception:
            tg_id = 0
        wallet = normalize_wallet_id(body.get("wallet") or "tronlink")
        kind = (body.get("kind") or "login").strip().lower()
        address = (body.get("address") or "").strip()
        if kind not in ("login", "sign"):
            kind = "login"
        if not tg_id:
            data = json.dumps({"ok": False, "message": "tg_id required"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        nonce = ""
        message = ""
        if kind == "sign":
            # issue server challenge bound to address if provided
            payload = issue_auth_nonce(tg_id, address)
            nonce = payload.get("nonce") or ""
            message = payload.get("message") or ""
            if not message:
                data = json.dumps({"ok": False, "message": "cannot issue nonce"}).encode()
                start_response("500 Internal Server Error", [
                    ("Content-Type", "application/json"),
                    ("Access-Control-Allow-Origin", "*"),
                    ("Content-Length", str(len(data))),
                ])
                return [data]

        action_id = create_deeplink_action(tg_id, wallet, kind, address, nonce, message)
        try:
            deep_link, param = build_wallet_deeplink(wallet, kind, action_id, message, address, tg_id)
        except Exception as _iso_err:
            data = json.dumps({"ok": False, "message": "wallet isolation: " + str(_iso_err)}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]


        # scheme 隔离校验
        if wallet == "tronlink" and not str(deep_link).startswith("tronlinkoutside://"):
            data = json.dumps({"ok": False, "message": "isolation: TronLink scheme mismatch"}).encode()
            start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Content-Length", str(len(data)))])
            return [data]
        if wallet == "tokenpocket" and not str(deep_link).startswith("tpoutside://"):
            data = json.dumps({"ok": False, "message": "isolation: TokenPocket scheme mismatch"}).encode()
            start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Content-Length", str(len(data)))])
            return [data]
        if wallet == "imtoken" and not str(deep_link).startswith("imtokenv2://"):
            data = json.dumps({"ok": False, "message": "isolation: imToken scheme mismatch"}).encode()
            start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Content-Length", str(len(data)))])
            return [data]

        data = json.dumps({
            "ok": True,
            "action_id": action_id,
            "wallet": wallet,
            "kind": kind,
            "deep_link": deep_link,
            "param": param,
            "nonce": nonce or None,
            "message": message or None,
            "callback_url": CALLBACK_URL,
            "poll_url": DOMAIN_HTTPS + "/api/deeplink/status?action_id=" + action_id,
        }).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]

    # ========== /api/deeplink/callback ==========
    # Wallet POST/GET result here
    if path.rstrip("/") == "/api/deeplink/callback":
        try:
            raw = read_body(environ)
            body = {}
            if raw:
                try:
                    body = json.loads(raw.decode() or "{}")
                except Exception:
                    # form-urlencoded
                    try:
                        from urllib.parse import parse_qs as _pq
                        body = {k: v[0] for k, v in _pq(raw.decode()).items()}
                    except Exception:
                        body = {"raw": raw.decode(errors="replace")[:800]}
            qs = parse_qs(environ.get("QUERY_STRING") or "")
            parsed = parse_callback_payload(body, qs)
            action_id = parsed["action_id"]
            addr = parsed["address"]
            sig = parsed["signature"]
            row = get_deeplink_action(action_id) if action_id else None

            # if no action_id, still accept address for pending
            tg_id = int(row["tg_id"]) if row else 0
            kind = (row["kind"] if row else "") or ""
            wallet = (row["wallet"] if row else "") or ""
            nonce = (row["nonce"] if row else "") or ""
            message = (row["message"] if row else "") or ""

            status = "received"
            bound = False
            if row:
                update_deeplink_action(
                    action_id,
                    address=addr or row.get("address") or "",
                    signature=sig or "",
                    status="signed" if sig else ("connected" if addr else "received"),
                    raw=json.dumps(parsed["raw"], ensure_ascii=False)[:2000],
                )
            if addr and tg_id:
                try:
                    set_pending_sign(tg_id, addr, wallet or "deeplink")
                except Exception:
                    pass

            # If sign + signature + nonce → try TIP-191 bind
            if kind == "sign" and sig and nonce and message and addr and tg_id:
                ok_n, err_n, server_msg = consume_auth_nonce(nonce, tg_id)
                check_msg = server_msg or message
                if ok_n and addr in check_msg:
                    ok_sig, recovered, err_sig = verify_tron_sign_message_v2(check_msg, sig, addr)
                    if ok_sig:
                        set_registered(tg_id, addr)
                        bound = True
                        status = "bound"
                        try:
                            clear_pending_sign(tg_id)
                        except Exception:
                            pass
                        try:
                            tg_send(tg_id, "✅ *钱包绑定成功（Deep Link）*\n`" + addr + "`")
                        except Exception:
                            pass
                        update_deeplink_action(action_id, status="bound", address=addr, signature=sig)
                    else:
                        status = "sig_fail:" + (err_sig or "")
                        update_deeplink_action(action_id, status=status)
                else:
                    status = "nonce_fail:" + (err_n or "")
                    update_deeplink_action(action_id, status=status)
            elif kind == "login" and addr:
                status = "connected"
                if row:
                    update_deeplink_action(action_id, status="connected", address=addr)

            data = json.dumps({
                "ok": True,
                "received": True,
                "action_id": action_id or None,
                "address": addr or None,
                "bound": bound,
                "status": status,
            }).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        except Exception as e:
            data = json.dumps({"ok": False, "error": str(e)}).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]


    # ========== /api/deeplink/link ==========
    if path.rstrip("/") == "/api/deeplink/link" and method == "GET":
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        action_id = (qs.get("action_id") or [""])[0]
        row = get_deeplink_action(action_id) if action_id else None
        deep_link = ""
        if row:
            try:
                raw = row.get("raw") or ""
                if raw:
                    j = json.loads(raw)
                    deep_link = j.get("deep_link") or ""
            except Exception:
                pass
        # 若没有缓存，按 kind 重建
        if not deep_link and row:
            wallet = normalize_wallet_id(row.get("wallet") or "tronlink")
            kind = (row.get("kind") or "login").lower()
            address = row.get("address") or ""
            message = row.get("message") or ""
            try:
                deep_link, _p = build_wallet_deeplink(wallet, kind, action_id, message, address, int(row.get("tg_id") or 0))
            except Exception:
                deep_link = ""
        data = json.dumps({"ok": bool(deep_link), "action_id": action_id, "deep_link": deep_link or None, "row": {
            "status": (row or {}).get("status"),
            "kind": (row or {}).get("kind"),
            "wallet": (row or {}).get("wallet"),
            "address": (row or {}).get("address"),
        } if row else None}).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]


    # ========== /api/deeplink/status ==========
    if path.rstrip("/") == "/api/deeplink/status" and method == "GET":
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        action_id = (qs.get("action_id") or [""])[0]
        row = get_deeplink_action(action_id) if action_id else None
        if not row:
            data = json.dumps({"ok": False, "message": "not found"}).encode()
            start_response("404 Not Found", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        data = json.dumps({
            "ok": True,
            "action_id": row.get("action_id"),
            "status": row.get("status"),
            "address": row.get("address") or None,
            "signature": (row.get("signature") or None) and (row.get("signature")[:16] + "…"),
            "has_signature": bool(row.get("signature")),
            "wallet": row.get("wallet"),
            "kind": row.get("kind"),
            "tg_id": row.get("tg_id"),
        }).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]


    if path.rstrip("/") == "/api/user_status":
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        tg_id = (qs.get("tg_id") or qs.get("telegram_id") or ["0"])[0]
        try:
            tg_id = int(tg_id)
        except Exception:
            tg_id = 0
        row = None
        if tg_id:
            try:
                conn = db()
                cur = conn.cursor()
                cur.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
                row = cur.fetchone()
                conn.close()
            except Exception:
                row = None
        registered = False
        wallet = ""
        if row:
            try:
                registered = bool(row["is_registered"] if "is_registered" in row.keys() else row["registered"] if "registered" in row.keys() else 0)
            except Exception:
                registered = bool(row["wallet"] if "wallet" in row.keys() else False)
            try:
                wallet = (row["wallet"] or row["address"] or "") if row else ""
            except Exception:
                wallet = ""
            if not wallet:
                try:
                    wallet = row["wallet_address"] if "wallet_address" in row.keys() else ""
                except Exception:
                    pass
            if wallet and str(wallet).startswith("T"):
                registered = True
        data = json.dumps({
            "ok": True,
            "tg_id": tg_id,
            "registered": bool(registered),
            "wallet": wallet or "",
        }).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]

    if path.rstrip("/") == "/api/pending_sign":
        if method == "POST":
            try:
                body = json.loads(read_body(environ).decode() or "{}")
            except Exception:
                body = {}
            tg_id = body.get("telegram_id") or body.get("tg_id")
            address = (body.get("address") or "").strip()
            wallet = (body.get("wallet") or "").strip()
            try:
                tg_id = int(tg_id)
            except Exception:
                tg_id = 0
            if not tg_id or not address.startswith("T"):
                data = json.dumps({"ok": False, "message": "参数错误"}).encode()
                start_response("400 Bad Request", [
                    ("Content-Type", "application/json"),
                    ("Access-Control-Allow-Origin", "*"),
                    ("Content-Length", str(len(data))),
                ])
                return [data]
            set_pending_sign(tg_id, address, wallet)
            
            # 不再向机器人推送「完成签名」按钮（按用户要求）
            data = json.dumps({"ok": True, "address": address}).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        if method == "GET":
            qs = environ.get("QUERY_STRING") or ""
            params = dict(x.split("=", 1) for x in qs.split("&") if "=" in x)
            tg_id = params.get("tg_id") or params.get("telegram_id") or "0"
            try:
                tg_id = int(tg_id)
            except Exception:
                tg_id = 0
            row = get_pending_sign(tg_id) if tg_id else None
            data = json.dumps({"ok": True, "pending": row}).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

        if method == "DELETE":
            qs = environ.get("QUERY_STRING") or ""
            params = dict(x.split("=", 1) for x in qs.split("&") if "=" in x)
            tg_id = params.get("tg_id") or "0"
            try:
                tg_id = int(tg_id)
            except Exception:
                tg_id = 0
            if tg_id:
                clear_pending_sign(tg_id)
            data = json.dumps({"ok": True}).encode()
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]

    # ========== 强制外部浏览器中转页 ==========
    # /open_browser.html → 引导 Safari/Chrome，绕过 TG 内置浏览器
    if path.rstrip("/").endswith("open_browser.html") or path.rstrip("/") == "/open_browser":
        open_path = "/home/nobbll/open_browser.html"
        try:
            with open(open_path, "rb") as f:
                data = f.read()
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "no-store"),
            ])
            return [data]
        except FileNotFoundError:
            data = b"<h1>open_browser.html missing - upload to /home/nobbll/open_browser.html</h1>"
            start_response("404 Not Found", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(data))),
            ])
            return [data]


    # ========== /api/resource/check ==========
    if path.rstrip("/") == "/api/resource/check" and method == "GET":
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        address = (qs.get("address") or [""])[0].strip()
        tg_id = (qs.get("tg_id") or ["0"])[0]
        try:
            tg_id = int(tg_id)
        except Exception:
            tg_id = 0
        st = resource_status(address)
        if tg_id and st.get("need_topup"):
            try:
                st["notified"] = notify_resource_low(tg_id, address, st)
            except Exception as e:
                st["notified"] = False
                st["notify_error"] = str(e)
        data = json.dumps({"ok": True, **st}, ensure_ascii=False).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]

    # ========== /api/resource/topup ==========
    if path.rstrip("/") == "/api/resource/topup" and method == "POST":
        try:
            body = json.loads(read_body(environ).decode() or "{}")
        except Exception:
            body = {}
        tg_id = body.get("tg_id") or body.get("telegram_id") or 0
        try:
            tg_id = int(tg_id)
        except Exception:
            tg_id = 0
        address = (body.get("address") or body.get("wallet") or "").strip()
        kind = (body.get("type") or body.get("kind") or "energy").strip().lower()
        pens = body.get("pens") or 2
        if not address.startswith("T") or not tg_id:
            data = json.dumps({"ok": False, "message": "参数错误"}).encode()
            start_response("400 Bad Request", [
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(data))),
            ])
            return [data]
        if kind in ("energy", "both"):
            result = one_click_topup_energy(tg_id, address, pens)
        else:
            result = {"ok": False, "message": "TRX 请向收款地址转入后查询", "payment_address": PAYMENT_ADDRESS}
            try:
                st = resource_status(address)
                tg_send(
                    tg_id,
                    "💎 *TRX 补充说明*\n"
                    f"当前 TRX：*{st.get('trx', 0):.4f}*\n"
                    f"请转入收款地址：`{PAYMENT_ADDRESS}`\n"
                    "到账后发送 /topup_check 查询。",
                )
            except Exception:
                pass
        data = json.dumps({"ok": True, "result": result}, ensure_ascii=False).encode()
        start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Content-Length", str(len(data))),
        ])
        return [data]


    # ========== 静态首页 ==========
    try:
        with open(INDEX, "rb") as f:
            data = f.read()
        start_response("200 OK", [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(data))),
        ])
        return [data]
    except FileNotFoundError:
        data = b"<h1>index.html missing</h1>"
        start_response("404 Not Found", [
            ("Content-Type", "text/html"),
            ("Content-Length", str(len(data))),
        ])
        return [data]
