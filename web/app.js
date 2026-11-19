"use strict";
/* LogicBuilder front-end: hash router, stepped lessons, 6 exercise types, visualizer, AI tutor. No build step. */

const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};
const curUser = () => store.get("lb-user", "default");
const api = async (path, body) => {
  const headers = { "X-User": curUser() };
  const opt = body === undefined ? { headers } : { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch("/api" + path, opt);
  const j = await r.json();
  if (!r.ok) { const e = new Error(j.error ? j.error.message : "Request failed"); e.code = j.error && j.error.code; e.status = r.status; throw e; }
  return j;
};
/* ---------- per-learner state kept ON THE SERVER: code drafts, plans, playground code, language, lesson position ---------- */
let STATE = { drafts: {}, prefs: {}, lessons: {} };
const pendingDrafts = {};
let flushTimer = null;
const draftGet = (k, d) => (k in STATE.drafts ? STATE.drafts[k] : d);
function draftSet(k, v) { STATE.drafts[k] = v; pendingDrafts[k] = v; clearTimeout(flushTimer); flushTimer = setTimeout(flushDrafts, 700); }
async function flushDrafts() {
  const items = { ...pendingDrafts };
  for (const k in pendingDrafts) delete pendingDrafts[k];
  if (!Object.keys(items).length) return;
  try {
    await fetch("/api/me/drafts", { method: "POST", keepalive: true, headers: { "X-User": curUser(), "Content-Type": "application/json" }, body: JSON.stringify({ drafts: items }) });
  } catch { Object.assign(pendingDrafts, items); } // retry with the next change
}
addEventListener("pagehide", flushDrafts);
document.addEventListener("visibilitychange", () => { if (document.hidden) flushDrafts(); });
async function loadState() {
  try { STATE = await api("/me/state"); } catch { STATE = { drafts: {}, prefs: {}, lessons: {} }; }
  await migrateLocal();
}
/* one-time: copy anything this browser saved before progress moved to the server */
async function migrateLocal() {
  const u = curUser(), flag = `lb-migrated-${u}`;
  if (store.get(flag, "")) return;
  const found = {};
  try {
    const esc2 = u.replace(/[^\w-]/g, "");
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i), v = localStorage.getItem(k);
      let m;
      if ((m = k.match(new RegExp(`^draft-${esc2}-(.+)-(python|javascript|typescript|java|cpp|go|csharp)$`)))) found[`draft:${m[1]}:${m[2]}`] = v;
      else if ((m = k.match(new RegExp(`^draft-${esc2}-(.+)$`)))) found[`draft:${m[1]}:python`] = v;
      else if ((m = k.match(new RegExp(`^plan-${esc2}-(.+)$`)))) found[`plan:${m[1]}`] = v;
      else if ((m = k.match(/^pg-code-(\w+)$/))) found[`pg:${m[1]}`] = v;
    }
  } catch { /* storage unavailable */ }
  for (const k in found) if (found[k] && !(k in STATE.drafts)) { STATE.drafts[k] = found[k]; pendingDrafts[k] = found[k]; }
  const oldLang = store.get(`lb-lang-${u}`, "");
  if (oldLang && !STATE.prefs.lang) { STATE.prefs.lang = oldLang; api("/me/prefs", { lang: oldLang }).catch(() => {}); }
  await flushDrafts();
  store.set(flag, "1");
}

function toast(msg) { const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 2200); }

