# -*- coding: utf-8 -*-
"""TRONIFY 完整单文件版 — 覆盖 /home/nobbll/main.py 后运行 python3.10 main.py"""

# ========== CONFIG ==========



# Telegram
BOT_TOKEN = "7995732464:AAFfk0dWr1R960hKOhn5cVpnKdfRxcbaHSU"
BOT_USERNAME = "SC_TRX_BOXbot"

# 管理员（数字 ID）
ADMIN_IDS = [
    8313520468,   # @SC_TRXbot
    7885062002,   # @blusele
    8107372042,   # @strator99
    8564084677,   # @nobbll8252
]

# 客服人员（最多 15 位，填 Telegram 用户名，不要带 @）
CS_USERNAMES = [
    "SC_TRXbot",  # 1 主客服
    None,  # 2
    None,  # 3
    None,  # 4
    None,  # 5
    None,  # 6
    None,  # 7
    None,  # 8
    None,  # 9
    None,  # 10
    None,  # 11
    None,  # 12
    None,  # 13
    None,  # 14
    None,  # 15
]

# 收款地址（TRX / USDT-TRC20 同一地址）
PAYMENT_ADDRESS = "TPzUyHMDv4ceVgq8jWjJ6hfoDzdLWQrt2b"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# DApp
DAPP_URL = "https://nobbll.pythonanywhere.com"
DAPP_REGISTER_URL = f"{DAPP_URL}/?from=bot"

# Feee.io
FEEE_API_KEY = "3c6f2aa5-7bd5-4378-90b0-52ab777853ba"
FEEE_USER_AGENT = "SC-TRX-BOX/1.0"
FEEE_BASE = "https://feee.io/open"
FEEE_MARKUP = 0.10  # 仅内部成本参考；对客能量严格 3 TRX/笔，不加价
ENERGY_APPLY_MARKUP = False  # False=对客不加价

# 业务参数
ENERGY_PRICE_PER_PEN = 3.0          # 闪租对客价：严格 3 TRX/笔（与海报一致）
CHECKIN_FREE_PENS = 1
FIAT_FEE_USDT = 15.0
FIAT_MIN_USDT = 20.0
MEMBER_PRICE_USDT = 88.0
MEMBER_DAYS = 30

# 笔数套餐单价 TRX/笔
PACKAGE_PRICES = {
    "1天": 3.6,
    "3天": 3.5,
    "7天": 3.4,
    "14天": 3.3,
    "包月": 3.2,
}
PACKAGE_PENS_OPTIONS = {
    "1天": [5, 10, 20, 30, 50, 100],
    "3天": [5, 10, 20, 30, 50, 100],
    "7天": [5, 10, 20, 30, 50, 100],
    "14天": [5, 10, 20, 30, 50, 100],
    "包月": [5, 10, 20, 30, 50, 60, 70, 80, 90, 100],
}
PACKAGE_DAILY_MIN = 3  # 托管每日低消笔数
PACKAGE_AUTO_SEND = 2  # 每次自动发能量笔数

# 邀请返利（按会员等级）
REBATE_RATES = {
    "普通会员": 0.05,
    "铜牌会员": 0.08,
    "银牌会员": 0.12,
    "金牌会员": 0.15,
    "钻石会员": 0.15,
}

# 等级门槛（有效邀请人数）
LEVEL_THRESHOLDS = [
    (0, "普通会员"),
    (5, "铜牌会员"),
    (10, "银牌会员"),
    (15, "金牌会员"),
    (30, "钻石会员"),
]

# 汇率（可后续接实时 API）
USDT_TO_TRX = 2.748
TRX_TO_USDT = 0.305

# 数据库路径（PythonAnywhere 家目录）
DB_PATH = "/home/nobbll/tronify.db"

# ========== DB ==========
import sqlite3
import time
from datetime import datetime, timedelta

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        wallet TEXT,
        is_registered INTEGER DEFAULT 0,
        level TEXT DEFAULT '普通会员',
        balance_usdt REAL DEFAULT 0,
        balance_trx REAL DEFAULT 0,
        pens INTEGER DEFAULT 0,
        inviter_id INTEGER,
        valid_invites INTEGER DEFAULT 0,
        member_until TEXT,
        auto_renew INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE,
        tg_id INTEGER,
        order_type TEXT,
        amount REAL,
        currency TEXT,
        status TEXT DEFAULT 'pending',
        extra TEXT,
        created_at TEXT,
        paid_at TEXT
    );
    CREATE TABLE IF NOT EXISTS packages (
        tg_id INTEGER PRIMARY KEY,
        plan TEXT,
        pens_left INTEGER,
        daily_min INTEGER DEFAULT 3,
        bound_wallet TEXT,
        expire_at TEXT,
        hosting INTEGER DEFAULT 1,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS checkins (
        tg_id INTEGER,
        day TEXT,
        PRIMARY KEY (tg_id, day)
    );
    CREATE TABLE IF NOT EXISTS rebates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER,
        from_tg_id INTEGER,
        amount REAL,
        rate REAL,
        note TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg TEXT,
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()

def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

def upsert_user(tg_id, username="", full_name=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,))
    if c.fetchone():
        c.execute(
            "UPDATE users SET username=?, full_name=?, updated_at=? WHERE tg_id=?",
            (username or "", full_name or "", now_str(), tg_id),
        )
    else:
        c.execute(
            "INSERT INTO users (tg_id, username, full_name, created_at, updated_at) VALUES (?,?,?,?,?)",
            (tg_id, username or "", full_name or "", now_str(), now_str()),
        )
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def set_registered(tg_id, wallet):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET is_registered=1, wallet=?, updated_at=? WHERE tg_id=?",
        (wallet, now_str(), tg_id),
    )
    conn.commit()
    conn.close()

def set_inviter(tg_id, inviter_id):
    if not inviter_id or inviter_id == tg_id:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT inviter_id FROM users WHERE tg_id=?", (tg_id,))
    row = c.fetchone()
    if row and row["inviter_id"]:
        conn.close()
        return
    c.execute("UPDATE users SET inviter_id=? WHERE tg_id=?", (inviter_id, tg_id))
    conn.commit()
    conn.close()

def add_valid_invite(inviter_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET valid_invites = valid_invites + 1, updated_at=? WHERE tg_id=?",
        (now_str(), inviter_id),
    )
    c.execute("SELECT valid_invites FROM users WHERE tg_id=?", (inviter_id,))
    row = c.fetchone()
    invites = row["valid_invites"] if row else 0
    level = "普通会员"
    for threshold, name in LEVEL_THRESHOLDS:
        if invites >= threshold:
            level = name
    c.execute("UPDATE users SET level=? WHERE tg_id=?", (level, inviter_id))
    conn.commit()
    conn.close()
    return level, invites

