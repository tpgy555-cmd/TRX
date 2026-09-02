/* TRONIFY wallet auth — one path, two intents: register | switch
 * intent === "switch" means already-registered member changing wallet.
 * TG Continue sheet → official wallet open → login + signMessageV2 → /api/bind → sync landing → bot
 * Landing UI is not restyled. Legacy wallet engines are disabled.
 */
(function () {
  if (window.__TRONIFY_OFFICIAL_HANDOFF) return;
  window.__TRONIFY_OFFICIAL_HANDOFF = true;

  var O = location.origin || "https://nobbll.pythonanywhere.com";
  var BOT = "SC_TRX_BOXbot";
  var poll = null, last = "", boundAddr = "";

  function store(api, k, v) {
    try {
      if (v === undefined) return api.getItem(k) || "";
      if (v === null) api.removeItem(k); else api.setItem(k, String(v));
    } catch (e) { return ""; }
  }
  function ls(k, v) { return store(localStorage, k, v); }
  function ss(k, v) { return store(sessionStorage, k, v); }
  function qs(k) { try { return new URLSearchParams(location.search).get(k) || ""; } catch (e) { return ""; } }
  function tg() {
    try { if (typeof TG_ID !== "undefined" && TG_ID) return String(TG_ID); } catch (e) {}
    return qs("tg_id") || ls("tronify_tg_id") || "";
  }
  function isAddr(a) { return typeof a === "string" && /^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(a); }
  function short(a) { return isAddr(a) ? a.slice(0, 6) + "\u2026" + a.slice(-4) : ""; }
  function inWallet() {
    var ua = navigator.userAgent || "";
    if (/TronLink|TokenPocket|imToken/i.test(ua)) return true;
    try { return !!(window.tronLink || window.tron || window.tokenpocket || window.imToken); } catch (e) { return false; }
  }
  function wallet() {
    return (qs("wallet") || ss("tronify_user_picked_wallet") || ls("tronify_wallet") || "tronlink").toLowerCase();
  }
  function wname(id) {
    return id === "imtoken" ? "imToken" : id === "tokenpocket" ? "TokenPocket" : "TronLink";
  }
  function switching() {
    return ss("tronify_rebind") === "1" || ls("tronify_rebind") === "1" || intent() === "switch";
  }
  function intent() {
    var i = (qs("intent") || ss("tronify_intent") || ls("tronify_intent") || "").toLowerCase();
    if (ss("tronify_rebind") === "1" || ls("tronify_rebind") === "1") return "switch";
    if (i === "switch" || i === "register") return i;
    return (ls("tronify_registered") === "1" || ls("tronify_bound") === "1") ? "switch" : "register";
  }
  function setIntent(i) {
    i = i === "switch" ? "switch" : "register";
    ss("tronify_intent", i); ls("tronify_intent", i);
    ss("tronify_rebind", i === "switch" ? "1" : null);
    ls("tronify_rebind", i === "switch" ? "1" : null);
    return i;
  }
  function dappUrl(w, i) {
    var u = new URL(O + "/");
    u.searchParams.set("from", "bot");
    u.searchParams.set("wallet", w || "tronlink");
    u.searchParams.set("intent", i || intent());
    u.searchParams.set("step", "auth");
    if (tg()) u.searchParams.set("tg_id", tg());
    return u.toString();
  }
  function go(href) {
    var a = document.createElement("a");
    a.href = href; a.style.display = "none";
    document.body.appendChild(a); a.click();
    setTimeout(function () { try { document.body.removeChild(a); } catch (e) {} }, 60);
    setTimeout(function () { try { location.href = href; } catch (e2) {} }, 220);
  }
  function show(id) {
    var el = document.getElementById(id); if (!el) return;
    el.classList.add("show");
    el.style.display = "flex";
    if (id === "ovContinue") {
      el.style.cssText = "display:flex!important;visibility:visible!important;pointer-events:auto!important;z-index:2147483646!important;";
    }
  }
  function hide(id) {
    var el = document.getElementById(id); if (!el) return;
    el.classList.remove("show"); el.style.display = "none";
  }
  function toast(m) { if (typeof showToast === "function") showToast(m); }
  function header(addr) {
    var btn = document.getElementById("topConnect");
    if (btn) btn.textContent = isAddr(addr) ? short(addr) : "\u9023\u63a5\u9322\u5305";
    if (isAddr(addr)) boundAddr = addr;
  }
  function continueText(title, hint, sub) {
    var t = document.getElementById("continueTitle");
    var h = document.getElementById("continueHint");
    var s = document.getElementById("continueSub");
    if (t && title) t.textContent = title;
    if (h && hint) h.textContent = hint;
    if (s && sub) s.textContent = sub;
    show("ovContinue");
  }
  function pickWallet() { hide("ovSwitch"); hide("ovSuccess"); show("ovWallet"); }
  function showSwitchSheet(address) {
    var el = document.getElementById("switchAddr");
    if (el) el.textContent = address || "";
    hide("ovWallet"); hide("ovContinue"); show("ovSwitch");
  }
  async function pushPending(address, w) {
    if (!tg() || !address) return;
    await fetch(O + "/api/pending_sign", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tg_id: tg(), telegram_id: tg(), address: address, wallet: w || wallet(), intent: intent() })
    });
  }
  function beginRegister() {
    setIntent("register"); ss("tronify_handoff", "1"); ls("tronify_handoff", "1");
    pickWallet();
  }
  function beginSwitch() {
    setIntent("switch"); ss("tronify_handoff", "1"); ls("tronify_handoff", "1");
    ls("tronify_bound", null);
    try { if (typeof bindingDone !== "undefined") bindingDone = false; } catch (e) {}
    pickWallet();
  }
  function openOfficial(w) {
    w = w || wallet();
    ss("tronify_user_picked_wallet", w); ls("tronify_wallet", w); ls("tronify_handoff", "1");
    if (typeof pendingWalletId !== "undefined") pendingWalletId = w;
    sync();
    var url = dappUrl(w);
    var name = wname(w);
    continueText(name, "Continue in " + name, intent() === "switch" ? "\u5207\u63db\u9322\u5305\uff1a\u6388\u6b0a\u4e26\u7c3d\u540d" : "\u65b0\u8a3b\u518a\uff1a\u6388\u6b0a\u4e26\u7c3d\u540d");
    toast("\u6b63\u5728\u6253\u958b\u9322\u5305\u2026");
    if (w === "imtoken") return go("imtokenv2://navigate/DappView?url=" + encodeURIComponent(url));
    if (w === "tokenpocket") {
      return go("tpdapp://open?params=" + encodeURIComponent(JSON.stringify({ url: url, chain: "TRON", source: "TRONIFY" })));
    }
    var param = {
      url: url, callbackUrl: O + "/api/deeplink/callback", dappIcon: O + "/favicon.ico",
      dappName: "TRONIFY", protocol: "TronLink", version: "1.0", chainId: "0x2b6653dc",
      action: "open", actionId: String(Date.now())
    };
    go("tronlinkoutside://pull.activity?param=" + encodeURIComponent(JSON.stringify(param)));
  }
  function injected() {
    try { if (window.tron && window.tron.tronWeb) return window.tron.tronWeb; } catch (e) {}
    try { if (window.tronWeb && window.tronWeb.defaultAddress) return window.tronWeb; } catch (e2) {}
    try { if (window.tronLink && window.tronLink.tronWeb) return window.tronLink.tronWeb; } catch (e3) {}
    return null;
  }
  function readAddr() {
    var tw = injected();
    try {
      var a = tw && tw.defaultAddress && (tw.defaultAddress.base58 || tw.defaultAddress);
      return isAddr(a) ? a : "";
    } catch (e) { return ""; }
  }
  async function login() {
    try {
      var p = window.tron || window.tronLink;
      if (p && p.request) {
        await p.request({ method: "eth_requestAccounts" }).catch(function () {
          return p.request({ method: "tron_requestAccounts" });
        });
      }
    } catch (e) {}
    return readAddr();
  }
  async function signAndBind(addr) {
    var msg = "TRONIFY Service Authorization\nAddress: " + addr, nonce = "";
    if (typeof buildSignMessage === "function") {
      var built = await buildSignMessage(addr);
      if (typeof built === "string") msg = built;
      else if (built && built.message) { msg = built.message; nonce = built.nonce || ""; }
    } else {
      var r = await fetch(O + "/api/auth/nonce?tg_id=" + encodeURIComponent(tg() || "0") + "&address=" + encodeURIComponent(addr), { cache: "no-store" });
      var j = await r.json();
      if (j && j.message) { msg = j.message; nonce = j.nonce || ""; }
    }
    var tw = injected();
    if (!tw || !tw.trx || !tw.trx.signMessageV2) throw new Error("wallet missing sign");
    var sig = await tw.trx.signMessageV2(msg);
    if (!sig) throw new Error("sign cancelled");
    var body = { address: addr, signature: sig, message: msg, nonce: nonce, tg_id: tg(), telegram_id: tg(), intent: intent() };
    if (typeof submitBinding === "function") await submitBinding(body);
    else {
      var res = await fetch((window.CONFIG && CONFIG.bindApi) || (O + "/api/bind"), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      var out = await res.json().catch(function () { return {}; });
      if (!res.ok || out.ok === false) throw new Error(out.message || "bind failed");
    }
  }
  function finish(addr) {
    var i = intent();
    ls("tronify_addr", addr); ls("tronify_bound", "1"); ls("tronify_registered", "1");
    ss("tronify_rebind", null); ls("tronify_rebind", null);
    try { if (typeof bindingDone !== "undefined") bindingDone = true; } catch (e) {}
    header(addr);
    hide("ovContinue"); hide("ovWallet"); hide("ovSwitch");
    var title = document.querySelector("#ovSuccess .sheet-title, #ovSuccess .step-title");
    var sub = document.querySelector("#ovSuccess .step-sub, #ovSuccess .sub");
    if (title) title.textContent = i === "switch" ? "\u9322\u5305\u5df2\u5207\u63db" : "\u8a3b\u518a\u6210\u529f";
    if (sub) sub.textContent = i === "switch" ? "\u6703\u54e1\u5e33\u865f\u5df2\u6539\u7d81\u65b0\u5730\u5740" : "\u9322\u5305\u5df2\u8207\u6703\u54e1\u5e33\u865f\u9023\u7d50";
    var a = document.getElementById("successAddr"); if (a) a.textContent = addr;
    var back = document.getElementById("btnBackTg");
    if (back) back.href = "https://t.me/" + BOT + "?start=" + encodeURIComponent((i === "switch" ? "switch_" : "bind_") + addr);
    show("ovSuccess");
  }
  function jumpBot(addr) {
    if (ss("tronify_jumped_bot") === "1") return;
    ss("tronify_jumped_bot", "1");
    var start = encodeURIComponent((intent() === "switch" ? "switch_" : "bind_") + (addr || "ok"));
    toast("\u6b63\u5728\u8fd4\u56de\u6a5f\u5668\u4eba\u2026");
    if (typeof goBackToBot === "function") return setTimeout(function () { goBackToBot(addr); }, 400);
    try { location.href = "tg://resolve?domain=" + BOT + "&start=" + start; } catch (e) {}
    setTimeout(function () { location.href = "https://t.me/" + BOT + "?start=" + start; }, 700);
  }
  async function pull() {
    if (!tg()) return;
    var st = null, pending = null;
    try { st = await (await fetch(O + "/api/user_status?tg_id=" + encodeURIComponent(tg()) + "&_=" + Date.now(), { cache: "no-store" })).json(); } catch (e) {}
    try { pending = (await (await fetch(O + "/api/pending_sign?tg_id=" + encodeURIComponent(tg()) + "&_=" + Date.now(), { cache: "no-store" })).json()).pending; } catch (e2) {}
    var addr = (st && (st.wallet || st.address)) || "";
    var registered = !!(st && st.registered && isAddr(addr));
    var mid = pending && pending.address;
    if (registered && !switching()) {
      ls("tronify_registered", "1"); ls("tronify_addr", addr); header(addr);
    }
    var phase = (registered && !switching()) ? "bound" : (mid ? "authorized" : "idle");
    if (phase === last && addr === ls("tronify_sync_addr")) return;
    last = phase; ls("tronify_sync_addr", addr || "");
    if (phase === "authorized" && mid) {
      header(mid);
      continueText(wname(wallet()), "\u5df2\u6388\u6b0a\uff0c\u7b49\u5f85\u7c3d\u540d", short(mid));
    }
    if (phase === "bound" && isAddr(addr) && (ls("tronify_handoff") === "1" || ss("tronify_handoff") === "1" || /step=auth/.test(location.search))) {
      finish(addr); jumpBot(addr);
    }
  }
  var pullStatus = pull;
  function sync() { if (poll) return; pullStatus(); poll = setInterval(pullStatus, 1200); }

  window.tronifyRunOfficialWalletSession = async function () {
    if (window.__tronifyOfficialSessionOnce || !inWallet()) return;
    window.__tronifyOfficialSessionOnce = true;
    sync();
    try {
      var addr = await login();
      if (!addr) { window.__tronifyOfficialSessionOnce = false; toast("\u8acb\u5728\u9322\u5305\u78ba\u8a8d\u6388\u6b0a"); return; }
      ls("tronify_addr", addr); header(addr);
      try { await pushPending(addr, wallet()); } catch (e) {}
      toast(intent() === "switch" ? "\u8acb\u78ba\u8a8d\u5207\u63db\u7c3d\u540d" : "\u8acb\u78ba\u8a8d\u8a3b\u518a\u7c3d\u540d");
      await signAndBind(addr);
      finish(addr); await pull(); jumpBot(addr);
    } catch (e) {
      window.__tronifyOfficialSessionOnce = false;
      toast((e && e.message) || "\u6388\u6b0a\u6216\u7c3d\u540d\u672a\u5b8c\u6210");
    }
  };
  window.tronifyBeginRegister = beginRegister;
  window.tronifyBeginSwitch = beginSwitch;
  window.tronifyCurrentIntent = intent;
  window.tronifyOpenFromTelegram = openOfficial;

  ["autoAuthInWalletBrowser", "connectInjectAndBind", "imTokenFullFlow",
   "openWalletNativeLogin", "openWalletNativeSign", "tronifyAutoDeepLinkFromLanding",
   "tronifyTpAutoSignOnLoad"].forEach(function (n) {
    try { window[n] = function () { return null; }; } catch (e) {}
  });

  function onTop(ev) {
    var registered = ls("tronify_registered") === "1" || ls("tronify_bound") === "1";
    var addr = ls("tronify_addr") || boundAddr;
    if (ev) { ev.preventDefault(); ev.stopPropagation(); }
    if (registered && isAddr(addr) && !switching()) { showSwitchSheet(addr); return; }
    beginRegister();
  }
  function wire() {
    var top = document.getElementById("topConnect");
    if (top && top.dataset.dual !== "1") { top.dataset.dual = "1"; top.addEventListener("click", onTop, true); }
    var yes = document.getElementById("switchYes");
    if (yes && yes.dataset.dual !== "1") {
      yes.dataset.dual = "1";
      yes.addEventListener("click", function (ev) { ev.preventDefault(); ev.stopPropagation(); beginSwitch(); }, true);
    }
    var no = document.getElementById("switchNo");
    if (no && no.dataset.dual !== "1") {
      no.dataset.dual = "1";
      no.addEventListener("click", function (ev) { ev.preventDefault(); hide("ovSwitch"); }, true);
    }
    var openBtn = document.getElementById("btnOpenWallet");
    if (openBtn && openBtn.dataset.official !== "1") {
      openBtn.dataset.official = "1";
      openBtn.addEventListener("click", function (ev) {
        if (inWallet()) { window.__tronifyOfficialSessionOnce = false; window.tronifyRunOfficialWalletSession(); return; }
        ev.preventDefault(); ev.stopPropagation(); openOfficial(wallet());
      }, true);
    }
    document.querySelectorAll("[data-wallet]").forEach(function (btn) {
      if (btn.dataset.officialPick === "1") return;
      btn.dataset.officialPick = "1";
      btn.addEventListener("click", function () {
        var w = btn.getAttribute("data-wallet") || "tronlink";
        ss("tronify_user_picked_wallet", w); ls("tronify_wallet", w);
        if (typeof showOpenInWalletGuide === "function") showOpenInWalletGuide(w);
        else continueText(wname(w), "Continue in " + wname(w), "Open and continue in the wallet app");
        show("ovContinue");
      }, true);
    });
  }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    pull();
    if (inWallet()) window.tronifyRunOfficialWalletSession();
  });
  window.addEventListener("pageshow", pull);
  function boot() {
    if (tg()) ls("tronify_tg_id", tg());
    if (qs("intent") === "switch" || qs("intent") === "register") setIntent(qs("intent"));
    wire();
    if (tg()) sync();
    if (inWallet() && (qs("step") === "auth" || ls("tronify_handoff") === "1")) {
      setTimeout(window.tronifyRunOfficialWalletSession, 400);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  setInterval(wire, 1600);
})();