/* ---------- tiny markdown ---------- */
function md(src) {
  const blocks = [];
  src = src.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _l, c) => { blocks.push(`<pre><code>${esc(c.replace(/\n$/, ""))}</code></pre>`); return `\n\n\u0000${blocks.length - 1}\u0000\n\n`; });
  src = src.replace(/^(#{1,4} .*)$/gm, "\n\n$1\n\n");
  const inline = (t) => esc(t).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*\n]+)\*/g, "<i>$1</i>");
  return src.split(/\n{2,}/).map((chunk) => {
    chunk = chunk.trim();
    if (!chunk) return "";
    const ph = chunk.match(/^\u0000(\d+)\u0000$/);
    if (ph) return blocks[+ph[1]];
    const h = chunk.match(/^(#{1,4})\s+(.*)$/);
    if (h && !chunk.includes("\n")) return `<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`;
    const lines = chunk.split("\n");
    if (lines.every((l) => /^\s*(?:[-*]|\d+\.)\s+/.test(l))) {
      const tag = /^\s*\d+\./.test(lines[0]) ? "ol" : "ul";
      return `<${tag}>${lines.map((l) => `<li>${inline(l.replace(/^\s*(?:[-*]|\d+\.)\s+/, ""))}</li>`).join("")}</${tag}>`;
    }
    return `<p>${inline(chunk).replace(/\n/g, "<br>")}</p>`;
  }).join("\n");
}

/* ---------- shared bits ---------- */
function codeHTML(code, { hl = 0, click = false } = {}) {
  return `<div class="viz-code codeview${click ? " clickable" : ""}">` + code.split("\n").map((l, n) =>
    `<div data-l="${n + 1}" class="${n + 1 === hl ? "cur" : ""}"><span class="n">${n + 1}</span>${esc(l) || " "}</div>`).join("") + "</div>";
}
const askAI = (text) => send(text);
const ic = (t) => esc(t).replace(/`([^`]+)`/g, "<code>$1</code>"); // inline `code` in short prompts

/* ---------- visualizer ---------- */
const POINTERS = new Set(["i", "j", "k", "lo", "hi", "low", "high", "mid", "left", "right", "l", "r", "idx", "index", "p", "pos", "start", "end"]);
function plain(v) {
  if (!v) return "";
  switch (v.t) {
    case "NoneType": return "None";
    case "bool": return v.v ? "True" : "False";
    case "str": return JSON.stringify(v.v);
    case "list": return "[" + v.items.map(plain).join(", ") + (v.more ? ", …" : "") + "]";
    case "tuple": return "(" + v.items.map(plain).join(", ") + (v.more ? ", …" : "") + ")";
    case "set": case "frozenset": return "{" + v.items.map(plain).join(", ") + "}";
    case "dict": return "{" + v.entries.map(([k, x]) => plain(k) + ": " + plain(x)).join(", ") + (v.more ? ", …" : "") + "}";
    default: return String(v.v);
  }
}
function valHTML(v, ptrs = {}) {
  if (["list", "tuple", "set", "frozenset"].includes(v.t)) {
    return `<div class="arr" title="${v.t}">` + v.items.map((x, i) => {
      const p = ptrs[i];
      return `<div class="cell${p ? " ptr-on" : ""}"><span class="idx">${i}</span><span class="v">${esc(plain(x))}</span><span class="ptr">${p ? esc(p.join(",")) : ""}</span></div>`;
    }).join("") + (v.more ? `<div class="cell more">+${v.more}</div>` : "") + (v.items.length ? "" : "<i>empty</i>") + "</div>";
  }
  if (v.t === "dict") return v.entries.length ? "<table>" + v.entries.map(([k, x]) => `<tr><td>${esc(plain(k))}</td><td>${esc(plain(x))}</td></tr>`).join("") + "</table>" : "<i>empty</i>";
  return esc(plain(v));
}
function narrate(trace, i, lines) {
  const s = trace.steps[i], prev = trace.steps[i - 1];
  const src = (lines[s.line - 1] || "").trim();
  const top = s.stack[s.stack.length - 1];
  let msg;
  if (s.event === "call") msg = `Calling <b>${esc(top.fn)}(${Object.values(top.locals).map(plain).map(esc).join(", ")})</b>. A new frame is added to the stack.`;
  else if (s.event === "return") msg = `<b>${esc(top.fn)}</b> returns <b>${esc(plain(s.ret))}</b>. Its frame will be removed.`;
  else if (s.event === "exception") msg = `⚠ Error: <b>${esc(s.exc)}</b>`;
  else msg = `About to run line ${s.line}: <code>${esc(src)}</code>`;
  const changes = [];
  if (prev) {
    const pf = prev.stack[prev.stack.length - 1];
    if (pf && top && pf.fn === top.fn) {
      for (const [k, v] of Object.entries(top.locals)) {
        const was = pf.locals[k];
        if (!was) changes.push(`${esc(k)} = ${esc(plain(v))} (new)`);
        else if (JSON.stringify(was) !== JSON.stringify(v)) changes.push(`${esc(k)}: ${esc(plain(was))} → ${esc(plain(v))}`);
      }
    }
  }
  return msg + (changes.length ? `<div style="margin-top:4px;color:var(--muted)">Changed: ${changes.join(" · ")}</div>` : "");
}
const stripQ = (s) => String(s).trim().replace(/^['"]|['"]$/g, "");

function mountViz(el, code, trace) {
  const lines = code.split("\n");
  if (trace.error && trace.verdict === "CE") { el.innerHTML = `<div class="res fail">Syntax error on line ${trace.error.line}: ${esc(trace.error.message)}</div>`; return; }
  if (!trace.steps.length) { el.innerHTML = `<div class="res">Nothing to visualize (no lines ran).</div>`; return; }
  let i = 0, timer = null, pendingMsg = "";
  el.innerHTML = `<div class="viz"><div class="viz-code"></div><div><div class="viz-note"></div><h4>Call stack (top frame highlighted)</h4><div class="viz-stack"></div><h4>Output</h4><pre class="viz-out"></pre></div></div>
  <div class="viz-ctl"><button class="btn" data-a="first" title="Restart">⏮</button><button class="btn" data-a="prev">◀ Back</button><button class="btn accent" data-a="play">▶ Play</button><button class="btn" data-a="next">Next ▶</button>
  <input type="range" min="0" max="${trace.steps.length - 1}" value="0" aria-label="Step"><span class="count"></span>
  <label class="pm" title="Guess the next value before it happens"><input type="checkbox" class="pmc"> 🎯 Predict mode</label></div><div class="viz-end"></div>`;
  $(".viz-code", el).innerHTML = lines.map((l, n) => `<div data-l="${n + 1}"><span class="n">${n + 1}</span>${esc(l) || " "}</div>`).join("");
  const range = $("input[type=range]", el), playBtn = $('[data-a="play"]', el), pm = $(".pmc", el), last = trace.steps.length - 1;
  function draw() {
    const s = trace.steps[i], prev = trace.steps[i - 1];
    el.querySelectorAll(".viz-code .cur").forEach((d) => d.classList.remove("cur"));
    const cur = $(`.viz-code [data-l="${s.line}"]`, el);
    if (cur) { cur.classList.add("cur"); cur.scrollIntoView({ block: "nearest" }); }
    $(".viz-note", el).innerHTML = narrate(trace, i, lines) + pendingMsg;
    pendingMsg = "";
    const frames = s.stack.slice().reverse();
    $(".viz-stack", el).innerHTML = frames.map((f, k) => {
      const pf = prev && prev.stack[s.stack.length - 1 - k] && prev.stack[s.stack.length - 1 - k].fn === f.fn ? prev.stack[s.stack.length - 1 - k] : null;
      const idxVars = {};
      Object.entries(f.locals).forEach(([n, v]) => { if (v.t === "int" && POINTERS.has(n) && typeof v.v === "number" && v.v >= 0) (idxVars[v.v] ||= []).push(n); });
      const rows = Object.entries(f.locals).map(([n, v]) => {
        const changed = prev && (!pf || JSON.stringify(pf.locals[n]) !== JSON.stringify(v));
        return `<tr><td>${esc(n)}</td><td class="${changed ? "chg" : ""}">${valHTML(v, idxVars)}</td></tr>`;
      }).join("");
      return `<div class="frame ${k === 0 ? "top" : ""}"><div class="fh">${esc(f.fn)}${f.fn === "main" ? " (top level)" : "()"} · line ${f.line}</div><table>${rows || '<tr><td colspan="2"><i>no variables yet</i></td></tr>'}</table></div>`;
    }).join("");
    $(".viz-out", el).textContent = s.stdout || "";
    range.value = i;
    $(".count", el).textContent = `step ${i + 1} / ${trace.steps.length}`;
    $(".viz-end", el).innerHTML = i === last ? (trace.truncated ? `<div class="res">Stopped after ${trace.steps.length} steps (limit) to keep the page fast.</div>` : trace.error ? `<div class="res fail">${esc(trace.error.type)}: ${esc(trace.error.message)}</div>` : `<div class="res pass">Program finished.</div>`) : "";
    aiCtx.step = `step ${i + 1}/${trace.steps.length}, line ${s.line} (${lines[s.line - 1] || ""}), event ${s.event}, variables: ` + JSON.stringify(Object.fromEntries(Object.entries(s.stack[s.stack.length - 1].locals).map(([k, v]) => [k, plain(v)])));
  }
  const stop = () => { clearInterval(timer); timer = null; playBtn.textContent = "▶ Play"; };
  const go = (n) => { i = Math.max(0, Math.min(last, n)); draw(); };
  function nextChange() {
    const a = trace.steps[i], b = trace.steps[i + 1];
    const fa = a.stack[a.stack.length - 1], fb = b.stack[b.stack.length - 1];
    if (!fa || !fb || fa.fn !== fb.fn) return null;
    for (const [k, v] of Object.entries(fb.locals)) if (["int", "float", "str", "bool"].includes(v.t) && JSON.stringify(fa.locals[k]) !== JSON.stringify(v)) return [k, v];
    return null;
  }
  function advance() {
    if (!pm.checked || i >= last) return go(i + 1);
    const ch = nextChange();
    if (!ch) return go(i + 1);
    const [name, val] = ch, ln = trace.steps[i].line;
    $(".viz-note", el).innerHTML = `🎯 Line ${ln} is about to run: <code>${esc((lines[ln - 1] || "").trim())}</code><div class="predict-box">What will <b>${esc(name)}</b> be afterwards? <input class="pin" autocomplete="off"><button class="btn accent pgo">Check</button><button class="btn pskip">Skip</button></div>`;
    const inp = $(".pin", el); inp.focus();
    const finish = (skip) => {
      const guess = inp.value;
      if (!skip && stripQ(guess) === stripQ(plain(val))) pendingMsg = `<div class="good">✅ Yes, ${esc(name)} becomes ${esc(plain(val))}.</div>`;
      else if (!skip) pendingMsg = `<div class="bad">Not quite: ${esc(name)} becomes ${esc(plain(val))}. Check how that line uses the earlier values.</div>`;
      go(i + 1);
    };
    $(".pgo", el).onclick = () => finish(false);
    $(".pskip", el).onclick = () => finish(true);
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") finish(false); });
  }
  el.addEventListener("click", (e) => {
    const a = e.target.dataset && e.target.dataset.a;
    if (!a) return;
    if (a === "next") { stop(); advance(); }
    if (a === "prev") { stop(); go(i - 1); }
    if (a === "first") { stop(); go(0); }
    if (a === "play") {
      if (timer) return stop();
      pm.checked = false;
      if (i >= last) go(0);
      playBtn.textContent = "⏸ Pause";
      timer = setInterval(() => { if (i >= last) return stop(); go(i + 1); }, 700);
    }
  });
  range.addEventListener("input", () => { stop(); go(+range.value); });
  el.tabIndex = 0;
  draw();
}
async function visualizeInto(el, code, url = "/trace") {
  el.innerHTML = `<div class="res">Tracing…</div>`;
  try { mountViz(el, code, await api(url, { code })); } catch (e) { el.innerHTML = `<div class="res fail">${esc(e.message)}</div>`; }
}

/* ---------- exercises ---------- */
const LABEL = { quiz: "Quick check", predict: "Predict the output", fill: "Fill the blank", parsons: "Put in order", trace_table: "Trace table", bug: "Find the bug" };
function mountExercise(host, ex, onDone) {
  host.classList.remove("done");
  host.classList.add("card", "ex");
  if (ex.done && !ex.retry) { // already solved earlier: show a compact summary, with the option to practise again
    host.classList.add("done");
    host.innerHTML = `<div class="ex-h"><span class="badge">${LABEL[ex.type]}</span> ${ic(ex.prompt)}</div><p class="good" style="margin:6px 0">✅ You answered this correctly before.</p><button class="btn again">Practise it again</button>`;
    $(".again", host).onclick = () => mountExercise(host, { ...ex, retry: true }, onDone);
    onDone(true);
    return;
  }
  host.innerHTML = `<div class="ex-h"><span class="badge">${LABEL[ex.type]}</span> ${ic(ex.prompt)}</div><div class="ex-body"></div><div class="ex-actions row"></div><div class="fb"></div>`;
  const body = $(".ex-body", host), act = $(".ex-actions", host), fb = $(".fb", host);
  let attempts = 0, finished = false, getAnswer = () => null, mark = () => {}, reveal = () => {}, lock = () => {};
  aiCtx.exercise = `${LABEL[ex.type]}: ${ex.prompt}\n${ex.code || (ex.lines ? ex.lines.join("\n") : "") || ""}`;

  if (ex.type === "quiz") {
    body.innerHTML = ex.options.map((o, i) => `<button class="btn qopt" data-i="${i}" style="display:block;width:100%;text-align:left;margin:6px 0">${esc(o)}</button>`).join("");
    getAnswer = () => null;
    body.onclick = (e) => { const i = e.target.dataset && e.target.dataset.i; if (i !== undefined && !finished) doCheck(+i, e.target); };
    reveal = (sol) => { const b = body.querySelector(`[data-i="${sol}"]`); if (b) b.classList.add("right"); };
    lock = () => body.querySelectorAll("button").forEach((b) => { b.disabled = true; });
  }
  if (ex.type === "predict") {
    body.innerHTML = codeHTML(ex.code) + `<textarea class="ans" rows="${Math.min(6, ex.lines)}" placeholder="Type exactly what gets printed${ex.lines > 1 ? " (one line per printed line)" : ""}" spellcheck="false"></textarea>`;
    const ta = $("textarea", body);
    getAnswer = () => (ta.value.trim() ? ta.value : null);
    reveal = (sol) => { ta.value = sol; };
    lock = () => { ta.disabled = true; };
  }
  if (ex.type === "fill") {
    const parts = ex.code.split(/\{\{(\w+)\}\}/);
    body.innerHTML = `<pre class="fillpre">` + parts.map((p, i) => (i % 2 ? `<input data-k="${esc(p)}" autocomplete="off" spellcheck="false">` : esc(p))).join("") + `</pre>`;
    const inputs = () => [...body.querySelectorAll("input")];
    getAnswer = () => { const o = {}; inputs().forEach((x) => { o[x.dataset.k] = x.value; }); return inputs().some((x) => x.value.trim()) ? o : null; };
    mark = (d) => inputs().forEach((x) => { x.classList.toggle("right", !!(d.blanks && d.blanks[x.dataset.k])); x.classList.toggle("wrong", !!(d.blanks && !d.blanks[x.dataset.k])); });
    reveal = (sol) => inputs().forEach((x) => { x.value = sol[x.dataset.k]; x.classList.add("right"); x.classList.remove("wrong"); });
    lock = () => inputs().forEach((x) => { x.disabled = true; });
  }
  if (ex.type === "parsons") {
    let order = ex.lines.slice(), dragFrom = null;
    const render = (marks) => {
      body.innerHTML = order.map((l, i) => `<div class="pl ${marks ? (marks[i] ? "right" : "wrong") : ""}" draggable="${!finished}" data-i="${i}"><span class="grip">⠿</span><code>${esc(l)}</code><span><button class="btn" data-up="${i}" ${finished ? "disabled" : ""}>↑</button> <button class="btn" data-dn="${i}" ${finished ? "disabled" : ""}>↓</button></span></div>`).join("");
    };
    const move = (a, b) => { if (b < 0 || b >= order.length || a === b) return; const [x] = order.splice(a, 1); order.splice(b, 0, x); render(); };
    render();
    body.addEventListener("click", (e) => { const t = e.target.dataset; if (t.up !== undefined) move(+t.up, +t.up - 1); if (t.dn !== undefined) move(+t.dn, +t.dn + 1); });
    body.addEventListener("dragstart", (e) => { const r = e.target.closest(".pl"); if (r) { dragFrom = +r.dataset.i; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", "x"); } });
    body.addEventListener("dragover", (e) => { if (dragFrom !== null) e.preventDefault(); });
    body.addEventListener("drop", (e) => { e.preventDefault(); const r = e.target.closest(".pl"); if (r && dragFrom !== null) move(dragFrom, +r.dataset.i); dragFrom = null; });
    getAnswer = () => order.slice();
    mark = (d) => render(d.positions);
    reveal = (sol) => { order = sol.slice(); render(); };
    lock = () => render();
  }
  if (ex.type === "trace_table") {
    body.innerHTML = codeHTML(ex.code, { hl: ex.line }) + `<table class="tt"><tr>${ex.vars.map((v) => `<th>${esc(v)}</th>`).join("")}</tr>` +
      Array.from({ length: ex.rows }, (_, r) => `<tr>${ex.vars.map((_v, c) => `<td><input data-r="${r}" data-c="${c}" autocomplete="off"></td>`).join("")}</tr>`).join("") + `</table>`;
    const inputs = () => [...body.querySelectorAll("input")];
    getAnswer = () => { const m = Array.from({ length: ex.rows }, () => Array(ex.vars.length).fill("")); inputs().forEach((x) => { m[+x.dataset.r][+x.dataset.c] = x.value; }); return inputs().some((x) => x.value.trim()) ? m : null; };
    mark = (d) => inputs().forEach((x) => { const ok = d.cells && d.cells[+x.dataset.r] && d.cells[+x.dataset.r][+x.dataset.c]; x.classList.toggle("right", !!ok); x.classList.toggle("wrong", !ok); });
    reveal = (sol) => inputs().forEach((x) => { x.value = sol[+x.dataset.r][+x.dataset.c]; x.classList.add("right"); x.classList.remove("wrong"); });
    lock = () => inputs().forEach((x) => { x.disabled = true; });
  }
  if (ex.type === "bug") {
    body.innerHTML = codeHTML(ex.code, { click: true });
    let sel = null;
    body.onclick = (e) => { const d = e.target.closest("[data-l]"); if (!d || finished) return; body.querySelectorAll(".sel").forEach((x) => x.classList.remove("sel", "wrongline")); d.classList.add("sel"); sel = +d.dataset.l; };
    getAnswer = () => sel;
    mark = () => { const d = body.querySelector(".sel"); if (d) { d.classList.remove("sel"); d.classList.add("wrongline"); } };
    reveal = (sol) => { body.querySelectorAll(".sel,.wrongline").forEach((x) => x.classList.remove("sel", "wrongline")); const d = body.querySelector(`[data-l="${sol}"]`); if (d) d.classList.add("rightline"); };
    lock = () => body.classList.remove("clickable");
  }

  function end(r, ok) {
    finished = true; lock();
    host.classList.add("done");
    fb.innerHTML = `<p class="${ok ? "good" : ""}">${ok ? "✅ Correct! " : "Here's the answer. "}${esc(r.explain || "")}</p>`;
    act.innerHTML = "";
    onDone(ok);
  }
  async function doCheck(ans, btn) {
    if (finished) return;
    const a = ans === undefined ? getAnswer() : ans;
    if (a === null || a === undefined) { fb.innerHTML = `<p class="bad">Give an answer first.</p>`; return; }
    let r;
    try { r = await api("/exercises/check", { id: ex.id, answer: a }); } catch (e) { fb.innerHTML = `<p class="bad">${esc(e.message)}</p>`; return; }
    attempts++;
    if (r.correct) { if (ex.type === "quiz" && btn) btn.classList.add("right"); return end(r, true); }
    mark(r.detail || {});
    if (btn) btn.classList.add("wrong");
    fb.innerHTML = `<p class="bad">Not quite${attempts >= 2 ? ". Try tracing it by hand, one line at a time." : ", have another look."}</p>`;
    if (attempts >= 2 && !act.querySelector(".hintb")) {
      act.insertAdjacentHTML("beforeend", `<button class="btn hintb">✦ Hint from AI tutor</button>`);
      $(".hintb", act).onclick = () => askAI("I'm stuck on this exercise. Give me a small hint without telling me the answer.");
    }
    if (attempts >= 3 && !act.querySelector(".showb")) {
      act.insertAdjacentHTML("beforeend", `<button class="btn showb">Show the answer</button>`);
      $(".showb", act).onclick = async () => { const s = await api("/exercises/check", { id: ex.id, answer: null, reveal: true }); reveal(s.solution); end(s, false); };
    }
  }
  if (ex.type !== "quiz") {
    act.innerHTML = `<button class="btn accent chk">Check</button>`;
    $(".chk", act).onclick = () => doCheck();
  }
}

/* ---------- views ---------- */
let aiCtx = {};
function setQuick(list) { $("#ai-quick").innerHTML = list.map((q) => `<button class="btn" type="button">${esc(q)}</button>`).join(""); }
const LEVELS = ["Level 0 · Thinking", "Level 1 · Basics", "Level 2 · Repetition", "Level 3 · Functions", "Level 4 · Collections", "Level 5 · Core DSA", "Level 6 · Patterns"];

async function refreshStats() {
  try {
    const p = await api("/progress");
    $("#stats").innerHTML = `${p.plan === "pro" ? '<span class="badge ok">PRO</span>' : ""}<span title="Days in a row">🔥 ${p.streak}</span><span>⭐ ${p.xp} XP</span>`;
    const n = $("#review-n"); n.hidden = !p.review_due; n.textContent = p.review_due;
    return p;
  } catch { return null; }
}

async function home() {
  const [p, lessons, problems] = await Promise.all([refreshStats(), api("/lessons"), api("/problems")]);
  const next = lessons.find((l) => !l.done && !l.locked);
  const nextP = problems.find((x) => x.status !== "solved");
  view.innerHTML = `<h1>Hi ${esc(p.name)}, let's build your logic</h1>
  <p>Logic isn't memorised in one sitting. It grows from many small steps: <b>see</b> code run, <b>predict</b> it, <b>fix</b> it, then <b>build</b> it. The method for every problem:</p>
  <div class="method"><span><b>U</b>nderstand</span><span><b>E</b>xamples</span><span><b>P</b>lan</span><span><b>C</b>ode</span><span><b>T</b>est</span><span><b>I</b>mprove</span></div>
  <div class="grid">
    <div class="card"><h4>Lessons</h4><div class="bar-track"><div class="bar-fill" style="width:${100 * p.lessons_done / p.lessons_total}%"></div></div><p>${p.lessons_done} / ${p.lessons_total} complete</p>
      ${next ? `<a class="btn accent" href="#/lesson/${next.id}">${p.lessons_done ? "Continue" : "Start"}: ${esc(next.title)}</a>` : "<b>All available lessons done 🎉</b>"}</div>
    <div class="card"><h4>Practice</h4><div class="bar-track"><div class="bar-fill" style="width:${100 * p.solved / p.problems_total}%"></div></div><p>${p.solved} / ${p.problems_total} solved</p>
      ${nextP ? `<a class="btn accent" href="#/problem/${nextP.slug}">Next: ${esc(nextP.title)}</a>` : "<b>Everything solved 🎉</b>"}</div>
    <div class="card"><h4>Review</h4><p>${p.review_due ? `<b>${p.review_due}</b> exercise${p.review_due > 1 ? "s" : ""} due. A few minutes now locks it in memory.` : "Nothing due. Finish lessons to build your review queue."}</p>${p.review_due ? '<a class="btn accent" href="#/review">Start review</a>' : '<a class="btn" href="#/skills">See skill map</a>'}</div>
  </div>
  <h2>Badges</h2><div class="badges">${p.badges.map((b) => `<div class="badge-card ${b.earned ? "" : "off"}"><div class="big">${b.earned ? "🏅" : "🔒"}</div><b>${esc(b.title)}</b><div class="muted">${esc(b.desc)}</div></div>`).join("")}</div>`;
  aiCtx = {};
  setQuick(["Where should a total beginner start?", "How do I get better at logic?"]);
}

async function learn() {
  const ls = await api("/lessons");
  view.innerHTML = `<h1>Learn</h1>` + [...new Set(ls.map((l) => l.level))].sort().map((lv) => `<h2>${LEVELS[lv] || "Level " + lv}</h2><div class="grid">` +
    ls.filter((l) => l.level === lv).map((l) => `<a class="item ${l.locked ? "locked" : ""}" href="#/lesson/${l.id}"><div class="t">${l.locked ? "🔒 " : ""}${esc(l.title)}</div><div class="m">${l.minutes} min ${l.done ? '<span class="badge ok">done</span>' : ""}${l.premium ? ' <span class="badge">Pro</span>' : ""}</div></a>`).join("") + "</div>").join("");
  aiCtx = {}; setQuick(["What is the difference between a variable and a function?", "Give me a study plan"]);
}

function paywall() {
  view.innerHTML = `<div class="card paywall"><h1>🔒 This lesson is part of Pro</h1><p>Pro unlocks the Core DSA levels: Big-O, sorting, stacks and more.</p>
  <button class="btn accent" id="up">Upgrade (demo: switches this learner to Pro)</button> <a class="btn" href="#/learn">Back to lessons</a>
  <p class="muted">Local demo, no payment. In production this button opens checkout and a payment webhook sets the plan.</p></div>`;
  $("#up").onclick = async () => { await api("/me", { plan: "pro" }); await refreshStats(); toast("Pro unlocked"); route(); };
}

async function lesson(id) {
  let l;
  try { l = await api("/lessons/" + id); } catch (e) { if (e.code === "PAYWALL") return paywall(); throw e; }
  view.innerHTML = `<div class="lesson"><a href="#/learn">← All lessons</a><h1>${esc(l.title)}</h1><div class="progress"><div class="bar-track"><div class="bar-fill" id="pb" style="width:0"></div></div></div>
    <div id="blocks"></div><div class="stepbar" id="sb"><span class="muted" id="si"></span><button class="btn accent" id="cont">Continue ▶</button></div></div>`;
  const box = $("#blocks"), cont = $("#cont"), n = l.blocks.length;
  let shown = 0, gate = true;
  aiCtx = { lesson: `${l.title} (level ${l.level})` };
  const interactive = (b) => !!b.id;
  function renderBlock(b) {
    const d = document.createElement("div");
    d.className = "block";
    if (b.type === "text") d.innerHTML = md(b.md);
    else if (b.type === "code") {
      d.innerHTML = `<div class="codeblock"><pre><code>${esc(b.code)}</code></pre><div class="bar"><button class="btn accent" data-v>▶ Visualize</button><button class="btn" data-p>Edit in playground</button></div><div class="vz" style="padding:8px"></div></div>`;
      $("[data-v]", d).onclick = () => { aiCtx.code = b.code; visualizeInto($(".vz", d), b.code); };
      $("[data-p]", d).onclick = () => { draftSet("pg:python", b.code); setLang("python"); location.hash = "#/playground"; };
    } else if (interactive(b)) mountExercise(d, b, () => { gate = true; bar(); refreshStats(); });
    return d;
  }
  function bar() {
    const done = gate ? shown : shown - 1;
    $("#pb").style.width = (100 * done / n) + "%";
    $("#si").textContent = gate ? `${shown} / ${n}` : "Answer the exercise to continue";
    cont.disabled = !gate;
    cont.textContent = shown >= n ? "Finish lesson (+10 XP) ✓" : "Continue ▶";
  }
  function revealNext(quiet) {
    let first = null;
    do {
      const b = l.blocks[shown], el = renderBlock(b);
      box.appendChild(el); first = first || el; shown++;
      gate = !interactive(b) || !!b.done; // an exercise you already solved doesn't block you again
      if (!(b.type === "text" && l.blocks[shown] && l.blocks[shown].type === "code")) break;
    } while (shown < n);
    bar();
    if (!quiet) {
      first.scrollIntoView({ behavior: "smooth", block: "start" });
      api(`/lessons/${id}/step`, { step: shown }).catch(() => {}); // remember where you are
    }
  }
  cont.onclick = async () => {
    if (shown < n) return revealNext();
    cont.disabled = true;
    const r = await api(`/lessons/${id}/complete`, {});
    refreshStats();
    $("#sb").outerHTML = `<div class="card paywall"><h2>🎉 Lesson complete!</h2><p>+10 XP. Exercises you answered are now in your review queue.</p>
      ${r.next ? `<a class="btn accent" href="#/lesson/${r.next}">Next lesson ▶</a>` : ""} <a class="btn" href="#/practice">Practice problems</a> <a class="btn" href="#/learn">All lessons</a></div>`;
  };
  if (l.resume > 0) {
    while (shown < l.resume && shown < n) revealNext(true); // pick up where you left off
    const last = box.lastElementChild;
    if (last) last.scrollIntoView({ block: "center" });
    toast(`Welcome back: resumed at step ${shown} of ${n}`);
  } else revealNext();
  setQuick(["Explain this like I'm 10", "Give me another example", "Quiz me on this"]);
}

async function practice() {
  const ps = await api("/problems");
  view.innerHTML = `<h1>Practice</h1><p class="muted">Tip: use the Plan box before coding. Planning in plain words is the real logic-building muscle.</p>` + [...new Set(ps.map((p) => p.level))].sort().map((lv) => `<h2>${LEVELS[lv] || "Level " + lv}</h2><div class="grid">` +
    ps.filter((p) => p.level === lv).map((p) => `<a class="item" href="#/problem/${p.slug}"><div class="t">${esc(p.title)}</div><div class="m">${"★".repeat(p.difficulty)}${"☆".repeat(5 - p.difficulty)} ${p.status === "solved" ? '<span class="badge ok">solved</span>' : p.status === "attempted" ? '<span class="badge warn">attempted</span>' : ""}<br>${p.concepts.map(esc).join(" · ")}</div></a>`).join("") + "</div>").join("");
  aiCtx = {}; setQuick(["What should I practice next?", "Explain Big-O simply"]);
}

async function problem(slug) {
  const p = await api("/problems/" + slug);
  const dk = (lg) => `draft:${slug}:${lg}`, pkey = `plan:${slug}`;
  let lang = langPref();
  view.innerHTML = `<a href="#/practice">← All problems</a><h1>${esc(p.title)} <span class="badge">${"★".repeat(p.difficulty)}</span></h1>
  <div class="split"><div class="card"><div id="stmt">${md(p.statement)}</div>
    <h4>Examples</h4>${p.samples.map((s) => `<pre>${esc(JSON.stringify(s.input))}  →  ${esc(JSON.stringify(s.expected))}</pre>`).join("")}
    <details class="plan"><summary>🧠 Plan before you code (recommended)</summary>
      <p class="muted">1. Say the problem in your own words. 2. Work one tiny example by hand. 3. Write the steps in plain English. 4. What odd inputs could break it (empty, 0, duplicates)?</p>
      <textarea id="plan" placeholder="My plan…"></textarea><div class="row"><button class="btn" id="plan-ai">✦ Review my plan</button></div></details>
    <h4>Hints (${p.hint_count})</h4><div id="hints"></div><div class="row"><button class="btn" id="hint">Show next hint</button></div>
    <div id="cx"></div></div>
  <div><div class="row"><label>Language <select id="lang">${langOptions()}</select></label><span id="lang-note" class="muted"></span></div>
    <textarea class="editor" id="code" spellcheck="false"></textarea>
    <div class="row"><button class="btn" id="run">Run examples</button><button class="btn accent" id="submit">Submit (all tests)</button><button class="btn" id="vis">Visualize my code</button><button class="btn" id="reset">Reset</button></div>
    <div id="out"></div></div></div><div id="viz" style="margin-top:16px"></div>`;
  const ta = $("#code"), out = $("#out"), hints = $("#hints"), plan = $("#plan");
  plan.value = draftGet(pkey, "");
  if (plan.value) $("details.plan").open = true;
  aiCtx = { problem: `${p.title}\n${p.statement}\nFunction: ${p.entry}`, plan: plan.value };
  const loadLang = () => {
    $("#lang").value = lang;
    ta.value = draftGet(dk(lang), p.starters[lang]);
    aiCtx.code = ta.value; aiCtx.lang = lang;
    const L = langInfo(lang), ok = L && L.available;
    $("#lang-note").innerHTML = ok ? (L.visualize ? "" : "Step-by-step visualizer is Python-only; run and submit work normally.") : `⚠ ${esc(L ? L.label : lang)} isn't installed. ${esc(L ? L.hint : "")}`;
    ["run", "submit"].forEach((id) => { $("#" + id).disabled = !ok; });
    $("#vis").disabled = !(ok && L.visualize);
    $("#vis").title = L && L.visualize ? "" : "Visualizer supports Python only";
  };
  $("#lang").onchange = () => { draftSet(dk(lang), ta.value); lang = $("#lang").value; setLang(lang); loadLang(); };
  ta.addEventListener("input", () => { draftSet(dk(lang), ta.value); aiCtx.code = ta.value; });
  plan.addEventListener("input", () => { draftSet(pkey, plan.value); aiCtx.plan = plan.value; });
  $("#plan-ai").onclick = () => askAI(plan.value.trim() ? "Please review my plan. Is it clear and complete? What am I missing? Don't write the code for me." : "I haven't written a plan yet. Ask me 2 short questions to help me start planning.");
  ta.addEventListener("keydown", (e) => { if (e.key === "Tab") { e.preventDefault(); document.execCommand("insertText", false, "    "); } });
  let shown = 0;
  const showHint = async (lv) => { const h = await api(`/problems/${slug}/hint`, { level: lv }); hints.insertAdjacentHTML("beforeend", `<div class="hint"><b>Hint ${h.level}:</b> ${esc(h.text)}</div>`); shown = lv; if (shown >= p.hint_count) $("#hint").disabled = true; };
  for (let i = 1; i <= p.hints_used; i++) await showHint(i);
  $("#hint").onclick = () => showHint(shown + 1);
  $("#reset").onclick = () => { if (confirm("Reset your code to the starter?")) { ta.value = p.starters[lang]; draftSet(dk(lang), ta.value); aiCtx.code = ta.value; } };
  const show = (r) => {
    const bad = r.verdict !== "AC";
    aiCtx.result = `${r.verdict}: ${r.passed}/${r.total} tests passed. ` + (r.error ? `${r.error.type}: ${r.error.message}` : "") + r.results.filter((x) => !x.pass && x.sample).map((x) => ` Input ${JSON.stringify(x.input)} expected ${JSON.stringify(x.expected)} got ${JSON.stringify(x.actual)}${x.error ? " error " + x.error : ""}`).join(";");
    out.innerHTML = `<div class="verdict ${bad ? "bad" : "AC"}">${r.verdict === "AC" ? "✅ Accepted" : { WA: "❌ Wrong answer", RE: "💥 Runtime error", CE: "⚠ Won't compile/run", TLE: "⏱ Too slow", NOLANG: "🧰 Language not installed" }[r.verdict] || r.verdict} · ${r.passed}/${r.total}${r.xp_gained ? ` · +${r.xp_gained} XP` : ""}</div>` +
      (r.error ? `<div class="res fail">${esc(r.error.type)}: ${esc(r.error.message)}${r.error.line ? " (line " + r.error.line + ")" : ""}</div>` : "") +
      r.results.map((x, k) => `<div class="res ${x.pass ? "pass" : "fail"}">${x.pass ? "✓" : "✗"} Test ${k + 1}${x.sample ? `: <code>${esc(JSON.stringify(x.input))}</code> expected <code>${esc(JSON.stringify(x.expected))}</code>${x.pass ? "" : ` got <code>${esc(JSON.stringify(x.actual))}</code>`}` : " (hidden)"}${x.error ? `<br><code>${esc(x.error)}</code>` : ""}</div>`).join("") +
      (bad ? `<div class="row"><button class="btn" id="why">✦ Why is it failing?</button></div>` : "") +
      (r.stdout ? `<h4>Your print output</h4><pre>${esc(r.stdout)}</pre>` : "");
    const why = $("#why"); if (why) why.onclick = () => askAI("Why is my code failing? Guide me to find the bug, don't just give the fixed code.");
    if (r.complexity) $("#cx").innerHTML = `<h4>Improve: efficiency</h4><p>Best known approach: <b>${esc(r.complexity)}</b>. Does yours match? <a href="#" id="cmp">Ask the tutor to compare</a></p>`;
    const cmp = $("#cmp"); if (cmp) cmp.onclick = (e) => { e.preventDefault(); askAI("Compare the time complexity of my solution with the best known approach, in plain words."); };
    refreshStats();
  };
  const act = (btn, kind) => async () => { btn.disabled = true; out.innerHTML = '<div class="res">Running…</div>'; try { show(await api(`/problems/${slug}/${kind}`, { code: ta.value, lang })); } catch (e) { out.innerHTML = `<div class="res fail">${esc(e.message)}</div>`; } btn.disabled = false; };
  $("#run").onclick = act($("#run"), "run");
  $("#submit").onclick = act($("#submit"), "submit");
  $("#vis").onclick = () => { aiCtx.code = ta.value; visualizeInto($("#viz"), ta.value, `/problems/${slug}/trace`); $("#viz").scrollIntoView({ behavior: "smooth" }); };
  loadLang();
  setQuick(["Give me a nudge, not the answer", "Is my approach efficient?", "Show the idiomatic way to do this in my language"]);
}