def add_pens(tg_id, n):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET pens = pens + ?, updated_at=? WHERE tg_id=?", (n, now_str(), tg_id))
    conn.commit()
    conn.close()

def has_checked_in(tg_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM checkins WHERE tg_id=? AND day=?", (tg_id, today_str()))
    row = c.fetchone()
    conn.close()
    return bool(row)

def do_checkin(tg_id, free_pens=1):
    if has_checked_in(tg_id):
        return False
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO checkins (tg_id, day) VALUES (?,?)", (tg_id, today_str()))
    c.execute("UPDATE users SET pens = pens + ?, updated_at=? WHERE tg_id=?", (free_pens, now_str(), tg_id))
    conn.commit()
    conn.close()
    return True

def create_order(tg_id, order_type, amount, currency, extra=""):
    order_no = f"{order_type[:2].upper()}{int(time.time())}{tg_id % 10000}"
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO orders (order_no, tg_id, order_type, amount, currency, status, extra, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (order_no, tg_id, order_type, amount, currency, "pending", extra, now_str()),
    )
    conn.commit()
    conn.close()
    return order_no

def mark_order_paid(order_no):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE orders SET status='paid', paid_at=? WHERE order_no=?",
        (now_str(), order_no),
    )
    conn.commit()
    conn.close()

