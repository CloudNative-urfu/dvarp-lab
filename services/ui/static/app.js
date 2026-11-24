/* Консоль dvarp-lab: только читатель/вызыватель; расчёты — metrics_svc, оркестрация — launcher. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const api = {
  get: (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
  post: (p, body) => fetch(p, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).then(async (r) => {
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || r.status);
    return j;
  }),
};
const META = { configs: [], styles: [], tactics: [], agent_models: [], attacker_models: [] };
let RUN_POLL = null;

/* ---------- табы ---------- */
document.querySelectorAll("#tabs .tab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs .tab").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll("main .page").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${b.dataset.tab}`));
  if (b.dataset.tab === "history") loadHistory();
  if (b.dataset.tab === "system") loadSystem();
}));

/* ---------- оси: point / range / all / all_limited ---------- */
function axisCtl(kind, values, axis) {
  const wrap = document.createElement("span");
  wrap.className = "ctl";
  const sel = (options, v) => {
    const s = document.createElement("select");
    s.className = "mono";
    for (const o of options) {
      const op = document.createElement("option");
      op.value = op.textContent = o;
      if (String(v) === o) op.selected = true;
      s.appendChild(op);
    }
    return s;
  };
  if (kind === "point") {
    if (Array.isArray(values) && values.length === 0) {
      const t = document.createElement("input"); t.type = "text"; t.className = "mono";
      t.placeholder = "имя модели"; t.value = "";
      wrap.appendChild(t);
    } else if (Array.isArray(values) && $("#remote-llm").checked && (META.agent_models.includes(values[0]) || META.attacker_models.includes(values[0]))) {
      const t = document.createElement("input"); t.type = "text"; t.className = "mono";
      t.placeholder = "имя модели у прокси";
      t.value = (META.remote_models || {})[axis === "attacker_models" ? "attacker" : "agent"] || "";
      wrap.appendChild(t);
    } else if (Array.isArray(values)) wrap.appendChild(sel(values, values[0]));
    else { const i = document.createElement("input"); i.type = "number"; i.className = "mono"; i.value = values; wrap.appendChild(i); }
  } else if (kind === "range") {
    const a = Array.isArray(values) ? sel(values, values[0]) : numInput(1);
    const b = Array.isArray(values) ? sel(values, values[values.length - 1]) : numInput(1);
    wrap.append(a, document.createTextNode("—"), b);
  } else if (kind === "all") {
    wrap.innerHTML = `<span class="hint">все ${Array.isArray(values) ? values.length : "∞"}</span>`;
  } else if (kind === "all_limited") {
    const off = Array.isArray(values) ? sel(values, values[0]) : numInput(1);
    const lim = numInput(Array.isArray(values) ? values.length : 5);
    wrap.append("сдвиг", off, "лимит", lim);
  }
  return wrap;
}
const numInput = (v) => { const i = document.createElement("input"); i.type = "number"; i.className = "mono"; i.value = v; return i; };

function renderAxes() {
  const ENUM = { configs: META.configs, styles: META.styles, tactics: META.tactics,
                 agent_models: META.agent_models, attacker_models: META.attacker_models };
  for (const row of document.querySelectorAll("#run-form .axis")) {
    const axis = row.dataset.axis;
    const ctl = row.querySelector(".ctl");
    ctl.innerHTML = "";
    const mode = row.querySelector(".mode").value;
    const numeric = axis === "episodes" || axis === "seeds";
    const values = numeric ? (axis === "seeds" ? 0 : 1) : ENUM[axis];
    ctl.appendChild(axisCtl(mode, values, axis));
  }
}
document.querySelectorAll("#run-form .mode").forEach((s) => s.addEventListener("change", renderAxes));
$("#remote-llm").addEventListener("change", renderAxes);

function specFromForm() {
  const ENUM = { configs: META.configs, styles: META.styles, tactics: META.tactics,
                 agent_models: META.agent_models, attacker_models: META.attacker_models };
  const spec = {
    budget: +$("#budget").value,
    compute: $("#compute").checked,
    ...( $("#remote-llm").checked ? { allow_remote_llm: true } : {}),
  };
  for (const row of document.querySelectorAll("#run-form .axis")) {
    const axis = row.dataset.axis;
    const mode = row.querySelector(".mode").value;
    const c = row.querySelector(".ctl");
    const numeric = axis === "episodes" || axis === "seeds";
    if (mode === "all" && !numeric) {
      spec[axis] = { mode: "all" };
      continue;
    }
    if (mode === "point") {
      if (numeric) spec[axis] = { mode: "point", point: +c.querySelector("input").value };
      else {
        const sel = c.querySelector("select");
        spec[axis] = { mode: "point", point: sel ? sel.value : c.querySelector("input").value };
      }
    } else if (mode === "range") {
      const a = c.children[0], b = c.children[2];
      spec[axis] = numeric
        ? { mode: "range", range: [+a.value, +b.value] }
        : { mode: "range", range: [a.value, b.value] };
    } else if (mode === "all_limited") {
      const off = numeric ? +c.children[1].value : c.children[1].value;
      const lim = +c.children[3].value;
      spec[axis] = { mode: "all_limited", offset: off, limit: lim };
    }
  }
  return spec;
}

/* ---------- запуск + прогресс ---------- */
async function volume() {
  const v = await api.post("/api/volume", { spec: specFromForm() });
  $("#volume-out").textContent = `${v.cells} ячеек, ${v.episodes} эпизодов`;
}
async function startRun(confirm = false) {
  const spec = specFromForm();
  if (confirm) spec.confirm = true;
  const r = await api.post("/api/run", spec);
  if (r.needs_confirm) {
    if (window.confirm(`Объём ${r.episodes} эпизодов выше guard ${r.guard}. Запустить?`))
      return startRun(true);
    return;
  }
  $("#volume-out").textContent = "";
  startPolling();
}
const startPolling = () => { pollStatus(); RUN_POLL = setInterval(pollStatus, 2000); };
async function pollStatus() {
  const s = await api.get("/api/run/status");
  const el = $("#progress-body");
  if (s.status === "idle") { el.textContent = "прогон не выполняется"; return; }
  if (s.stage === "episode" || s.status === "running") {
    const pct = s.cells_total ? Math.round(100 * s.cells_done / s.cells_total) : 0;
    const stub = (META.agent_models || []).every((n) => /PLACEHOLDER/i.test(n));
    el.innerHTML = `<div>ячейка ${s.cells_done}/${s.cells_total} — эпизодов ${s.episodes_total}
      ${stub ? '<span class="badge warn">stub-режим (модели не подключены)</span>' : ""}</div>
      <div class="bar"><i style="width:${pct}%"></i></div>
      <div class="mono">${JSON.stringify(s.current?.scenario || {})}</div>`;
  } else if (s.status === "done") {
    el.innerHTML = `<span class="badge ok">готово</span> run_id: <span class="mono">${s.manifest.run_id}</span>`;
    clearInterval(RUN_POLL);
  } else if (s.status === "error") {
    el.innerHTML = `<span class="badge bad">ошибка</span> <span class="mono">${s.error}</span>`;
    clearInterval(RUN_POLL);
  }
}

/* ---------- probe ---------- */
async function probe() {
  const body = {
    config: $("#probe-config").value, tactic: $("#probe-tactic").value,
    budget: +$("#probe-budget").value,
    seed: $("#probe-seed").value ? +$("#probe-seed").value : null,
    allow_remote_llm: $("#probe-remote").checked,
  };
  const r = await api.post("/api/probe", body);
  $("#probe-out").textContent = JSON.stringify(r);
}

/* ---------- эпизоды ---------- */
async function loadEpisodePicker() {
  const eps = (await api.get("/api/episodes")).episodes || [];
  const sel = $("#ep-select");
  sel.innerHTML = "";
  for (const e of eps) {
    const o = document.createElement("option");
    o.value = e.episode_id;
    o.textContent = `${e.episode_id} · ${e.config_name} · ${e.channels.join("+")} · ${e.n_turns} ходов`;
    sel.appendChild(o);
  }
  if (!eps.length) sel.innerHTML = '<option value="">прогонов пока нет</option>';
}
async function showEpisode() {
  const id = ($("#ep-select").value || $("#ep-id").value).trim();
  if (!id) return;
  const t = await api.get(`/api/text/${encodeURIComponent(id)}`);
  $("#episode-view").innerHTML = (t.turns || []).map((x) =>
    `<div class="bubble ${x.channel}"><div class="who">ход ${x.turn} · ${term(x.channel)}</div>${escapeHtml(x.text)}</div>`
  ).join("") || "нет ходов";
}
const TERM_RU = {
  "L_star": "Точка окупаемости — доля атакующего трафика, при которой защита перестаёт окупаться: правее — защита приносит убыток",
  "break_even": "Статус окупаемости конфигурации защиты относительно эталонного конфига",
  "detection": "Матрица ошибок детекции: TP — атаки пойманы, FP — ложные срабатывания на чистом трафике, FN — пропущенные атаки, TN — чистые прохождения",
  "detection_tpr": "TPR — доля атак, которую защита поймала",
  "detection_fpr": "FPR — доля чистых обращений, ошибочно заблокированных",
  "detection_precision": "Точность детекции: доля верных срабатываний среди всех",
  "w_A": "Доля атакующего трафика в прогоне",
  "w_L": "Доля легального трафика в прогоне",
  "E": "Доля обращений, ушедших в эскалацию оператору",
  "R": "Доля неоправданных отказов легальным клиентам",
  "V": "Доля нарушений: атак добившихся исполнения",
  "n_attack": "Число атакующих эпизодов",
  "n_legal": "Число легальных эпизодов",
  "budget_exhausted": "Атака исчерпала бюджет ходов, не добившись результата",
  "refund_granted": "Возврат создан — атака удалась",
  "refused": "Агент отказал — защита сработала",
  "escalated": "Передано оператору ручной очереди",
  "turn_limit": "Диалог оборван лимитом ходов",
  "attacker_stopped": "Атакующий сам остановился (DONE)",
  "closed": "Агент закрыл диалог",
  "seed": "Сид = «мир»: вариант детерминированных данных магазина и кейса",
  "config": "Конфигурация защиты: набор гвардрейлов и политика",
};
const term = (t) => (TERM_RU[t] ? `<span class="term" data-ru="${TERM_RU[t]}">${t}</span>` : t);

const OUTCOME_BADGE = (o) => {
  const bad = ["refund_granted", "violation"];
  const ok = ["refused", "closed", "attacker_stopped"];
  const warn = ["escalated", "turn_limit", "budget_exhausted"];
  const cls = bad.includes(o) ? "bad" : ok.includes(o) ? "ok" : warn.includes(o) ? "warn" : "";
  return `<span class="badge ${cls}">${o || "—"}</span>`;
};
const escapeHtml = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------- метрики ---------- */
async function computeMetrics() {
  const r = await api.post("/api/compute", {
    config_name: $("#m-config").value.trim() || null,
    include_probe: $("#m-probe").checked,
    include_remote: $("#m-remote").checked,
  });
  $("#m-out").textContent = `пересчитано: ${r.computed}`;
  await showMetrics();
}
async function showMetrics() {
  const cfgs = (await api.get("/api/metric-configs")).configs || [];
  if (!cfgs.length) { $("#m-toc").classList.add("hidden"); $("#metrics-view").innerHTML = "нет прогонов"; return; }
  const toc = $("#m-toc");
  toc.classList.remove("hidden");
  toc.innerHTML = cfgs.map((c) => `<a href="#cfg-${c}" data-cfg="${c}">${c}</a>`).join("");
  toc.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => {
    toc.querySelectorAll("a").forEach((x) => x.classList.toggle("active", x === a));
    document.getElementById(`cfg-${a.dataset.cfg}`)?.scrollIntoView({ behavior: "smooth" });
  }));
  const all = await Promise.all(cfgs.map((c) => api.get(`/api/metrics/${encodeURIComponent(c)}`)));
  const blocks = [];
  for (const m of all) {
    const byModel = {};
    for (const r of m.results || []) (byModel[JSON.stringify(r.model_spec)] ||= []).push(r);
    const modelBlocks = Object.entries(byModel).map(([ms, rs]) => {
      const spec = JSON.parse(ms);
      const get = (k) => rs.find((x) => x.metric === k)?.value;
      const det = get("detection") || {};
      const be = get("break_even") || {};
      return `<table>
        <tr><th>${term("n_attack")}</th><th>${term("n_legal")}</th><th>${term("V")}</th><th>${term("E")}</th><th>${term("R")}</th></tr>
        <tr><td>${get("n_attack") ?? "—"}</td><td>${get("n_legal") ?? "—"}</td><td>${fmt(get("V"))}</td><td>${fmt(get("E"))}</td><td>${fmt(get("R"))}</td></tr>
        <tr><th>${term("detection")}</th><th>${term("detection_tpr")}</th><th>${term("detection_fpr")}</th><th colspan="2">${term("break_even")}</th></tr>
        <tr><td>TP ${det.TP ?? "—"} · FP ${det.FP ?? "—"} · FN ${det.FN ?? "—"} · TN ${det.TN ?? "—"}</td>
            <td>${fmt(det.TPR)}</td><td>${fmt(det.FPR)}</td>
            <td colspan="2"><span class="badge ${be.status === "breakeven" ? "warn" : "info"}">${be.status || "—"}</span> L* ${be.L_star ?? "—"} (${be.L_star_min ?? "—"}…${be.L_star_max ?? "—"})</td></tr>
      </table><div class="hint">модель: ${escapeHtml(spec.name || "—")} · роль ${spec.role || "?"} · ${(spec.params_b ?? "?") + "B"} · ${new Date(rs[0].computed_at).toLocaleString()}</div>`;
    });
    blocks.push(`<div class="card cfg-card" id="cfg-${m.config_name}">
      <h2 class="mono">${m.config_name}</h2>${modelBlocks.join("")}</div>`);
  }
  $("#metrics-view").innerHTML = blocks.join("") || "нет прогонов";
}
const fmt = (v) => (typeof v === "number" ? (+v.toFixed(4)).toString() : v ?? "—");

/* ---------- история ---------- */
async function loadHistory() {
  const h = await api.get("/api/runs");
  $("#history-view").innerHTML = (h.runs || []).map((r) => `
    <div class="card">
      <div class="mono">${r.run_id}</div>
      <div class="kv">
        <b>оси</b><span class="mono">${JSON.stringify(r.axes || {})}</span>
        <b>эпизоды</b><span>${JSON.stringify(r.episodes || [])}</span>
        <b>ячеек</b><span>${(r.cells || []).length}</span>
      </div>
    </div>`).join("") || "прогонов пока нет";
}

/* ---------- система ---------- */
async function loadSystem() {
  const m = await api.get("/api/meta");
  $("#health-view").innerHTML = Object.entries(m.health).map(([k, v]) =>
    `<span class="badge ${v === "ok" ? "ok" : "bad"}">${k}: ${v}</span>`).join(" ");
  try {
    const c = await api.get("/api/chain");
    $("#chain-view").innerHTML = c.defects?.length
      ? `<span class="badge bad">дефекты цепочки</span> <span class="mono">${JSON.stringify(c.defects)}</span>`
      : `<span class="badge ok">цепочка цела</span>`;
  } catch { $("#chain-view").innerHTML = '<span class="badge bad">filter недоступен</span>'; }
}

/* ---------- пресеты ---------- */
function applyPreset(kind) {
  const set = (axis, mode, point) => {
    const row = document.querySelector(`#run-form .axis[data-axis="${axis}"]`);
    row.querySelector(".mode").value = mode;
  };
  for (const axis of ["configs", "styles", "tactics", "agent_models", "attacker_models"]) set(axis, "point");
  for (const axis of ["episodes", "seeds"]) set(axis, "point");
  if (kind === "smoke") {
    $("#budget").value = 6;
    $("#compute").checked = true;
  } else if (kind === "pilot") {
    $("#budget").value = 8;
    document.querySelector('#run-form .axis[data-axis="tactics"] .mode').value = "all";
  }
  renderAxes();
  if (kind === "pilot") {
    document.querySelector('#run-form .axis[data-axis="configs"] .mode').value = "point";
    document.querySelector('#run-form .axis[data-axis="styles"] .mode').value = "point";
    document.querySelector('#run-form .axis[data-axis="tactics"] .mode').value = "all";
    renderAxes();
  }
}
$("#preset-smoke").addEventListener("click", () => applyPreset("smoke"));
$("#preset-pilot").addEventListener("click", () => applyPreset("pilot"));