async function review() {
  const due = await api("/review/due");
  aiCtx = {};
  if (!due.length) { view.innerHTML = `<h1>Review</h1><div class="card paywall"><h2>Nothing due 🎉</h2><p>Exercises you answer in lessons come back here on a schedule (1, 3, 7, 14 days…). Revisiting just before you'd forget is the fastest way to remember.</p><a class="btn accent" href="#/learn">Go to lessons</a></div>`; return; }
  view.innerHTML = `<h1>Review</h1><div class="progress"><div class="bar-track"><div class="bar-fill" id="rp" style="width:0"></div></div></div><div id="rq" class="lesson"></div>`;
  let k = 0;
  const step = () => {
    $("#rp").style.width = (100 * k / due.length) + "%";
    if (k >= due.length) { $("#rq").innerHTML = `<div class="card paywall"><h2>Review done ✅</h2><a class="btn accent" href="#/">Home</a></div>`; refreshStats(); return; }
    const host = document.createElement("div");
    $("#rq").innerHTML = `<p class="muted">From: ${esc(due[k].lesson)} · ${k + 1} / ${due.length}</p>`;
    $("#rq").appendChild(host);
    mountExercise(host, due[k], () => { const b = document.createElement("button"); b.className = "btn accent"; b.textContent = k + 1 >= due.length ? "Finish" : "Next ▶"; b.onclick = () => { k++; step(); }; host.appendChild(b); });
  };
  step();
  setQuick(["Explain this again differently"]);
}