def set_package(tg_id, plan, pens, days, wallet):
    expire = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO packages (tg_id, plan, pens_left, bound_wallet, expire_at, hosting, updated_at)
           VALUES (?,?,?,?,?,1,?)
           ON CONFLICT(tg_id) DO UPDATE SET
             plan=excluded.plan, pens_left=excluded.pens_left,
             bound_wallet=excluded.bound_wallet, expire_at=excluded.expire_at,
             hosting=1, updated_at=excluded.updated_at""",
        (tg_id, plan, pens, wallet or "", expire, now_str()),
    )
    conn.commit()
    conn.close()

def get_package(tg_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM packages WHERE tg_id=?", (tg_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def add_rebate(tg_id, from_tg_id, amount, rate, note=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO rebates (tg_id, from_tg_id, amount, rate, note, created_at) VALUES (?,?,?,?,?,?)",
        (tg_id, from_tg_id, amount, rate, note, now_str()),
    )
    c.execute(
        "UPDATE users SET balance_usdt = balance_usdt + ?, updated_at=? WHERE tg_id=?",
        (amount, now_str(), tg_id),
    )
    conn.commit()
    conn.close()

def get_rebate_rate(level):
    return REBATE_RATES.get(level, 0.05)


def list_orders(tg_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM orders WHERE tg_id=? ORDER BY id DESC LIMIT ?",
        (tg_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def list_invitees(inviter_id, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT tg_id, username, full_name, is_registered, created_at FROM users WHERE inviter_id=? ORDER BY created_at DESC LIMIT ?",
        (inviter_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def list_rebates(tg_id, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM rebates WHERE tg_id=? ORDER BY id DESC LIMIT ?",
        (tg_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def total_rebate(tg_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) AS s FROM rebates WHERE tg_id=?", (tg_id,))
    s = c.fetchone()["s"]
    conn.close()
    return float(s or 0)

def create_withdraw(tg_id, amount):
    return create_order(tg_id, "withdraw", amount, "USDT", "rebate_withdraw")

def list_withdraws(tg_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM orders WHERE tg_id=? AND order_type='withdraw' ORDER BY id DESC LIMIT ?",
        (tg_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# ========== FEEE ==========
import requests

HEADERS = {
    "key": FEEE_API_KEY,
    "User-Agent": FEEE_USER_AGENT,
    "Content-Type": "application/json",
}

def query_account():
    r = requests.get(f"{FEEE_BASE}/v2/api/query", headers=HEADERS, timeout=20)
    return r.json()

def create_energy_order(receive_address: str, resource_value: int, rent_time_unit="h", rent_duration=1):
    """
    V2 下单：能量
    resource_value: 能量数量，例如 65000
    rent_time_unit: h / d / m
    rent_duration: 配合 unit
    """
    payload = {
        "resource_type": 1,
        "receive_address": receive_address,
        "resource_value": int(resource_value),
        "rent_duration": int(rent_duration),
        "rent_time_unit": rent_time_unit,
        "rent_time_second": 0,
    }
    r = requests.post(
        f"{FEEE_BASE}/v2/order/submit",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    return r.json()

def create_energy_v3(receive_address: str, resource_value: int):
    """V3 固定约 5 分钟，更便宜"""
    payload = {
        "resource_type": 1,
        "receive_address": receive_address,
        "resource_value": int(resource_value),
    }
    r = requests.post(
        f"{FEEE_BASE}/v3/order/create",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    return r.json()

def order_detail(order_no: str):
    r = requests.get(
        f"{FEEE_BASE}/v2/order/query",
        headers=HEADERS,
        params={"order_no": order_no},
        timeout=20,
    )
    return r.json()

# ========== BOT ==========
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters,
)

(
    ENERGY_CONFIRM, ENERGY_PAY,
    PKG_PLAN, PKG_PENS, PKG_PAY,
    TRX_AMOUNT, TRX_CONFIRM, TRX_PAY,
    FIAT_COUNTRY, FIAT_AMOUNT, FIAT_CONFIRM, FIAT_PAY, FIAT_INFO,
    RECHARGE_AMOUNT, RECHARGE_PAY,
    MEMBER_PAY,
    TG_ITEM, TG_QTY, TG_TARGET, TG_PAY,
) = range(20)


def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⚡️ 能量闪租"), KeyboardButton("🗓 每日签到")],
        [KeyboardButton("💸 TRX 闪兑"), KeyboardButton("✏️ 笔数套餐")],
        [KeyboardButton("✈️ TG 商品"), KeyboardButton("↔️ 法币闪兑")],
        [KeyboardButton("🪙 我要充值"), KeyboardButton("⭕️ 个人中心")],
        [KeyboardButton("💼 代理中心"), KeyboardButton("👑 会员订阅")],
    ], resize_keyboard=True)


def personal_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👤 基本资料"), KeyboardButton("💰 我的资产")],
        [KeyboardButton("⚡ 能量额度"), KeyboardButton("🏆 会员等级")],
        [KeyboardButton("📋 我的订单"), KeyboardButton("⚙️ 账号设置")],
        [KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)


def agent_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 邀请链接"), KeyboardButton("👥 邀请记录")],
        [KeyboardButton("💰 返利明细"), KeyboardButton("🏆 会员等级")],
        [KeyboardButton("💸 申请提现"), KeyboardButton("📋 提现记录")],
        [KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)


def cancel_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 取消")]], resize_keyboard=True)


def pay_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 复制地址"), KeyboardButton("🔄 我已转账")],
        [KeyboardButton("🔙 取消")],
    ], resize_keyboard=True)


async def notify_admins(context, text: str):
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid, "🛠 管理通知\n\n" + str(text))
        except Exception:
            pass


def require_registered(user_row):
    return user_row and user_row.get("is_registered")


def register_link(tg_id: int):
    return f"{DAPP_URL}/?tg_id={tg_id}&from=bot"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.full_name or "")
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref"):
            try:
                set_inviter(user.id, int(arg.replace("ref", "")))
            except ValueError:
                pass
        # DApp 签名绑定回跳：/start bind_Txxxxx
        if arg.startswith("bind_"):
            wallet = arg[5:].strip()
            if wallet.startswith("T") and 30 <= len(wallet) <= 36:
                set_registered(user.id, wallet)
                inv = get_user(user.id)
                if inv and inv.get("inviter_id"):
                    level, invites = add_valid_invite(inv["inviter_id"])
                    await notify_admins(
                        context,
                        f"新会员绑定\n用户 {user.id} @{user.username or '-'}\n钱包 {wallet}\n邀请人 {inv['inviter_id']} 等级{level}({invites})"
                    )
                else:
                    await notify_admins(context, f"新会员绑定\n用户 {user.id} @{user.username or '-'}\n钱包 {wallet}")
                await update.message.reply_text(
                    f"✅ 钱包绑定成功\n`{wallet}`\n\n已开通专属会员，请选择服务：",
                    parse_mode="Markdown",
                    reply_markup=main_menu(),
                )
                return
    row = get_user(user.id)
    if not require_registered(row):
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("🌐 立即开通 DApp 专属会员")],
            [KeyboardButton("✈️ 联系客服")],
        ], resize_keyboard=True)
        await update.message.reply_text(
            "🏦 欢迎使用 Tronify 能量机器人\n\n"
            "检测到您尚未注册\n\n"
            "本机器人所有服务仅对【DApp 专属入驻会员】开放使用。\n\n"
            "请先通过官方 DApp 连接冷钱包完成注册，成为专属会员后即可解锁全部功能。\n\n"
            "未注册将无法使用任何服务。\n\n"
            "⚠️ 打开链接后请点右上角 ··· →「在浏览器中打开」\n"
            "必须使用 Safari / Chrome，不要用 Telegram 内置浏览器。",
            reply_markup=kb,
        )
        return
    level = row.get("level") or "普通会员"
    w = row.get("wallet") or ""
    short = (w[:8] + "..." + w[-4:]) if len(w) > 12 else w
    await update.message.reply_text("🏦 欢迎回来，TRONIFY 专属会员！")
    await update.message.reply_text(
        f"👤 会员信息\n昵称：{user.full_name}\nUID：{user.id}\n等级：{level}\n钱包：{short}"
    )
    await update.message.reply_text("请选择服务：", reply_markup=main_menu())


# ----- energy -----
async def energy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not require_registered(row):
        await update.message.reply_text("请先完成 Dapp 注册会员")
        return ConversationHandler.END
    price = ENERGY_PRICE_PER_PEN  # 严格 3 TRX/笔
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("1笔"), KeyboardButton("2笔"), KeyboardButton("3笔")],
        [KeyboardButton("5笔"), KeyboardButton("10笔")],
        [KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        f"⚡️ 能量闪租（约1小时）\n单价 {price:.0f} TRX / 笔\n"
        f"收款地址：\n`{PAYMENT_ADDRESS}`",
        reply_markup=kb, parse_mode="Markdown",
    )
    return ENERGY_CONFIRM


async def energy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 返回主菜单":
        await update.message.reply_text("已返回", reply_markup=main_menu())
        return ConversationHandler.END
    mapping = {"1笔": 1, "2笔": 2, "3笔": 3, "5笔": 5, "10笔": 10}
    if text not in mapping:
        await update.message.reply_text("请选择正确笔数")
        return ENERGY_CONFIRM
    pens = mapping[text]
    unit = ENERGY_PRICE_PER_PEN  # 严格 3 TRX/笔
    amount = round(pens * unit, 3)
    context.user_data["energy_pens"] = pens
    context.user_data["energy_amount"] = amount
    order_no = create_order(update.effective_user.id, "energy", amount, "TRX", f"pens={pens}")
    context.user_data["order_no"] = order_no
    kb = ReplyKeyboardMarkup([[KeyboardButton("✅ 确认购买"), KeyboardButton("🔙 取消")]], resize_keyboard=True)
    await update.message.reply_text(f"确认租用 {pens} 笔\n金额 {amount} TRX\n订单号：{order_no}", reply_markup=kb)
    return ENERGY_PAY


async def energy_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in ["🔙 取消", "🔙 返回主菜单"]:
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "✅ 确认购买":
        amount = context.user_data["energy_amount"]
        await update.message.reply_text(
            f"请支付 {amount} TRX\n地址：\n`{PAYMENT_ADDRESS}`\n\n转账后点「我已转账」",
            reply_markup=pay_kb(), parse_mode="Markdown",
        )
        return ENERGY_PAY
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return ENERGY_PAY
    if text == "🔄 我已转账":
        pens = context.user_data.get("energy_pens", 0)
        order_no = context.user_data.get("order_no", "")
        uid = update.effective_user.id
        row = get_user(uid)
        wallet = (row or {}).get("wallet") or ""
        await notify_admins(
            context,
            f"能量订单待确认\n用户：{uid}\n订单：{order_no}\n笔数：{pens}\n"
            f"金额：{context.user_data.get('energy_amount')} TRX\n钱包：{wallet}",
        )
        if wallet:
            try:
                res = create_energy_v3(wallet, pens * 65000)
                await notify_admins(context, f"Feee 下单结果：{res}")
            except Exception as e:
                await notify_admins(context, f"Feee 下单异常：{e}")
        await update.message.reply_text(
            f"✅ 已提交。订单 {order_no}\n能量将发送至绑定冷钱包。",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END
    return ENERGY_PAY


# ----- package -----
async def package_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not require_registered(row):
        await update.message.reply_text("请先完成 Dapp 注册会员")
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("1天套餐"), KeyboardButton("3天套餐")],
        [KeyboardButton("7天套餐"), KeyboardButton("14天套餐")],
        [KeyboardButton("包月套餐"), KeyboardButton("📋 我的托管")],
        [KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        "✏️ 笔数套餐\n\n"
        "✔️ 1-3-7-14 天：5/10/20/30/50/100 笔\n"
        "✔️ 包月额外：60-90 笔\n"
        "✔️ 单价 3.6→3.2 TRX/笔\n"
        "✔️ 购买后自动托管，每日低消 3 笔\n"
        "⚠️ 购买后无法解除托管",
        reply_markup=kb,
    )
    return PKG_PLAN


async def package_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 返回主菜单":
        await update.message.reply_text("已返回", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "📋 我的托管":
        pkg = get_package(update.effective_user.id)
        if not pkg:
            await update.message.reply_text("暂无托管套餐", reply_markup=main_menu())
        else:
            await update.message.reply_text(
                f"📋 我的托管\n套餐：{pkg['plan']}\n剩余笔数：{pkg['pens_left']}\n"
                f"绑定地址：{pkg.get('bound_wallet') or '-'}\n到期：{pkg.get('expire_at')}\n"
                f"每日低消：{PACKAGE_DAILY_MIN} 笔",
                reply_markup=main_menu(),
            )
        return ConversationHandler.END
    plan_map = {
        "1天套餐": "1天", "3天套餐": "3天", "7天套餐": "7天",
        "14天套餐": "14天", "包月套餐": "包月",
    }
    if text not in plan_map:
        await update.message.reply_text("请选择套餐")
        return PKG_PLAN
    plan = plan_map[text]
    context.user_data["pkg_plan"] = plan
    options = PACKAGE_PENS_OPTIONS[plan]
    price = PACKAGE_PRICES[plan]
    buttons, row_btns = [], []
    for p in options:
        row_btns.append(KeyboardButton(f"{p}笔"))
        if len(row_btns) == 3:
            buttons.append(row_btns)
            row_btns = []
    if row_btns:
        buttons.append(row_btns)
    buttons.append([KeyboardButton("🔙 取消")])
    await update.message.reply_text(
        f"请选择笔数（{plan}套餐）\n单价：{price} TRX / 笔",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )
    return PKG_PENS


async def package_pens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if not text.endswith("笔"):
        await update.message.reply_text("请选择笔数")
        return PKG_PENS
    try:
        pens = int(text.replace("笔", ""))
    except ValueError:
        await update.message.reply_text("请选择笔数")
        return PKG_PENS
    plan = context.user_data["pkg_plan"]
    price = PACKAGE_PRICES[plan]
    total = round(pens * price, 3)
    context.user_data["pkg_pens"] = pens
    context.user_data["pkg_total"] = total
    days = {"1天": 1, "3天": 3, "7天": 7, "14天": 14, "包月": 30}[plan]
    context.user_data["pkg_days"] = days
    order_no = create_order(update.effective_user.id, "package", total, "TRX", f"{plan}:{pens}")
    context.user_data["order_no"] = order_no
    kb = ReplyKeyboardMarkup([[KeyboardButton("✅ 确认购买"), KeyboardButton("🔙 取消")]], resize_keyboard=True)
    await update.message.reply_text(
        f"📋 确认购买\n套餐：{plan}\n笔数：{pens}\n单价：{price} TRX\n总价：{total} TRX\n"
        f"有效期：{days} 天\n订单：{order_no}",
        reply_markup=kb,
    )
    return PKG_PAY


async def package_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "✅ 确认购买":
        total = context.user_data["pkg_total"]
        await update.message.reply_text(
            f"请支付 {total} TRX\n地址：\n`{PAYMENT_ADDRESS}`",
            reply_markup=pay_kb(), parse_mode="Markdown",
        )
        return PKG_PAY
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return PKG_PAY
    if text == "🔄 我已转账":
        uid = update.effective_user.id
        row = get_user(uid)
        wallet = (row or {}).get("wallet") or ""
        pens = context.user_data.get("pkg_pens", 0)
        plan = context.user_data.get("pkg_plan", "")
        days = context.user_data.get("pkg_days", 1)
        order_no = context.user_data.get("order_no", "")
        set_package(uid, plan, pens, days, wallet)
        add_pens(uid, pens)
        await notify_admins(context, f"笔数套餐待确认\n用户{uid}\n{plan} {pens}笔\n订单{order_no}")
        await update.message.reply_text(
            f"🎉 购买成功（待链上确认）\n订单：{order_no}\n已开启托管",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END
    return PKG_PAY


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    row = get_user(uid)
    if not require_registered(row):
        await update.message.reply_text("请先完成 Dapp 注册会员")
        return
    ok = do_checkin(uid, CHECKIN_FREE_PENS)
    if ok:
        await update.message.reply_text(
            f"✔️ 签到成功！已到账 {CHECKIN_FREE_PENS} 笔免费转账额度 🎁",
            reply_markup=main_menu(),
        )
    else:
        await update.message.reply_text("今日已签到 ✅\n明日 00:00 后再来", reply_markup=main_menu())


# ----- TRX swap -----
async def trx_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not require_registered(row):
        await update.message.reply_text("请先完成 Dapp 注册会员")
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("USDT兑TRX"), KeyboardButton("TRX兑USDT")],
        [KeyboardButton("📊 刷新汇率"), KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        f"💱 汇率\n1 USDT = {USDT_TO_TRX} TRX\n1 TRX ≈ {TRX_TO_USDT} USDT\n"
        f"地址：\n`{PAYMENT_ADDRESS}`",
        reply_markup=kb, parse_mode="Markdown",
    )
    return TRX_AMOUNT


async def trx_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 返回主菜单":
        await update.message.reply_text("已返回", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "📊 刷新汇率":
        await update.message.reply_text("汇率已刷新（当前为配置汇率）")
        return TRX_AMOUNT
    if text in ["USDT兑TRX", "TRX兑USDT"]:
        context.user_data["trx_direction"] = text
        await update.message.reply_text("请输入数量", reply_markup=cancel_kb())
        return TRX_CONFIRM
    return TRX_AMOUNT


async def trx_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("请输入有效数字")
        return TRX_CONFIRM
    direction = context.user_data["trx_direction"]
    if direction == "USDT兑TRX":
        receive = round(amount * USDT_TO_TRX, 3)
        unit_pay, unit_get = "USDT", "TRX"
    else:
        receive = round(amount * TRX_TO_USDT, 3)
        unit_pay, unit_get = "TRX", "USDT"
    context.user_data["trx_pay"] = amount
    context.user_data["trx_receive"] = receive
    order_no = create_order(update.effective_user.id, "swap", amount, unit_pay, f"get={receive}{unit_get}")
    context.user_data["order_no"] = order_no
    kb = ReplyKeyboardMarkup([[KeyboardButton("✅ 确认兑换"), KeyboardButton("🔙 取消")]], resize_keyboard=True)
    await update.message.reply_text(
        f"确认：{amount} {unit_pay} → {receive} {unit_get}\n订单：{order_no}",
        reply_markup=kb,
    )
    return TRX_PAY


async def trx_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "✅ 确认兑换":
        pay = context.user_data["trx_pay"]
        unit = "USDT" if context.user_data["trx_direction"] == "USDT兑TRX" else "TRX"
        await update.message.reply_text(
            f"请转账 {pay} {unit}\n地址：\n`{PAYMENT_ADDRESS}`",
            reply_markup=pay_kb(), parse_mode="Markdown",
        )
        return TRX_PAY
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return TRX_PAY
    if text == "🔄 我已转账":
        receive = context.user_data.get("trx_receive", 0)
        unit = "TRX" if context.user_data.get("trx_direction") == "USDT兑TRX" else "USDT"
        await notify_admins(
            context,
            f"闪兑待确认\n用户{update.effective_user.id}\n订单{context.user_data.get('order_no')}\n应到账 {receive} {unit}",
        )
        await update.message.reply_text(
            f"已提交，到账后发放 {receive} {unit}\n订单：{context.user_data.get('order_no')}",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END
    return TRX_PAY


# ----- fiat -----
async def fiat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("🔄 立即兑换"), KeyboardButton("📊 查看汇率")],
        [KeyboardButton("📋 出款方式"), KeyboardButton("📦 订单查询")],
        [KeyboardButton("✈️ 联系客服"), KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        f"↔️ 法币闪兑\n仅支持 USDT→法币\n手续费 {FIAT_FEE_USDT}U / 次\n最低 {FIAT_MIN_USDT}U",
        reply_markup=kb,
    )
    return FIAT_COUNTRY


async def fiat_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 返回主菜单":
        await update.message.reply_text("已返回", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "🔄 立即兑换":
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("🇨🇳 中国"), KeyboardButton("🇹🇼 台湾")],
            [KeyboardButton("🇻🇳 越南"), KeyboardButton("🔙 取消")],
        ], resize_keyboard=True)
        await update.message.reply_text("请选择法币地区", reply_markup=kb)
        return FIAT_AMOUNT
    if text == "📊 查看汇率":
        await update.message.reply_text(f"出款按实时汇率，另收手续费 {FIAT_FEE_USDT}U")
        return FIAT_COUNTRY
    if text == "📋 出款方式":
        await update.message.reply_text("中国：支付宝/微信\n台湾：银行\n越南：银行 + MoMo/ZaloPay")
        return FIAT_COUNTRY
    if text == "📦 订单查询":
        await update.message.reply_text("请联系客服并提供订单号")
        return FIAT_COUNTRY
    if text == "✈️ 联系客服":
        cs = [u for u in CS_USERNAMES if u]
        if not cs:
            await update.message.reply_text(
                "客服时间 09:00-21:00\n请联系：https://t.me/SC_TRXbot"
            )
        elif len(cs) == 1:
            u = cs[0]
            await update.message.reply_text(
                "✈️ 联系客服\n客服时间 09:00-21:00\n\n请点击联系：\nhttps://t.me/" + u
            )
        else:
            lines_cs = ["✈️ 联系客服", "客服时间 09:00-21:00", "", "请选择客服："]
            for idx, u in enumerate(cs, 1):
                lines_cs.append(f"{idx}. @{u}  https://t.me/{u}")
            await update.message.reply_text(chr(10).join(lines_cs))
        return
async def fiat_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text in ["🇨🇳 中国", "🇹🇼 台湾", "🇻🇳 越南"]:
        context.user_data["fiat_country"] = text
        await update.message.reply_text(f"请输入 USDT 数量（最低 {FIAT_MIN_USDT}）", reply_markup=cancel_kb())
        return FIAT_CONFIRM
    return FIAT_AMOUNT


async def fiat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    try:
        amount = float(text)
        if amount < FIAT_MIN_USDT:
            await update.message.reply_text(f"最低 {FIAT_MIN_USDT}U")
            return FIAT_CONFIRM
    except Exception:
        await update.message.reply_text("请输入数字")
        return FIAT_CONFIRM
    context.user_data["fiat_amount"] = amount
    order_no = create_order(update.effective_user.id, "fiat", amount, "USDT", context.user_data.get("fiat_country", ""))
    context.user_data["order_no"] = order_no
    kb = ReplyKeyboardMarkup([[KeyboardButton("✅ 确认下单"), KeyboardButton("🔙 取消")]], resize_keyboard=True)
    await update.message.reply_text(
        f"确认：{amount} USDT\n手续费：{FIAT_FEE_USDT}U\n订单：{order_no}",
        reply_markup=kb,
    )
    return FIAT_PAY


async def fiat_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "✅ 确认下单":
        amount = context.user_data["fiat_amount"]
        await update.message.reply_text(
            f"请转账 {amount} USDT\n地址：\n`{PAYMENT_ADDRESS}`",
            reply_markup=pay_kb(), parse_mode="Markdown",
        )
        return FIAT_INFO
    return FIAT_PAY


async def fiat_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in ["🔙 取消", "🔙 取消订单"]:
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return FIAT_INFO
    if text == "🔄 我已转账":
        await update.message.reply_text("请发送收款信息（姓名/账号/银行或支付宝微信）", reply_markup=cancel_kb())
        return FIAT_INFO
    await notify_admins(
        context,
        f"法币出款申请\n用户{update.effective_user.id}\n订单{context.user_data.get('order_no')}\n"
        f"金额{context.user_data.get('fiat_amount')}U\n地区{context.user_data.get('fiat_country')}\n收款信息：\n{text}",
    )
    await update.message.reply_text("✅ 信息已收到，管理员将处理出款", reply_markup=main_menu())
    return ConversationHandler.END


# ----- recharge -----
async def recharge_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not require_registered(row):
        await update.message.reply_text("请先完成 Dapp 注册会员")
        return ConversationHandler.END
    await update.message.reply_text(
        "🪙 我要充值\n请输入要充值的 USDT 数量\n（可用于笔数套餐、TRX闪兑；不可用于能量闪兑）",
        reply_markup=cancel_kb(),
    )
    return RECHARGE_AMOUNT


async def recharge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("请输入有效数量")
        return RECHARGE_AMOUNT
    context.user_data["recharge_amount"] = amount
    order_no = create_order(update.effective_user.id, "recharge", amount, "USDT")
    context.user_data["order_no"] = order_no
    await update.message.reply_text(
        f"请支付 {amount} USDT\n地址：\n`{PAYMENT_ADDRESS}`\n订单：{order_no}",
        reply_markup=pay_kb(), parse_mode="Markdown",
    )
    return RECHARGE_PAY


async def recharge_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return RECHARGE_PAY
    if text == "🔄 我已转账":
        await notify_admins(
            context,
            f"充值待确认\n用户{update.effective_user.id}\n"
            f"{context.user_data.get('recharge_amount')} USDT\n订单{context.user_data.get('order_no')}",
        )
        await update.message.reply_text("已提交，确认到账后余额到账", reply_markup=main_menu())
        return ConversationHandler.END
    return RECHARGE_PAY


# ----- member -----
async def member_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    until = (row or {}).get("member_until") or "未订阅"
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("✅ 立即订阅（88U）"), KeyboardButton("📋 我的订阅状态")],
        [KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        f"👑 会员订阅\n价格：{MEMBER_PRICE_USDT} USDT / {MEMBER_DAYS}天\n"
        f"权益：每日基础笔数、优先通道、专属客服、套餐折扣\n当前到期：{until}",
        reply_markup=kb,
    )
    return MEMBER_PAY


async def member_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 返回主菜单":
        await update.message.reply_text("已返回", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "📋 我的订阅状态":
        row = get_user(update.effective_user.id)
        await update.message.reply_text(f"到期时间：{(row or {}).get('member_until') or '未订阅'}")
        return MEMBER_PAY
    if text == "✅ 立即订阅（88U）":
        order_no = create_order(update.effective_user.id, "member", MEMBER_PRICE_USDT, "USDT")
        context.user_data["order_no"] = order_no
        await update.message.reply_text(
            f"请支付 {MEMBER_PRICE_USDT} USDT\n地址：\n`{PAYMENT_ADDRESS}`\n订单：{order_no}",
            reply_markup=pay_kb(), parse_mode="Markdown",
        )
        return MEMBER_PAY
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return MEMBER_PAY
    if text == "🔄 我已转账":
        await notify_admins(context, f"会员订阅待确认\n用户{update.effective_user.id}\n订单{context.user_data.get('order_no')}")
        await update.message.reply_text("已提交，确认后开通会员", reply_markup=main_menu())
        return ConversationHandler.END
    return MEMBER_PAY


# ----- TG goods -----
async def tg_goods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not require_registered(row):
        await update.message.reply_text("请先完成 Dapp 注册会员")
        return ConversationHandler.END
    kb = ReplyKeyboardMarkup([
        [KeyboardButton("⭐ 购买星星"), KeyboardButton("👑 购买TG会员")],
        [KeyboardButton("📞 匿名号码"), KeyboardButton("🆔 匿名帐号")],
        [KeyboardButton("🔙 返回主菜单")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        "✈️ TG 商品专区\n"
        "下单付款后，由客服人工购买并赠送到您指定的账号。\n"
        "请选择商品：",
        reply_markup=kb,
    )
    return TG_ITEM


async def tg_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 返回主菜单":
        await update.message.reply_text("已返回", reply_markup=main_menu())
        return ConversationHandler.END
    catalog = {
        "⭐ 购买星星": {"name": "Telegram星星", "unit": "U/个", "price": 0.02, "need_qty": True, "min_qty": 50, "max_qty": 10000},
        "👑 购买TG会员": {"name": "Telegram会员", "need_qty": False, "options": [
            ("3个月", 12), ("6个月", 30), ("1年", 50)
        ]},
        "📞 匿名号码": {"name": "匿名号码+888", "unit": "U", "price": 0, "need_qty": False, "custom_price": True},
        "🆔 匿名帐号": {"name": "匿名用户名", "unit": "U", "price": 0, "need_qty": False, "custom_price": True},
    }
    if text not in catalog:
        await update.message.reply_text("请选择商品")
        return TG_ITEM
    item = catalog[text]
    context.user_data["tg_item"] = item
    context.user_data["tg_item_key"] = text
    if text == "👑 购买TG会员":
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("3个月（12U）"), KeyboardButton("6个月（30U）")],
            [KeyboardButton("1年（50U）"), KeyboardButton("🔙 取消")],
        ], resize_keyboard=True)
        await update.message.reply_text("请选择会员时长", reply_markup=kb)
        return TG_QTY
    if item.get("custom_price"):
        await update.message.reply_text(
            f"{item['name']}\n价格以客服确认为准。\n请先输入您要购买的目标（用户名/号码说明）：",
            reply_markup=cancel_kb(),
        )
        context.user_data["tg_amount"] = 0
        context.user_data["tg_label"] = item["name"]
        return TG_TARGET
    # 星星
    await update.message.reply_text(
        f"⭐ 星星 0.02U/个\n支持 50～10000 个\n请输入购买数量：",
        reply_markup=cancel_kb(),
    )
    return TG_QTY


async def tg_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    key = context.user_data.get("tg_item_key")
    if key == "👑 购买TG会员":
        mapping = {"3个月（12U）": ("3个月会员", 12), "6个月（30U）": ("6个月会员", 30), "1年（50U）": ("1年会员", 50)}
        if text not in mapping:
            await update.message.reply_text("请选择时长")
            return TG_QTY
        label, amount = mapping[text]
        context.user_data["tg_label"] = label
        context.user_data["tg_amount"] = amount
        await update.message.reply_text(
            "开通给谁？\n1）发送「自己」开通到当前账号\n2）或发送对方 Telegram 用户名（如 @username）",
            reply_markup=cancel_kb(),
        )
        return TG_TARGET
    # 星星数量
    try:
        qty = int(text)
        if qty < 50 or qty > 10000:
            await update.message.reply_text("数量需在 50～10000")
            return TG_QTY
    except Exception:
        await update.message.reply_text("请输入数字数量")
        return TG_QTY
    amount = round(qty * 0.02, 2)
    context.user_data["tg_label"] = f"星星 x{qty}"
    context.user_data["tg_amount"] = amount
    context.user_data["tg_qty"] = qty
    await update.message.reply_text(
        "赠送给谁？\n1）发送「自己」\n2）或发送对方 @用户名",
        reply_markup=cancel_kb(),
    )
    return TG_TARGET


async def tg_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    target = text.strip()
    if target in ("自己", "本人", "me", "Me"):
        u = update.effective_user
        target = f"@{u.username}" if u.username else f"tg_id:{u.id}"
    context.user_data["tg_target"] = target
    # custom price items: ask amount
    if context.user_data.get("tg_amount") == 0:
        await update.message.reply_text(
            "请输入本单支付 USDT 金额（与客服确认后的价格）：",
            reply_markup=cancel_kb(),
        )
        context.user_data["tg_need_price"] = True
        return TG_TARGET
    if context.user_data.get("tg_need_price"):
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError()
            context.user_data["tg_amount"] = amount
            context.user_data["tg_need_price"] = False
            # target already set previous step - if we just got price, keep target
        except Exception:
            # might still be target for custom - already stored
            try:
                amount = float(text)
                context.user_data["tg_amount"] = amount
                context.user_data["tg_need_price"] = False
            except Exception:
                await update.message.reply_text("请输入有效金额")
                return TG_TARGET
    amount = context.user_data.get("tg_amount") or 0
    label = context.user_data.get("tg_label") or "TG商品"
    target = context.user_data.get("tg_target") or ""
    order_no = create_order(
        update.effective_user.id, "tg_goods", amount, "USDT",
        f"{label}|to={target}",
    )
    context.user_data["order_no"] = order_no
    kb = ReplyKeyboardMarkup([[KeyboardButton("✅ 确认下单"), KeyboardButton("🔙 取消")]], resize_keyboard=True)
    await update.message.reply_text(
        f"📋 确认订单\n商品：{label}\n赠送目标：{target}\n金额：{amount} USDT\n订单：{order_no}\n\n"
        f"付款后客服将人工购买并赠送。",
        reply_markup=kb,
    )
    return TG_PAY


async def tg_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 取消":
        await update.message.reply_text("已取消", reply_markup=main_menu())
        return ConversationHandler.END
    if text == "✅ 确认下单":
        amount = context.user_data.get("tg_amount") or 0
        await update.message.reply_text(
            f"请支付 {amount} USDT\n地址：\n`{PAYMENT_ADDRESS}`",
            reply_markup=pay_kb(), parse_mode="Markdown",
        )
        return TG_PAY
    if text == "📋 复制地址":
        await update.message.reply_text(f"`{PAYMENT_ADDRESS}`", parse_mode="Markdown")
        return TG_PAY
    if text == "🔄 我已转账":
        uid = update.effective_user.id
        u = update.effective_user
        order_no = context.user_data.get("order_no", "")
        label = context.user_data.get("tg_label", "")
        target = context.user_data.get("tg_target", "")
        amount = context.user_data.get("tg_amount", 0)
        msg = (
            f"📦 TG商品订单（待人工处理）\n"
            f"订单号：{order_no}\n"
            f"用户：{uid} @{u.username or '-'}\n"
            f"商品：{label}\n"
            f"赠送目标：{target}\n"
            f"金额：{amount} USDT\n"
            f"请确认到账后人工购买并赠送客户。"
        )
        await notify_admins(context, msg)
        # 也通知客服用户名（若能解析则私聊不了，只能管理员）
        await update.message.reply_text(
            f"✅ 订单已提交\n订单号：{order_no}\n客服确认收款后会为您人工开通/赠送。\n"
            f"可点 ✈️ 联系客服 查询进度。",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END
    return TG_PAY


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.full_name or "")
    row = get_user(user.id)

    if text == "🌐 立即开通 DApp 专属会员":
        await update.message.reply_text(
            "请打开链接连接冷钱包完成注册：\n"
            f"{register_link(user.id)}\n\n"
            "注册成功后回到机器人点 /start\n\n"
            "⚠️ 务必使用 Safari / Chrome打开，右上角 ··· →「在浏览器中打开」"
        )
        return

    if text == "✈️ 联系客服":
        cs = [u for u in CS_USERNAMES if u]
        if not cs:
            await update.message.reply_text(
                "客服时间 09:00-21:00\n请联系：https://t.me/SC_TRXbot"
            )
        elif len(cs) == 1:
            u = cs[0]
            await update.message.reply_text(
                "✈️ 联系客服\n客服时间 09:00-21:00\n\n请点击联系：\nhttps://t.me/" + u
            )
        else:
            lines_cs = ["✈️ 联系客服", "客服时间 09:00-21:00", "", "请选择客服："]
            for idx, u in enumerate(cs, 1):
                lines_cs.append(f"{idx}. @{u}  https://t.me/{u}")
            await update.message.reply_text(chr(10).join(lines_cs))
        return
    if text == "⭕️ 个人中心":
        if not require_registered(row):
            await update.message.reply_text("请先注册")
            return
        await update.message.reply_text(
            f"⭕️ 个人中心\nUID：{user.id}\n等级：{row.get('level')}\n"
            f"笔数：{row.get('pens')}\nUSDT：{row.get('balance_usdt')}\nTRX：{row.get('balance_trx')}",
            reply_markup=personal_menu(),
        )
        return

    if text == "💼 代理中心":
        if not require_registered(row):
            await update.message.reply_text("请先注册")
            return
        rate = int(get_rebate_rate(row.get("level") or "普通会员") * 100)
        await update.message.reply_text(
            f"💼 代理中心\n等级：{row.get('level')}\n有效邀请：{row.get('valid_invites')}\n返利比例：{rate}%",
            reply_markup=agent_menu(),
        )
        return

    if text == "🔙 返回主菜单":
        await update.message.reply_text("请选择服务：", reply_markup=main_menu())
        return

    if text == "👤 基本资料":
        await update.message.reply_text(
            f"UID：{user.id}\n用户名：@{user.username or '-'}\n钱包：{(row or {}).get('wallet') or '-'}",
            reply_markup=personal_menu(),
        )
        return

    if text == "💰 我的资产":
        await update.message.reply_text(
            f"USDT：{(row or {}).get('balance_usdt', 0)}\n"
            f"TRX：{(row or {}).get('balance_trx', 0)}\n"
            f"笔数：{(row or {}).get('pens', 0)}",
            reply_markup=personal_menu(),
        )
        return

    if text == "⚡ 能量额度":
        pkg = get_package(user.id)
        extra = ""
        if pkg:
            extra = f"\n托管剩余：{pkg.get('pens_left')} 笔（{pkg.get('plan')}）"
        await update.message.reply_text(
            f"当前笔数：{(row or {}).get('pens', 0)}{extra}",
            reply_markup=personal_menu(),
        )
        return

    if text == "🔗 邀请链接":
        me = await context.bot.get_me()
        await update.message.reply_text(
            f"专属邀请链接：\nhttps://t.me/{me.username}?start=ref{user.id}\n"
            f"好友需经此链接注册才算有效邀请",
            reply_markup=agent_menu(),
        )
        return

    if text == "🏆 会员等级":
        cur = (row or {}).get("level") or "普通会员"
        invites = (row or {}).get("valid_invites") or 0
        await update.message.reply_text(
            f"当前：{cur}（有效邀请 {invites} 人）\n\n"
            "普通会员：返利5%\n"
            "铜牌（5人）：返利8% + 赠送88U\n"
            "银牌（10人）：返利12% + TG会员 + 188U\n"
            "金牌（15人）：返利15% + TG会员 + ⭐ + 388U\n"
            "钻石（30人）：返利15% + TG会员 + ⭐ + 588U",
            reply_markup=agent_menu() if text else personal_menu(),
        )
        return

    if text == "👥 邀请记录":
        rows = list_invitees(user.id)
        if not rows:
            await update.message.reply_text("暂无邀请记录", reply_markup=agent_menu())
        else:
            lines = [f"👥 邀请记录（{len(rows)}）"]
            for r in rows:
                mark = "✅" if r.get("is_registered") else "⏳"
                name = r.get("username") or r.get("full_name") or str(r.get("tg_id"))
                lines.append(f"{mark} {name}  {(r.get('created_at') or '')[:10]}")
            await update.message.reply_text("\n".join(lines), reply_markup=agent_menu())
        return

    if text == "💰 返利明细":
        total = total_rebate(user.id)
        bal = (row or {}).get("balance_usdt") or 0
        rows = list_rebates(user.id)
        lines = [f"💰 返利明细\n累计返利：{total:.2f} U\n可提现：{bal:.2f} U"]
        if rows:
            lines.append("")
            for r in rows[:10]:
                lines.append(
                    f"+{r['amount']:.2f}U  {int((r.get('rate') or 0)*100)}%  {(r.get('created_at') or '')[:10]}"
                )
        else:
            lines.append("暂无返利记录")
        await update.message.reply_text("\n".join(lines), reply_markup=agent_menu())
        return

    if text == "💸 申请提现":
        bal = float((row or {}).get("balance_usdt") or 0)
        if bal < 10:
            await update.message.reply_text(
                f"可提现 {bal:.2f} U\n最低提现 10 USDT",
                reply_markup=agent_menu(),
            )
            return
        order_no = create_withdraw(user.id, bal)
        await notify_admins(
            context,
            f"返利提现申请\n用户 {user.id} @{user.username or '-'}\n"
            f"金额 {bal:.2f} U\n订单 {order_no}\n钱包 {(row or {}).get('wallet')}",
        )
        await update.message.reply_text(
            f"已提交提现申请 {bal:.2f} U\n订单号：{order_no}\n管理员审核后打款",
            reply_markup=agent_menu(),
        )
        return

    if text == "📋 提现记录":
        rows = list_withdraws(user.id)
        if not rows:
            await update.message.reply_text("暂无提现记录", reply_markup=agent_menu())
        else:
            lines = ["📋 提现记录"]
            for r in rows:
                lines.append(
                    f"{r['order_no']}  {r['amount']}U  {r['status']}  {(r.get('created_at') or '')[:16]}"
                )
            await update.message.reply_text("\n".join(lines), reply_markup=agent_menu())
        return

    if text == "📋 我的订单":
        rows = list_orders(user.id)
        if not rows:
            await update.message.reply_text("暂无订单", reply_markup=personal_menu())
        else:
            lines = ["📋 我的订单（最近10笔）"]
            for r in rows:
                lines.append(
                    f"{r['order_no']} | {r['order_type']} | {r['amount']} {r['currency']} | {r['status']}"
                )
            await update.message.reply_text("\n".join(lines), reply_markup=personal_menu())
        return

    if text == "⚙️ 账号设置":
        w = (row or {}).get("wallet") or "未绑定"
        st = "已注册" if (row or {}).get("is_registered") else "未注册"
        await update.message.reply_text(
            f"⚙️ 账号设置\nUID：{user.id}\n钱包：{w}\n注册状态：{st}\n\n"
            f"重新绑定：\n{register_link(user.id)}\n\n"
            f"⚠️ 打开后点右上角 ··· →「在浏览器中打开」\n"
            f"使用 Safari / Chrome，勿用 Telegram 内置浏览器。",
            reply_markup=personal_menu(),
        )
        return

    # TG 商品细节由 ConversationHandler 处理

    await update.message.reply_text("请点击按钮选择服务", reply_markup=main_menu())


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("用法：/bind <tg_id> <wallet>")
        return
    try:
        tg_id = int(context.args[0])
        wallet = context.args[1].strip()
    except Exception:
        await update.message.reply_text("参数错误")
        return
    upsert_user(tg_id)
    set_registered(tg_id, wallet)
    u = get_user(tg_id)
    if u and u.get("inviter_id"):
        level, invites = add_valid_invite(u["inviter_id"])
        await notify_admins(context, f"邀请成功：{u['inviter_id']} 当前{invites}人，等级{level}")
    await update.message.reply_text(f"已绑定 {tg_id} → {wallet}")
    try:
        await context.bot.send_message(tg_id, f"✅ 钱包绑定成功：{wallet}\n请发送 /start 进入主菜单")
    except Exception:
        pass



async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理员或任意用户发图时回传 file_id，方便绑定宣传图"""
    if not update.message or not update.message.photo:
        return
    photo = update.message.photo[-1]  # 最大尺寸
    fid = photo.file_id
    await update.message.reply_text(
        f"✅ 已收到图片\nfile_id（复制下面整行）：\n`{fid}`\n\n"
        f"尺寸约：{photo.width}x{photo.height}",
        parse_mode="Markdown",
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text(
        "管理员命令：\n/bind <tg_id> <wallet> — 手动绑定会员\n/start — 测试菜单"
    )


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    energy_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚡️ 能量闪租$"), energy_start)],
        states={
            ENERGY_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, energy_confirm)],
            ENERGY_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, energy_pay)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    pkg_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✏️ 笔数套餐$"), package_start)],
        states={
            PKG_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, package_plan)],
            PKG_PENS: [MessageHandler(filters.TEXT & ~filters.COMMAND, package_pens)],
            PKG_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, package_pay)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    trx_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 TRX 闪兑$"), trx_start)],
        states={
            TRX_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, trx_amount)],
            TRX_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, trx_confirm)],
            TRX_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, trx_pay)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    fiat_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^↔️ 法币闪兑$"), fiat_start)],
        states={
            FIAT_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, fiat_country)],
            FIAT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, fiat_amount)],
            FIAT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, fiat_confirm)],
            FIAT_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, fiat_pay)],
            FIAT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fiat_info)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    recharge_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🪙 我要充值$"), recharge_start)],
        states={
            RECHARGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recharge_amount)],
            RECHARGE_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, recharge_pay)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    member_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👑 会员订阅$"), member_start)],
        states={MEMBER_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, member_pay)]},
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(energy_conv)
    app.add_handler(pkg_conv)
    app.add_handler(trx_conv)
    app.add_handler(fiat_conv)
    app.add_handler(recharge_conv)
    tg_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✈️ TG 商品$"), tg_goods)],
        states={
            TG_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_item)],
            TG_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_qty)],
            TG_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_target)],
            TG_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_pay)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u, c: ConversationHandler.END)],
        allow_reentry=True,
    )
    app.add_handler(member_conv)
    app.add_handler(tg_conv)
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Regex("^🗓 每日签到$"), checkin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("TRONIFY 机器人已启动...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
