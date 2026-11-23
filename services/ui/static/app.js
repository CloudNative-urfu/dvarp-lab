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
function axisCtl(kind, values) {
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
    if (Array.isArray(values) && $("#remote-llm").checked && (META.agent_models.includes(values[0]) || META.attacker_models.includes(values[0]))) {
      const t = document.createElement("input"); t.type = "text"; t.className = "mono";
      t.placeholder = "имя модели у прокси"; t.value = "openai/gpt-4o-mini";
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
    const values = numeric ? null : ENUM[axis];
    ctl.appendChild(axisCtl(mode, values));
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
const OUTCOME_BADGE = (o) => {
  const bad = ["refund_granted", "violation"];
  const ok = ["refused", "closed", "attacker_stopped"];
  const warn = ["escalated", "turn_limit", "budget_exhausted"];
  const cls = bad.includes(o) ? "bad" : ok.includes(o) ? "ok" : warn.includes(o) ? "warn" : "";
  return `<span class="badge ${cls}">${o || "—"}</span>`;
};
async function showEpisode() {
  const id = $("#ep-id").value.trim();
  if (!id) return;
  const t = await api.get(`/api/text/${encodeURIComponent(id)}`);
  $("#episode-view").innerHTML = (t.turns || []).map((x) =>
    `<div class="bubble ${x.channel}"><div class="who">ход ${x.turn} · ${x.channel}</div>${escapeHtml(x.text)}</div>`
  ).join("") || "нет ходов";
}
const escapeHtml = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------- метрики ---------- */
async function computeMetrics() {
  const r = await api.post("/api/compute", { config_name: $("#m-config").value.trim(), include_probe: $("#m-probe").checked });
  $("#m-out").textContent = `пересчитано: ${r.computed}`;
  await showMetrics();
}
async function showMetrics() {
  const m = await api.get(`/api/metrics/${encodeURIComponent($("#m-config").value.trim())}`);
  const byModel = {};
  for (const r of m.results || []) (byModel[JSON.stringify(r.model_spec)] ||= []).push(r);
  const rows = [];
  for (const [ms, rs] of Object.entries(byModel)) {
    const spec = JSON.parse(ms);
    rows.push(`<tr><th colspan="4">модель: ${escapeHtml(spec.name || "—")} (${spec.role || "?"}, ${spec.params_b || "?"}B)</th></tr>`);
    for (const r of rs) {
      let v = r.value;
      if (r.metric === "detection") v = `TP ${v.TP} · FP ${v.FP} · FN ${v.FN} · TN ${v.TN} (TPR ${(v.TPR * 100).toFixed(0)}%)`;
      if (r.metric === "break_even") v = `<span class="badge ${v.status === "breakeven" ? "warn" : "info"}">${v.status}</span> L*=${v.L_star ?? "—"}`;
      if (typeof v === "number") v = (+v.toFixed(4)).toString();
      if (v === null) v = "—";
      rows.push(`<tr><td>${r.metric}</td><td>${v}</td><td class="mono">${new Date(r.computed_at).toLocaleTimeString()}</td></tr>`);
    }
  }
  $("#metrics-view").innerHTML = rows.length ? `<table>${rows.join("")}</table>` : "нет данных";
}

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
  $("#btn-compute").addEventListener("click", () => computeMetrics().catch((e) => ($("#m-out").textContent = e.message)));
  $("#btn-metrics").addEventListener("click", () => showMetrics().catch((e) => ($("#metrics-view").textContent = e.message)));
  startPolling();
}
init();