async function skills() {
  const sk = await api("/skills");
  const weak = sk.filter((s) => s.mastery < 0.7).sort((a, b) => a.level - b.level)[0];
  view.innerHTML = `<h1>Skill map</h1><p class="muted">Mastery blends your exercise answers and solved problems for each concept.</p>
  ${weak ? `<div class="card">🎯 <b>Next focus: ${esc(weak.concept)}</b> (${Math.round(weak.mastery * 100)}%). <a href="#/learn">Lessons</a> · <a href="#/practice">Practice</a></div>` : ""}` +
    [...new Set(sk.map((s) => s.level))].sort().map((lv) => `<h2>${LEVELS[lv] || "Level " + lv}</h2>` + sk.filter((s) => s.level === lv).map((s) =>
      `<div class="skill"><span class="t">${esc(s.concept)}</span><div class="bar-track"><div class="bar-fill" style="width:${s.mastery * 100}%"></div></div><span class="muted">${Math.round(s.mastery * 100)}% · ${s.items} item${s.items > 1 ? "s" : ""}</span></div>`).join("")).join("");
  aiCtx = {}; setQuick(["What should I strengthen first?"]);
}

async function account() {
  const p = await api("/progress");
  view.innerHTML = `<h1>Account</h1><div class="grid"><div class="card"><h4>Learner</h4><p><input id="nm" value="${esc(p.name)}" style="font:inherit;padding:4px 8px"> <button class="btn" id="sv">Save name</button></p>
    <p>Plan: <b>${p.plan === "pro" ? "Pro" : "Free"}</b> <button class="btn" id="pl">${p.plan === "pro" ? "Switch to Free" : "Upgrade to Pro (demo)"}</button></p><p class="muted">Local demo: no billing. Production: checkout + payment webhook.</p></div>
    <div class="card"><h4>Your data</h4><p>Everything is stored on this computer.</p><button class="btn" id="ex">Download my progress (JSON)</button></div></div>
    <h2>Badges</h2><div class="badges">${p.badges.map((b) => `<div class="badge-card ${b.earned ? "" : "off"}"><div class="big">${b.earned ? "🏅" : "🔒"}</div><b>${esc(b.title)}</b><div class="muted">${esc(b.desc)}</div></div>`).join("")}</div>
    <p class="muted" style="margin-top:30px"><a href="#/admin">Admin analytics</a></p>`;
  $("#sv").onclick = async () => { await api("/me", { name: $("#nm").value }); await loadUsers(); refreshStats(); toast("Saved"); };
  $("#pl").onclick = async () => { await api("/me", { plan: p.plan === "pro" ? "free" : "pro" }); await loadUsers(); refreshStats(); account(); };
  $("#ex").onclick = async () => { const d = await api("/export"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); a.download = "logicbuilder-progress.json"; a.click(); };
  aiCtx = {}; setQuick([]);
}

