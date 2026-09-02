/* TRONIFY dual-framework handoff
 * A) 新註冊會員 register
 * B) 已註冊會員切換錢包 switch
 * TG in-app → Continue in wallet → official login/sign → poll landing → bot
 */
(function () {
  if (window.__TRONIFY_OFFICIAL_HANDOFF) return;
  window.__TRONIFY_OFFICIAL_HANDOFF = true;

  var ORIGIN = location.origin || "https://nobbll.pythonanywhere.com";
  var CALLBACK = ORIGIN + "/api/deeplink/callback";
  var ICON = ORIGIN + "/favicon.ico";
  var STATUS_API = ORIGIN + "/api/user_status";
  var PENDING_API = ORIGIN + "/api/pending_sign";
  var BIND_API = ORIGIN + "/api/bind";
  var NONCE_API = ORIGIN + "/api/auth/nonce";
  var CHAIN = "0x2b6653dc";
  var BOT = "SC_TRX_BOXbot";
  var lastPhase = "";
  var pollTimer = null;
  var knownBoundAddr = "";

  function ls(k, v) {
    try {
      if (arguments.length === 1) return localStorage.getItem(k) || "";
      if (v === null) localStorage.removeItem(k);
      else localStorage.setItem(k, String(v));
    } catch (e) { return ""; }
  }
  function ss(k, v) {
    try {
      if (arguments.length === 1) return sessionStorage.getItem(k) || "";
      if (v === null) sessionStorage.removeItem(k);
      else sessionStorage.setItem(k, String(v));
    } catch (e) { return ""; }
  }
  function qs(name) {
    try { return new URLSearchParams(location.search).get(name) || ""; } catch (e) { return ""; }
  }
  function tgId() {
    try { if (typeof TG_ID !== "undefined" && TG_ID) return String(TG_ID); } catch (e) {}
    return qs("tg_id") || ls("tronify_tg_id") || "";
  }
  function uuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
  function isTronAddr(a) {
    return typeof a === "string" && /^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(a);
  }
  function shortAddr(a) {
    if (!isTronAddr(a)) return "";
    return a.slice(0, 6) + "\u2026" + a.slice(-4);
  }
  function isTgBrowser() {
    var ua = navigator.userAgent || "";
    if (/TronLink|TokenPocket|imToken/i.test(ua)) return false;
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) return true;
    return /Telegram/i.test(ua);
  }
  function inAnyWallet() {
    var ua = navigator.userAgent || "";
    if (/TronLink|TokenPocket|imToken/i.test(ua)) return true;
    try {
      if (window.tronLink || (window.tron && window.tron.isTronLink)) return true;
      if (window.tokenpocket || window.imToken) return true;
    } catch (e) {}
    return false;
  }
  function pickedWallet() {
    return (qs("wallet") || ss("tronify_user_picked_wallet") || ls("tronify_wallet") || "tronlink").toLowerCase();
  }
  function walletName(id) {
    if (id === "imtoken") return "imToken";
    if (id === "tokenpocket") return "TokenPocket";
    return "TronLink";
  }

  function rawIntent() {
    return (qs("intent") || ss("tronify_intent") || ls("tronify_intent") || "").toLowerCase();
  }
  function isSwitching() {
    return ss("tronify_rebind") === "1" || ls("tronify_rebind") === "1" || rawIntent() === "switch";
  }
  function currentIntent() {
    if (isSwitching()) return "switch";
    var i = rawIntent();
    if (i === "register" || i === "switch") return i;
    if (ls("tronify_bound") === "1" || ls("tronify_registered") === "1") return "switch";
    return "register";
  }
  function setIntent(intent) {
    intent = intent === "switch" ? "switch" : "register";
    ss("tronify_intent", intent);
    ls("tronify_intent", intent);
    if (intent === "switch") {
      ss("tronify_rebind", "1");
      ls("tronify_rebind", "1");
    } else {
      ss("tronify_rebind", null);
      ls("tronify_rebind", null);
    }
    return intent;
  }
  function beginRegister() {
    setIntent("register");
    ss("tronify_handoff", "1");
    ls("tronify_handoff", "1");
    try { if (typeof bindingDone !== "undefined") bindingDone = false; } catch (e) {}
    openWalletPicker();
  }
  function beginSwitch() {
    setIntent("switch");
    ss("tronify_handoff", "1");
    ls("tronify_handoff", "1");
    ls("tronify_bound", null);
    try { if (typeof bindingDone !== "undefined") bindingDone = false; } catch (e) {}
    try { if (typeof window.tronifyStartRebind === "function") window.tronifyStartRebind(); } catch (e2) {}
    hideOv("ovSwitch");
    openWalletPicker();
  }

  function dappUrl(wallet, intent) {
    var u = new URL(ORIGIN + "/");
    u.searchParams.set("from", "bot");
    u.searchParams.set("wallet", wallet || "tronlink");
    u.searchParams.set("intent", intent || currentIntent());
    u.searchParams.set("step", "auth");
    var tg = tgId();
    if (tg) u.searchParams.set("tg_id", tg);
    return u.toString();
  }
  function fireHref(href) {
    try {
      var a = document.createElement("a");
      a.href = href;
      a.rel = "noreferrer";
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { try { document.body.removeChild(a); } catch (e) {} }, 80);
    } catch (e) {}
    setTimeout(function () { try { location.href = href; } catch (e2) {} }, 250);
  }
  function officialTronLinkParam(extra) {
    var base = {
      url: extra.url || dappUrl("tronlink"),
      callbackUrl: CALLBACK,
      dappIcon: ICON,
      dappName: "TRONIFY",
      protocol: "TronLink",
      version: "1.0",
      chainId: CHAIN,
      action: extra.action || "open",
      actionId: extra.actionId || uuid()
    };
    for (var k in extra) if (Object.prototype.hasOwnProperty.call(extra, k)) base[k] = extra[k];
    return "tronlinkoutside://pull.activity?param=" + encodeURIComponent(JSON.stringify(base));
  }
  function persist(wallet) {
    try {
      ss("tronify_user_picked_wallet", wallet);
      ss("tronify_wallet", wallet);
      ss("tronify_allow_leave", "1");
      ls("tronify_wallet", wallet);
      ls("tronify_picked_wallet", wallet);
      ls("tronify_tg_id", tgId());
      ls("tronify_handoff", "1");
      if (typeof pendingWalletId !== "undefined") pendingWalletId = wallet;
    } catch (e) {}
  }

  function showOv(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.add("show");
    if (id === "ovContinue") {
      el.style.cssText = "display:flex!important;visibility:visible!important;pointer-events:auto!important;z-index:2147483646!important;";
    } else {
      el.style.display = "flex";
    }
  }
  function hideOv(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.remove("show");
    el.style.display = "none";
  }
  function openWalletPicker() {
    hideOv("ovSwitch");
    hideOv("ovSuccess");
    showOv("ovWallet");
  }
  function setContinueText(title, hint, sub) {
    var t = document.getElementById("continueTitle");
    var h = document.getElementById("continueHint");
    var s = document.getElementById("continueSub");
    if (t && title) t.textContent = title;
    if (h && hint) h.textContent = hint;
    if (s && sub) s.textContent = sub;
    showOv("ovContinue");
  }
  function toast(msg) {
    if (typeof showToast === "function") showToast(msg);
  }

  function applyHeader(address, registered) {
    var btn = document.getElementById("topConnect");
    if (!btn) return;
    if (isTronAddr(address)) {
      btn.textContent = shortAddr(address);
      btn.dataset.bound = registered ? "1" : "0";
    } else {
      btn.textContent = "\u9023\u63a5\u9322\u5305";
      btn.dataset.bound = "0";
    }
  }
  function showSwitchSheet(address) {
    var el = document.getElementById("switchAddr");
    if (el) el.textContent = address || "";
    hideOv("ovWallet");
    hideOv("ovContinue");
    showOv("ovSwitch");
  }

  function openFromTelegram(wallet) {
    wallet = wallet || pickedWallet() || "tronlink";
    persist(wallet);
    startSync();
    var intent = currentIntent();
    var url = dappUrl(wallet, intent);
    var name = walletName(wallet);
    var sub = intent === "switch"
      ? "\u5207\u63db\u9322\u5305\uff1a\u5230 App \u6388\u6b0a\u4e26\u7c3d\u540d\uff0c\u5169\u908a\u9801\u9762\u6703\u540c\u6b65"
      : "\u65b0\u8a3b\u518a\uff1a\u5230 App \u6388\u6b0a\u4e26\u7c3d\u540d\uff0c\u5169\u908a\u9801\u9762\u6703\u540c\u6b65";
    setContinueText(name, "Continue in " + name, sub);
    toast("\u6b63\u5728\u6253\u958b\u9322\u5305\u2026");
    if (wallet === "imtoken") {
      fireHref("imtokenv2://navigate/DappView?url=" + encodeURIComponent(url));
      return;
    }
    if (wallet === "tokenpocket") {
      fireHref("tpdapp://open?params=" + encodeURIComponent(JSON.stringify({
        url: url, chain: "TRON", source: "TRONIFY"
      })));
      return;
    }
    fireHref(officialTronLinkParam({ url: url, action: "open" }));
  }

  function getInjectedTronWeb() {
    try { if (window.tron && window.tron.tronWeb) return window.tron.tronWeb; } catch (e) {}
    try { if (window.tronWeb && window.tronWeb.defaultAddress) return window.tronWeb; } catch (e2) {}
    try { if (window.tronLink && window.tronLink.tronWeb) return window.tronLink.tronWeb; } catch (e3) {}
    return null;
  }
  function readAddr(tw) {
    try {
      var a = tw && tw.defaultAddress && (tw.defaultAddress.base58 || tw.defaultAddress);
      if (isTronAddr(a)) return a;
    } catch (e) {}
    return "";
  }
  async function requestAddress() {
    try {
      var provider = window.tron || window.tronLink;
      if (provider && provider.request) {
        await provider.request({ method: "eth_requestAccounts" }).catch(function () {
          return provider.request({ method: "tron_requestAccounts" });
        });
      }
    } catch (e) {}
    return readAddr(getInjectedTronWeb());
  }
  async function pushPending(address, wallet) {
    var tg = tgId();
    if (!tg || !address) return;
    try {
      await fetch(PENDING_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tg_id: tg, telegram_id: tg, address: address,
          wallet: wallet || pickedWallet(),
          intent: currentIntent()
        })
      });
    } catch (e) {}
  }
  async function officialSignAndBind(address) {
    var intent = currentIntent();
    var msg = "TRONIFY Service Authorization\nAddress: " + address;
    var nonce = "";
    if (typeof window.buildSignMessage === "function") {
      try {
        var built = await window.buildSignMessage(address);
        if (typeof built === "string" && built) msg = built;
        else if (built && built.message) {
          msg = built.message;
          nonce = built.nonce || "";
        }
      } catch (e) {}
    } else {
      try {
        var r = await fetch(NONCE_API + "?tg_id=" + encodeURIComponent(tgId() || "0") + "&address=" + encodeURIComponent(address), { cache: "no-store" });
        var j = await r.json();
        if (j && j.ok && j.message) {
          msg = j.message;
          nonce = j.nonce || "";
        }
      } catch (e2) {}
    }
    var tw = getInjectedTronWeb();
    if (!tw || !tw.trx || !tw.trx.signMessageV2) throw new Error("wallet missing signMessageV2");
    var sig = await tw.trx.signMessageV2(msg);
    if (!sig) throw new Error("user cancelled");
    var payload = {
      address: address, signature: sig, message: msg, nonce: nonce,
      tg_id: tgId(), telegram_id: tgId(), intent: intent
    };
    if (typeof submitBinding === "function") await submitBinding(payload);
    else {
      var res = await fetch((window.CONFIG && CONFIG.bindApi) || BIND_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      var body = await res.json().catch(function () { return {}; });
      if (!res.ok || body.ok === false) throw new Error(body.message || "bind failed");
    }
    return address;
  }

  function markBound(address, intent) {
    intent = intent || currentIntent();
    ls("tronify_addr", address);
    ls("tronify_bound", "1");
    ls("tronify_registered", "1");
    ss("tronify_rebind", null);
    ls("tronify_rebind", null);
    knownBoundAddr = address;
    applyHeader(address, true);
    hideOv("ovContinue"); hideOv("ovWallet"); hideOv("ovSwitch");
    var title = document.querySelector("#ovSuccess .sheet-title, #ovSuccess .step-title");
    var sub = document.querySelector("#ovSuccess .step-sub, #ovSuccess .sub");
    if (title) title.textContent = intent === "switch" ? "\u9322\u5305\u5df2\u5207\u63db" : "\u8a3b\u518a\u6210\u529f";
    if (sub) sub.textContent = intent === "switch" ? "\u6703\u54e1\u5e33\u865f\u5df2\u6539\u7d81\u65b0\u5730\u5740" : "\u9322\u5305\u5df2\u8207\u6703\u54e1\u5e33\u865f\u9023\u7d50";
    var addrEl = document.getElementById("successAddr");
    if (addrEl) addrEl.textContent = address;
    var back = document.getElementById("btnBackTg");
    if (back) {
      var start = (intent === "switch" ? "switch_" : "bind_") + address;
      back.href = "https://t.me/" + BOT + "?start=" + encodeURIComponent(start);
    }
    showOv("ovSuccess");
  }

  function jumpBot(address) {
    if (ss("tronify_jumped_bot") === "1") return;
    ss("tronify_jumped_bot", "1");
    var intent = currentIntent();
    var start = encodeURIComponent((intent === "switch" ? "switch_" : "bind_") + (address || "ok"));
    toast("returning to bot");
    if (typeof goBackToBot === "function") {
      setTimeout(function () { goBackToBot(address); }, 400);
      return;
    }
    try { location.href = "tg://resolve?domain=" + BOT + "&start=" + start; } catch (e) {}
    setTimeout(function () { location.href = "https://t.me/" + BOT + "?start=" + start; }, 700);
  }

  async function pullStatus() {
    var tg = tgId();
    if (!tg) return;
    var st = null, pending = null;
    try {
      var r1 = await fetch(STATUS_API + "?tg_id=" + encodeURIComponent(tg) + "&_=" + Date.now(), { cache: "no-store" });
      st = await r1.json();
    } catch (e) {}
    try {
      var r2 = await fetch(PENDING_API + "?tg_id=" + encodeURIComponent(tg) + "&_=" + Date.now(), { cache: "no-store" });
      var j2 = await r2.json();
      pending = j2 && j2.pending;
    } catch (e2) {}
    var addr = (st && (st.wallet || st.address)) || "";
    var registered = !!(st && st.registered && isTronAddr(addr));
    var pendingAddr = pending && pending.address;
    var switching = isSwitching();
    if (registered && !switching) {
      ls("tronify_registered", "1");
      ls("tronify_addr", addr);
      knownBoundAddr = addr;
      applyHeader(addr, true);
    }
    var phase = (registered && !switching) ? "bound" : (pendingAddr ? "authorized" : "idle");
    if (phase === lastPhase && addr === ls("tronify_sync_addr")) return;
    lastPhase = phase;
    ls("tronify_sync_addr", addr || "");
    if (phase === "authorized" && pendingAddr) {
      applyHeader(pendingAddr, false);
      setContinueText(walletName(pickedWallet()), "authorized, waiting sign", shortAddr(pendingAddr));
    }
    if (phase === "bound" && isTronAddr(addr)) {
      var handoff = ls("tronify_handoff") === "1" || ss("tronify_handoff") === "1" || /step=auth/.test(location.search);
      if (handoff) {
        markBound(addr, currentIntent());
        jumpBot(addr);
      }
    }
  }
  function startSync() {
    if (pollTimer) return;
    pullStatus();
    pollTimer = setInterval(pullStatus, 1200);
  }

  window.tronifyRunOfficialWalletSession = async function () {
    if (window.__tronifyOfficialSessionOnce) return;
    if (!inAnyWallet()) return;
    window.__tronifyOfficialSessionOnce = true;
    startSync();
    try {
      var addr = await requestAddress();
      if (!addr) { window.__tronifyOfficialSessionOnce = false; return; }
      ls("tronify_addr", addr);
      applyHeader(addr, false);
      await pushPending(addr, pickedWallet());
      await officialSignAndBind(addr);
      markBound(addr, currentIntent());
      await pullStatus();
      jumpBot(addr);
    } catch (e) {
      window.__tronifyOfficialSessionOnce = false;
      toast((e && e.message) || "auth/sign incomplete");
    }
  };
  window.tronifyBeginRegister = beginRegister;
  window.tronifyBeginSwitch = beginSwitch;
  window.tronifyCurrentIntent = currentIntent;

  function onTopConnect(ev) {
    var registered = ls("tronify_registered") === "1" || ls("tronify_bound") === "1";
    var addr = ls("tronify_addr") || knownBoundAddr;
    if (registered && isTronAddr(addr) && !isSwitching()) {
      if (ev) { ev.preventDefault(); ev.stopPropagation(); }
      showSwitchSheet(addr);
      return true;
    }
    if (ev) { ev.preventDefault(); ev.stopPropagation(); }
    beginRegister();
    return true;
  }
  function wire() {
    var top = document.getElementById("topConnect");
    if (top && top.dataset.dual !== "1") {
      top.dataset.dual = "1";
      top.addEventListener("click", onTopConnect, true);
    }
    var yes = document.getElementById("switchYes");
    if (yes && yes.dataset.dual !== "1") {
      yes.dataset.dual = "1";
      yes.addEventListener("click", function (ev) {
        ev.preventDefault(); ev.stopPropagation(); beginSwitch();
      }, true);
    }
    var no = document.getElementById("switchNo");
    if (no && no.dataset.dual !== "1") {
      no.dataset.dual = "1";
      no.addEventListener("click", function (ev) { ev.preventDefault(); hideOv("ovSwitch"); }, true);
    }
    var openBtn = document.getElementById("btnOpenWallet");
    if (openBtn && openBtn.dataset.official !== "1") {
      openBtn.dataset.official = "1";
      openBtn.addEventListener("click", function (ev) {
        if (inAnyWallet()) {
          window.__tronifyOfficialSessionOnce = false;
          window.tronifyRunOfficialWalletSession();
          return;
        }
        ev.preventDefault(); ev.stopPropagation();
        openFromTelegram(pickedWallet());
      }, true);
    }
  }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    pullStatus();
    if (inAnyWallet()) window.tronifyRunOfficialWalletSession();
  });
  function boot() {
    var tg = tgId();
    if (tg) ls("tronify_tg_id", tg);
    var qi = qs("intent");
    if (qi === "switch" || qi === "register") setIntent(qi);
    wire();
    if (tg) startSync();
    if (inAnyWallet() && (qs("step") === "auth" || ls("tronify_handoff") === "1")) {
      setTimeout(function () { window.tronifyRunOfficialWalletSession(); }, 400);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  setInterval(wire, 1500);
})();
