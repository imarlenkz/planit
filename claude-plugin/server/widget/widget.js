/*!
 * iMARLEN Claude widget — сайтқа чат-көмекші.
 * Қосу:  <script src="https://ai.imarlen.kz/widget.js" data-site="planit" defer></script>
 * Опциялар: data-site (міндетті), data-api (әдепкі: скрипттің өз домені), data-position="left|right"
 */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || window.__imarlenClaude) return;
  window.__imarlenClaude = true;

  var site = script.getAttribute("data-site");
  var api = (script.getAttribute("data-api") || new URL(script.src).origin).replace(/\/$/, "");
  var side = script.getAttribute("data-position") === "left" ? "left" : "right";
  if (!site) { console.warn("[imarlen-claude] data-site жоқ"); return; }

  var storeKey = "imarlen-claude:" + site;
  var history = [];
  try { history = JSON.parse(sessionStorage.getItem(storeKey) || "[]") || []; } catch (e) { history = []; }
  function save() { try { sessionStorage.setItem(storeKey, JSON.stringify(history.slice(-20))); } catch (e) {} }

  var host = document.createElement("div");
  host.style.cssText = "position:fixed;bottom:20px;" + side + ":20px;z-index:2147483000";
  document.body.appendChild(host);
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  root.innerHTML =
    '<style>' +
    ':host{all:initial}*{box-sizing:border-box;font-family:Nunito,system-ui,-apple-system,"Segoe UI",sans-serif}' +
    '.btn{width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;background:var(--c);color:#fff;' +
    'box-shadow:0 6px 20px rgba(0,0,0,.2);display:flex;align-items:center;justify-content:center}' +
    '.btn svg{width:26px;height:26px}' +
    '.panel{position:absolute;bottom:68px;' + side + ':0;width:min(370px,calc(100vw - 32px));height:min(540px,calc(100vh - 110px));' +
    'background:#fff;color:#1b2430;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden}' +
    '.panel.open{display:flex}' +
    '.head{background:var(--c);color:#fff;padding:12px 14px;font-weight:700;display:flex;justify-content:space-between;align-items:center}' +
    '.head button{background:none;border:0;color:#fff;cursor:pointer;font-size:13px;opacity:.85}' +
    '.log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f6f8fa}' +
    '.m{max-width:85%;padding:8px 11px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word;font-size:14px;line-height:1.4}' +
    '.u{align-self:flex-end;background:var(--c);color:#fff;border-bottom-right-radius:4px}' +
    '.a{align-self:flex-start;background:#fff;border:1px solid #e3e8ee;border-bottom-left-radius:4px}' +
    '.note{align-self:flex-start;font-size:12px;color:#6b7785}' +
    '.err{align-self:flex-start;font-size:13px;color:#b42318}' +
    'form{display:flex;gap:6px;padding:10px;border-top:1px solid #e3e8ee;background:#fff}' +
    'textarea{flex:1;resize:none;border:1px solid #d0d7de;border-radius:10px;padding:8px 10px;font-size:14px;height:40px;max-height:120px;color:#1b2430;background:#fff}' +
    'form button{border:0;border-radius:10px;background:var(--c);color:#fff;padding:0 14px;font-weight:700;cursor:pointer}' +
    'form button:disabled{opacity:.5;cursor:default}' +
    '.foot{font-size:11px;color:#8b96a3;text-align:center;padding:0 0 8px;background:#fff}' +
    '@media (prefers-color-scheme:dark){.panel{background:#161b22;color:#e6edf3}.log{background:#0d1117}' +
    '.a{background:#161b22;border-color:#30363d;color:#e6edf3}form,.foot{background:#161b22;border-color:#30363d}' +
    'textarea{background:#0d1117;color:#e6edf3;border-color:#30363d}}' +
    '</style>' +
    '<div class="panel" role="dialog" aria-label="Chat">' +
    '<div class="head"><span class="title">Көмекші</span><button type="button" class="clear">Жаңа чат</button></div>' +
    '<div class="log" aria-live="polite"></div>' +
    '<form><textarea placeholder="Сұрағыңызды жазыңыз…" maxlength="4000"></textarea><button type="submit">➤</button></form>' +
    '<div class="foot">Claude AI · жауаптарды тексеріп отырыңыз</div>' +
    '</div>' +
    '<button class="btn" type="button" aria-label="Чатты ашу">' +
    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z"/></svg></button>';

  var panel = root.querySelector(".panel"), log = root.querySelector(".log");
  var form = root.querySelector("form"), input = root.querySelector("textarea");
  var sendBtn = form.querySelector("button"), title = root.querySelector(".title");
  var greeting = "Сәлеметсіз бе! Сізге қалай көмектесе аламын?";
  host.style.setProperty("--c", "#2f9e6e");

  function add(cls, text) {
    var el = document.createElement("div");
    el.className = cls; el.textContent = text;
    log.appendChild(el); log.scrollTop = log.scrollHeight;
    return el;
  }
  function render() {
    log.innerHTML = "";
    add("m a", greeting);
    history.forEach(function (m) { add("m " + (m.role === "user" ? "u" : "a"), m.content); });
  }

  fetch(api + "/v1/sites/" + encodeURIComponent(site)).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (cfg) {
      if (!cfg) return;
      title.textContent = cfg.title || cfg.name || "Көмекші";
      greeting = cfg.greeting || greeting;
      if (/^#[0-9a-fA-F]{3,8}$/.test(cfg.color || "")) host.style.setProperty("--c", cfg.color);
      render();
    }).catch(function () {});
  render();

  root.querySelector(".btn").addEventListener("click", function () {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) input.focus();
  });
  root.querySelector(".clear").addEventListener("click", function () { history = []; save(); render(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit")); }
  });

  var busy = false;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text || busy) return;
    busy = true; sendBtn.disabled = true; input.value = "";
    history.push({ role: "user", content: text }); save();
    add("m u", text);
    var bubble = null, answer = "", note = add("note", "…");

    fetch(api + "/v1/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site: site, messages: history })
    }).then(function (resp) {
      if (!resp.ok || !resp.body) {
        return resp.json().catch(function () { return {}; }).then(function (j) { throw new Error(j.detail || ("HTTP " + resp.status)); });
      }
      var reader = resp.body.getReader(), dec = new TextDecoder(), buf = "";
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) return;
          buf += dec.decode(r.value, { stream: true });
          var parts = buf.split("\n\n"); buf = parts.pop();
          parts.forEach(function (chunk) {
            var ev = "message", data = "";
            chunk.split("\n").forEach(function (line) {
              if (line.indexOf("event: ") === 0) ev = line.slice(7);
              else if (line.indexOf("data: ") === 0) data += line.slice(6);
            });
            var d = {}; try { d = JSON.parse(data || "{}"); } catch (x) {}
            if (ev === "text") {
              if (!bubble) { bubble = add("m a", ""); }
              answer += d.text || ""; bubble.textContent = answer; log.scrollTop = log.scrollHeight;
              note.textContent = "";
            } else if (ev === "tool") {
              note.textContent = "🔎 сайттан қарап жатыр…"; log.appendChild(note);
              if (answer) answer += "\n";
            } else if (ev === "error") {
              add("err", d.message || "Қате");
            }
          });
          return pump();
        });
      }
      return pump();
    }).catch(function (err) {
      add("err", err.message || "Қосылу қатесі");
    }).then(function () {
      if (note.parentNode) note.parentNode.removeChild(note);
      if (answer.trim()) { history.push({ role: "assistant", content: answer.trim() }); }
      else { history.pop(); }
      save(); busy = false; sendBtn.disabled = false; input.focus();
    });
  });
})();