async function admin() {
  let s;
  try { s = await api("/admin/stats"); } catch (e) { view.innerHTML = `<div class="res fail">${esc(e.message)}</div>`; return; }
  const tbl = (head, rows) => `<table class="data"><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>${rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</table>`;
  view.innerHTML = `<h1>Admin analytics</h1><p class="muted">Local-only view. Before deploying publicly this page must sit behind authentication (see docs/03). Paywall: ${s.paywall ? "ON" : "off (set LB_PAYWALL=1)"}.</p>
  <h2>Learners</h2>${tbl(["Name", "Plan", "XP", "Lessons", "Solved", "Streak"], s.users.map((u) => [u.name, u.plan, u.xp, u.lessons, u.solved, u.streak]))}
  <h2>Lesson completion</h2>${tbl(["Lesson", "Completed by"], s.lessons.map((l) => [l.title, l.completed]))}
  <h2>Problems (where learners struggle)</h2>${tbl(["Problem", "Tried", "Solved", "Avg attempts", "Avg hints"], s.problems.map((p) => [p.title, p.learners, p.solved, p.avg_attempts, p.avg_hints]))}
  <h2>Hardest exercises</h2>${s.hardest_exercises.length ? tbl(["Lesson", "Type", "Attempts", "Accuracy"], s.hardest_exercises.map((e) => [e.lesson, e.type, e.attempts, Math.round(e.accuracy * 100) + "%"])) : "<p class='muted'>No data yet.</p>"}`;
  aiCtx = {}; setQuick([]);
}