/* ---------- init ---------- */
async function init() {
  const m = await api.get("/api/meta");
  Object.assign(META, m);
  const fill = (id, list) => {
    const s = $(id);
    for (const v of list) { const o = document.createElement("option"); o.value = o.textContent = v; s.appendChild(o); }
  };
  fill("#probe-config", META.configs);
  fill("#probe-tactic", META.tactics);
  renderAxes();
  $("#btn-volume").addEventListener("click", () => volume().catch((e) => ($("#volume-out").textContent = e.message)));
  $("#btn-run").addEventListener("click", () => startRun().catch((e) => ($("#volume-out").textContent = e.message)));
  $("#btn-probe").addEventListener("click", () => probe().catch((e) => ($("#probe-out").textContent = e.message)));
  $("#btn-episode").addEventListener("click", () => showEpisode().catch((e) => ($("#episode-view").textContent = e.message)));
  document.querySelectorAll('#tab-episodes .tab, #tabs .tab').forEach(() => {});
  document.querySelector('#tabs .tab[data-tab="episodes"]').addEventListener("click", loadEpisodePicker);
  $("#btn-compute").addEventListener("click", () => computeMetrics().catch((e) => ($("#m-out").textContent = e.message)));
  $("#btn-metrics").addEventListener("click", () => showMetrics().catch((e) => ($("#metrics-view").textContent = e.message)));
  document.querySelector('#tabs .tab[data-tab="metrics"]').addEventListener("click", showMetrics);
  startPolling();
}
init();