function playground() {
  let lang = langPref();
  view.innerHTML = `<h1>Playground</h1><p>Write a complete program in any language. <b>Run</b> shows the output. For Python, <b>Visualize</b> lets you step through it (try 🎯 Predict mode).</p>
  <div class="row"><label>Language <select id="lang">${langOptions()}</select></label><span id="lang-note" class="muted"></span></div>
  <textarea class="editor" id="code" spellcheck="false"></textarea>
  <div class="row"><button class="btn" id="run">Run</button><button class="btn accent" id="vis">▶ Visualize</button></div><div id="out"></div><div id="viz"></div>`;
  const ta = $("#code");
  const pk = (lg) => `pg:${lg}`;
  const load = () => {
    const L = langInfo(lang), ok = L && L.available;
    $("#lang").value = lang;
    ta.value = draftGet(pk(lang), L ? L.template : "");
    aiCtx = { code: ta.value, lang };
    $("#lang-note").innerHTML = ok ? "" : `⚠ ${esc(L ? L.label : lang)} isn't installed. ${esc(L ? L.hint : "")}`;
    $("#run").disabled = !ok;
    $("#vis").disabled = !(ok && L.visualize);
    $("#vis").title = L && L.visualize ? "" : "Visualizer supports Python only";
    $("#out").innerHTML = ""; $("#viz").innerHTML = "";
  };
  $("#lang").onchange = () => { draftSet(pk(lang), ta.value); lang = $("#lang").value; setLang(lang); load(); };
  ta.addEventListener("input", () => { draftSet(pk(lang), ta.value); aiCtx.code = ta.value; });
  ta.addEventListener("keydown", (e) => { if (e.key === "Tab") { e.preventDefault(); document.execCommand("insertText", false, "    "); } });
  $("#run").onclick = async () => {
    $("#run").disabled = true; $("#out").innerHTML = '<div class="res">Running…</div>';
    try {
      const r = await api("/run", { code: ta.value, lang });
      aiCtx.result = `${r.verdict} ${r.error ? r.error.type + ": " + r.error.message : ""} output: ${r.stdout}`;
      $("#out").innerHTML = `<h4>Output</h4><pre>${esc(r.stdout || "(nothing printed)")}</pre>` + (r.error ? `<div class="res fail"><pre style="margin:0;white-space:pre-wrap">${esc(r.error.type)}: ${esc(r.error.message)}${r.error.line ? " (line " + r.error.line + ")" : ""}</pre></div>` : "");
    } catch (e) { $("#out").innerHTML = `<div class="res fail">${esc(e.message)}</div>`; }
    $("#run").disabled = false;
  };
  $("#vis").onclick = () => { aiCtx.code = ta.value; visualizeInto($("#viz"), ta.value); };
  load();
  setQuick(["Explain my code step by step", "Find the bug", "How can I make this shorter?"]);
}

/* ---------- languages ---------- */
let LANGS_LIST = [];
const langInfo = (id) => LANGS_LIST.find((l) => l.id === id);
function langPref() {
  const v = STATE.prefs.lang || "python";
  return langInfo(v) ? v : "python";
}
function setLang(l) { STATE.prefs.lang = l; api("/me/prefs", { lang: l }).catch(() => {}); }
const langOptions = () => LANGS_LIST.map((l) => `<option value="${l.id}">${esc(l.label)}${l.available ? "" : " (not installed)"}</option>`).join("");
async function loadLangs(refresh) {
  try { LANGS_LIST = await (await fetch("/api/languages" + (refresh ? "?refresh=1" : ""))).json(); } catch { LANGS_LIST = [{ id: "python", label: "Python", available: true, visualize: true, template: "" }]; }
}

async function languages() {
  await loadLangs(true);
  const r = await api("/rosetta");
  const name = Object.fromEntries(LANGS_LIST.map((l) => [l.id, l.label]));
  view.innerHTML = `<h1>Languages</h1><p>Solve every practice problem in the language your interviews expect. Your choice is remembered. Lessons teach concepts in Python (the clearest way to learn logic); the same logic carries over.</p>
  <h2>Installed on this computer</h2><div class="grid">${LANGS_LIST.map((l) => `<div class="card"><b>${esc(l.label)}</b> ${l.available ? '<span class="badge ok">ready</span>' : '<span class="badge warn">not installed</span>'}<div class="muted">${l.available ? (l.visualize ? "Run, submit and visualize" : "Run and submit") : esc(l.hint)}</div></div>`).join("")}</div>
  <div class="row"><button class="btn" id="rescan">↻ Re-scan after installing</button></div>
  <h2>Which language for which interview?</h2>${r.advice.map((a) => `<div class="card" style="margin:8px 0"><b>${esc(a.lang)}</b><p style="margin:4px 0">${esc(a.when)}</p><p class="muted" style="margin:0">⚠ ${esc(a.watch)}</p></div>`).join("")}
  <h2>Cheat sheet: the same idea in every language</h2>
  <div class="row"><label>Show: </label>${r.order.map((id) => `<label class="pm"><input type="checkbox" class="lg" value="${id}" ${["python", "java", "cpp"].includes(id) ? "checked" : ""}> ${esc(name[id] || id)}</label>`).join("")}</div><div id="rose"></div>`;
  const draw = () => {
    const on = [...document.querySelectorAll(".lg:checked")].map((x) => x.value);
    $("#rose").innerHTML = r.concepts.map((c) => `<div class="card" style="margin:10px 0"><b>${esc(c.title)}</b>${c.note ? `<div class="muted">${esc(c.note)}</div>` : ""}<div class="rose-grid">${on.map((id) => `<div><div class="muted">${esc(name[id] || id)}</div><pre>${esc(c.code[id] || "")}</pre></div>`).join("")}</div></div>`).join("");
  };
  document.querySelectorAll(".lg").forEach((x) => { x.onchange = draw; });
  $("#rescan").onclick = () => languages();
  draw();
  aiCtx = {}; setQuick(["Which language should I pick for my interviews?", "Translate my Python solution to Java"]);
}

/* ---------- router ---------- */
const routes = [[/^#\/?$/, home], [/^#\/learn$/, learn], [/^#\/lesson\/([\w-]+)$/, lesson], [/^#\/practice$/, practice], [/^#\/problem\/([\w-]+)$/, problem],
  [/^#\/review$/, review], [/^#\/skills$/, skills], [/^#\/account$/, account], [/^#\/admin$/, admin], [/^#\/playground$/, playground], [/^#\/languages$/, languages]];
async function route() {
  const h = location.hash || "#/";
  document.querySelectorAll(".top nav a").forEach((a) => a.classList.toggle("on", h.startsWith(a.getAttribute("href"))));
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) {
      try { await fn(...m.slice(1)); } catch (e) { view.innerHTML = `<div class="res fail">${esc(e.message)}</div>`; }
      window.scrollTo(0, 0);
      return;
    }
  }
  view.innerHTML = "<h1>Not found</h1>";
}
addEventListener("hashchange", route);

/* ---------- learners ---------- */
async function loadUsers() {
  let users = [];
  try { users = await (await fetch("/api/users")).json(); } catch { /* offline */ }
  let cur = store.get("lb-user", "");
  if (!cur) { // browser data was cleared or this is a new browser: open on whoever used the app last
    try { cur = (await (await fetch("/api/active")).json()).id; } catch { cur = "default"; }
  }
  if (!users.some((u) => u.id === cur)) cur = "default";
  store.set("lb-user", cur);
  $("#user").innerHTML = users.map((u) => `<option value="${esc(u.id)}">${esc(u.name)}</option>`).join("");
  $("#user").value = cur;
}
async function switchLearner(id) {
  await flushDrafts(); // save the previous learner's unsaved typing first
  store.set("lb-user", id);
  ai.history = [];
  await loadState();
  api("/me/active", {}).catch(() => {});
  refreshStats(); route();
}
$("#user").onchange = () => switchLearner($("#user").value);
$("#user-add").onclick = async () => {
  const name = prompt("Name of the new learner?");
  if (!name) return;
  await flushDrafts();
  const r = await api("/users", { name });
  store.set("lb-user", r.id); await loadUsers(); location.hash = "#/";
  await switchLearner(r.id);
};

/* ---------- AI tutor ---------- */
const ai = { cfg: null, history: [], busy: false };
const aiEl = $("#ai");
$("#ai-quick").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") send(e.target.textContent); });
function renderLog() {
  const log = $("#ai-log");
  log.innerHTML = ai.history.map((m) => {
    const text = m.role === "assistant" ? m.content.replace(/<think>[\s\S]*?(<\/think>|$)/g, "").trim() || "…" : m.content;
    return `<div class="msg ${m.role}">${m.role === "assistant" ? md(text) : esc(text)}</div>`;
  }).join("") || `<div class="msg assistant">Hi! I'm your tutor. Pick a model above (local via Ollama, or cloud via OpenRouter) and ask me anything. I can see your current lesson, exercise, code and test results, and I'll guide you with questions instead of just giving answers.</div>`;
  log.scrollTop = log.scrollHeight;
}
async function loadAI() {
  ai.cfg = await api("/ai/config");
  const c = ai.cfg;
  $("#ai-family").innerHTML = Object.entries(c.families).map(([id, f]) => `<option value="${id}">${esc(f.label)}</option>`).join("");
  $("#ai-family").value = c.family;
  $("#ai-provider").value = c.provider;
  updateStatus();
}
function updateStatus() {
  const c = ai.cfg, fam = $("#ai-family").value, prov = $("#ai-provider").value, model = c.families[fam][prov];
  let s = model ? `Model: ${esc(model)}` : `No ${prov} model for this family`;
  let canDownload = false;
  if (prov === "ollama") {
    if (c.ollama_installed === null) s += " · ⚠ Ollama not running. Install/start it with setup-ai (see README)";
    else if (model && (c.ollama_installed.includes(model) || c.ollama_installed.includes(model + ":latest"))) s += " · ✓ installed";
    else if (model) { s += " · not downloaded yet "; canDownload = true; }
  } else s += c.providers.openrouter.has_key ? " · ✓ key set" : " · ⚠ add API key in ⚙";
  $("#ai-status").innerHTML = s + (canDownload ? ` <button class="btn" id="dl" style="padding:1px 10px;font-size:12px">⬇ Download</button>` : "");
  if (canDownload) $("#dl").onclick = () => downloadModel(model);
}
async function downloadModel(model) {
  const st = $("#ai-status");
  const note = (t) => { st.innerHTML = `Downloading ${esc(model)}: ${t}`; };
  note("starting…");
  try {
    const r = await fetch("/api/ai/pull", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model }) });
    if (!r.ok) { note("failed"); return; }
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = "", failed = null;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n"); buf = lines.pop();
      for (const ln of lines) {
        if (!ln.trim()) continue;
        let j; try { j = JSON.parse(ln); } catch { continue; }
        if (j.error) failed = j.error;
        else if (j.total && j.completed) note(`${Math.round(100 * j.completed / j.total)}% of ${(j.total / 1e9).toFixed(1)} GB`);
        else if (j.status) note(esc(j.status));
      }
    }
    if (failed) { st.innerHTML = `⚠ ${esc(failed)}`; return; }
  } catch (e) { st.textContent = "Download interrupted: " + e.message; return; }
  ai.cfg = await api("/ai/config"); updateStatus();
}
async function saveSel() { ai.cfg = await api("/ai/config", { family: $("#ai-family").value, provider: $("#ai-provider").value }); updateStatus(); }
$("#ai-family").onchange = saveSel; $("#ai-provider").onchange = saveSel;
$("#ai-toggle").onclick = async () => { aiEl.hidden = !aiEl.hidden; if (!aiEl.hidden) { if (!ai.cfg) await loadAI(); renderLog(); } };
$("#ai-close").onclick = () => { aiEl.hidden = true; };
$("#ai-gear").onclick = () => {
  const box = $("#ai-settings");
  box.hidden = !box.hidden;
  if (box.hidden) return;
  const c = ai.cfg;
  box.innerHTML = `<b>Model ids</b> (edit to match what you have installed)` + Object.entries(c.families).map(([id, f]) => `<label>${esc(f.label)}</label><input data-fam="${id}" data-prov="ollama" placeholder="Ollama model, e.g. qwen2.5-coder:7b" value="${esc(f.ollama)}"><input data-fam="${id}" data-prov="openrouter" placeholder="OpenRouter model id" value="${esc(f.openrouter)}">`).join("") +
    `<label>OpenRouter API key (stored only in data/ai_config.json on this PC)</label><input id="or-key" type="password" placeholder="${c.providers.openrouter.has_key ? "•••• saved (type to replace)" : "sk-or-..."}">
    <label>Ollama URL</label><input id="ol-url" value="${esc(c.providers.ollama.base_url)}"><div class="row"><button class="btn accent" id="save-set">Save</button></div>`;
  $("#save-set").onclick = async () => {
    const models = {};
    box.querySelectorAll("input[data-fam]").forEach((i) => { (models[i.dataset.fam] ||= {})[i.dataset.prov] = i.value; });
    ai.cfg = await api("/ai/config", { models, providers: { openrouter: { api_key: $("#or-key").value }, ollama: { base_url: $("#ol-url").value } } });
    box.hidden = true; updateStatus();
  };
};
async function send(text) {
  text = (text || "").trim();
  if (!text || ai.busy) return;
  if (aiEl.hidden) { aiEl.hidden = false; if (!ai.cfg) await loadAI(); }
  ai.busy = true;
  ai.history.push({ role: "user", content: text });
  const reply = { role: "assistant", content: "" };
  ai.history.push(reply);
  renderLog();
  try {
    const r = await fetch("/api/ai/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: ai.history.slice(0, -1), context: aiCtx, provider: $("#ai-provider").value, family: $("#ai-family").value }) });
    const reader = r.body.getReader(), dec = new TextDecoder();
    for (;;) { const { done, value } = await reader.read(); if (done) break; reply.content += dec.decode(value, { stream: true }); renderLog(); }
  } catch (e) { reply.content += `\n[Connection error: ${e.message}]`; renderLog(); }
  ai.busy = false;
}
$("#ai-form").onsubmit = (e) => { e.preventDefault(); const t = $("#ai-input").value; $("#ai-input").value = ""; send(t); };
$("#ai-input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#ai-form").requestSubmit(); } });

/* ---------- appearance: theme + fonts (persisted, applied pre-paint by index.html) ---------- */
const root = document.documentElement;
const look = {
  theme: store.get("lb-theme", "auto"), mono: store.get("lb-mono", "geist"), head: store.get("lb-head", "oswald"), size: +store.get("lb-size", "14") || 14,
};
function applyLook(save) {
  if (look.theme === "auto") delete root.dataset.theme; else root.dataset.theme = look.theme;
  root.dataset.mono = look.mono; root.dataset.head = look.head;
  root.style.setProperty("--code-size", look.size + "px");
  $("#theme").textContent = { auto: "◐", light: "☀", dark: "☾" }[look.theme];
  $("#theme").title = `Theme: ${look.theme} (click to change)`;
  document.querySelectorAll("#seg-theme button").forEach((b) => b.classList.toggle("on", b.dataset.v === look.theme));
  $("#sel-mono").value = look.mono; $("#sel-head").value = look.head;
  $("#rng-size").value = look.size; $("#size-val").textContent = look.size;
  if (save) { store.set("lb-theme", look.theme); store.set("lb-mono", look.mono); store.set("lb-head", look.head); store.set("lb-size", String(look.size)); }
}
$("#theme").onclick = () => { look.theme = { auto: "light", light: "dark", dark: "auto" }[look.theme]; applyLook(true); };
$("#seg-theme").onclick = (e) => { if (e.target.dataset.v) { look.theme = e.target.dataset.v; applyLook(true); } };
$("#sel-mono").onchange = () => { look.mono = $("#sel-mono").value; applyLook(true); };
$("#sel-head").onchange = () => { look.head = $("#sel-head").value; applyLook(true); };
$("#rng-size").oninput = () => { look.size = +$("#rng-size").value; applyLook(true); };
$("#aa").onclick = (e) => { e.stopPropagation(); const p = $("#pop"); p.hidden = !p.hidden; $("#aa").setAttribute("aria-expanded", String(!p.hidden)); };
document.addEventListener("click", (e) => { if (!e.target.closest(".appear")) { $("#pop").hidden = true; $("#aa").setAttribute("aria-expanded", "false"); } });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#pop").hidden = true; });
applyLook(false);

loadUsers().then(() => Promise.all([loadState(), loadLangs()])).then(() => {
  api("/me/active", {}).catch(() => {});
  route(); refreshStats();
});
