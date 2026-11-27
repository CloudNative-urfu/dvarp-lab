/* Консоль dvarp-lab: только рисует. Оси, поля, пресеты, подписи и словарь терминов приходят из
   /api/meta; результаты, пары, запуск и диалоги - вызовы /api/*. Расчётов и оркестрации здесь нет. */
"use strict";

const { createApp, reactive } = Vue;

const api = {
  async get(p) {
    const r = await fetch(p);
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `${p}: ${r.status}`);
    return j;
  },
  async post(p, body) {
    const r = await fetch(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `${p}: ${r.status}`);
    return j;
  },
};

// Ключи спецификации оси для каждого режима (формат launcher.axes); прочее состояние формы не отправляется.
const MODE_KEYS = { point: ["point"], range: ["range"], set: ["values"], all: ["split"], all_limited: ["offset", "limit"] };
const asOptions = (list) => list.map((o) => (o !== null && typeof o === "object" && "value" in o ? o : { value: o, label: String(o) }));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* ---------- выпадающий список (listbox) с клавиатурой ---------- */
const Pick = {
  props: { modelValue: null, options: Array, label: String, terms: Object },
  emits: ["update:modelValue"],
  data: () => ({ open: false, active: 0 }),
  computed: {
    opts() { return asOptions(this.options || []); },
    current() { return this.opts.find((o) => same(o.value, this.modelValue)); },
  },
  methods: {
    toggle() {
      this.open = !this.open;
      this.active = Math.max(0, this.opts.findIndex((o) => same(o.value, this.modelValue)));
    },
    choose(o) { this.$emit("update:modelValue", o.value); this.open = false; this.$refs.btn.focus(); },
    key(e) {
      if (!this.open && ["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); this.toggle(); return; }
      if (!this.open) return;
      if (e.key === "ArrowDown") { e.preventDefault(); this.active = Math.min(this.opts.length - 1, this.active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); this.active = Math.max(0, this.active - 1); }
      else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (this.opts[this.active]) this.choose(this.opts[this.active]); }
      else if (e.key === "Escape" || e.key === "Tab") this.open = false;
    },
  },
  template: `<span class="pick" @focusout="(e) => { if (!$el.contains(e.relatedTarget)) open = false }">
    <button ref="btn" type="button" class="pick-btn" :aria-label="label" aria-haspopup="listbox" :aria-expanded="open"
      :title="terms && current ? terms[current.value] : null" @click="toggle" @keydown="key">
      {{ current ? current.label : (label || "выбрать") }}<span class="caret" aria-hidden="true"></span></button>
    <ul v-if="open" class="pick-list" role="listbox" :aria-label="label">
      <li v-for="(o, i) in opts" :key="i" role="option" tabindex="-1" :aria-selected="same(o.value, modelValue)"
        :class="{active: i === active}" :title="terms ? terms[o.value] : null" @mousedown.prevent="choose(o)" @mouseenter="active = i">{{ o.label }}</li>
      <li v-if="!opts.length" class="hint">пусто</li>
    </ul></span>`,
  setup: () => ({ same }),
};

/* ---------- термин с тултипом из словаря бэкенда ---------- */
const TermLabel = {
  props: { k: String, terms: Object },
  template: `<span v-if="terms && terms[k]" class="term" tabindex="0" :data-ru="terms[k]" :aria-label="terms[k]"><slot>{{ k }}</slot></span><span v-else><slot>{{ k }}</slot></span>`,
};

/* ---------- значение любой формы: число, строка, список, словарь (рекурсивно) ---------- */
const ValueView = {
  name: "value-view",
  props: { v: null, terms: Object },
  methods: {
    fmt(x) { return typeof x === "number" ? String(+x.toFixed(4)) : x === null || x === undefined ? "нет" : String(x); },
    isObj(x) { return x !== null && typeof x === "object" && !Array.isArray(x); },
    isScalarList(x) { return Array.isArray(x) && x.every((y) => y === null || typeof y !== "object"); },
  },
  template: `<div v-if="isObj(v)" class="kv">
      <template v-for="(val, key) in v" :key="key">
        <b><term-label :k="String(key)" :terms="terms"></term-label></b>
        <value-view :v="val" :terms="terms"></value-view>
      </template>
    </div>
    <span v-else-if="isScalarList(v)" class="mono">{{ v.length ? v.map(fmt).join(", ") : "пусто" }}</span>
    <div v-else-if="Array.isArray(v)"><value-view v-for="(x, i) in v" :key="i" :v="x" :terms="terms"></value-view></div>
    <span v-else class="mono"><term-label v-if="typeof v === 'string'" :k="v" :terms="terms"></term-label><template v-else>{{ fmt(v) }}</template></span>`,
};

/* ---------- контрол оси по режиму ---------- */
const AxisControl = {
  props: { axis: Object, value: Object, terms: Object },
  computed: {
    enumAxis() { return this.axis.kind === "enum"; },
    indexOptions() { return (this.axis.universe || []).map((v, i) => ({ value: i, label: `${i}: ${v}` })); },
  },
  methods: {
    toggleValue(v) {
      const vals = this.value.values || (this.value.values = []);
      const i = vals.indexOf(v);
      if (i >= 0) vals.splice(i, 1); else vals.push(v);
    },
    setFree(text) { this.value.values = text.split(",").map((s) => s.trim()).filter(Boolean).map((s) => (this.enumAxis ? s : +s)); },
  },
  template: `<span class="ctl">
    <template v-if="value.mode === 'point'">
      <template v-if="enumAxis">
        <pick v-model="value.point" :options="axis.universe" :label="axis.label" :terms="terms"></pick>
        <input v-if="axis.free" class="mono" placeholder="или имя вне ростера" :aria-label="axis.label + ': имя вне ростера'" @change="(e) => e.target.value && (value.point = e.target.value.trim())">
      </template>
      <input v-else type="number" min="0" class="mono num" v-model.number="value.point" :aria-label="axis.label">
    </template>
    <template v-else-if="value.mode === 'range'">
      <template v-if="enumAxis">
        <pick v-model="value.range[0]" :options="axis.universe" :label="axis.label + ': от'"></pick> -
        <pick v-model="value.range[1]" :options="axis.universe" :label="axis.label + ': до'"></pick>
      </template>
      <template v-else>
        <input type="number" min="0" class="mono num" v-model.number="value.range[0]" :aria-label="axis.label + ': от'"> -
        <input type="number" min="0" class="mono num" v-model.number="value.range[1]" :aria-label="axis.label + ': до'">
      </template>
    </template>
    <template v-else-if="value.mode === 'set'">
      <template v-if="enumAxis">
        <label v-for="u in axis.universe" :key="u" class="chip" :class="{on: (value.values || []).includes(u)}" :title="terms[u]">
          <input type="checkbox" :checked="(value.values || []).includes(u)" @change="toggleValue(u)"> {{ u }}</label>
      </template>
      <input v-if="!enumAxis || axis.free" class="mono" :placeholder="enumAxis ? 'имена через запятую' : '0, 1, 5'"
        :aria-label="axis.label + ': список'" :value="(value.values || []).join(', ')" @change="(e) => setFree(e.target.value)">
    </template>
    <template v-else-if="value.mode === 'all'">
      <span class="hint">все {{ enumAxis ? axis.universe.length : "" }}</span>
      <pick v-if="axis.splits" v-model="value.split" :options="[{value: undefined, label: 'весь корпус'}, ...axis.splits]" label="split" :terms="terms"></pick>
    </template>
    <template v-else-if="value.mode === 'all_limited'">
      <span class="hint">сдвиг</span>
      <pick v-if="enumAxis" v-model="value.offset" :options="indexOptions" :label="axis.label + ': сдвиг'"></pick>
      <input v-else type="number" min="0" class="mono num" v-model.number="value.offset" :aria-label="axis.label + ': сдвиг'">
      <span class="hint">лимит</span>
      <input type="number" min="1" class="mono num" v-model.number="value.limit" :aria-label="axis.label + ': лимит'">
    </template>
  </span>`,
};

/* ---------- поле формы по описанию ---------- */
const FieldControl = {
  props: { field: Object, model: Object, terms: Object },
  template: `<label :class="{check: field.type === 'bool'}">
    <template v-if="field.type === 'bool'"><input type="checkbox" v-model="model[field.name]"> <term-label :k="field.name" :terms="terms">{{ field.label }}</term-label></template>
    <template v-else>
      <term-label :k="field.name" :terms="terms">{{ field.label }}</term-label>
      <span v-if="field.type === 'select'" class="ctl">
        <pick v-model="model[field.name]" :options="field.options.map((o) => ({value: o, label: o === '' ? 'нет' : o}))" :label="field.label" :terms="terms"></pick>
        <input v-if="field.free" class="mono" placeholder="или имя вне ростера" :aria-label="field.label + ': имя вне ростера'" @change="(e) => e.target.value && (model[field.name] = e.target.value.trim())">
      </span>
      <input v-else-if="field.type === 'int'" type="number" class="mono num" :min="field.min" v-model.number="model[field.name]">
      <input v-else class="mono" v-model="model[field.name]">
    </template>
  </label>`,
};

/* ---------- значок lucide (inline SVG, currentColor) ---------- */
const Icon = {
  props: { name: String },
  template: `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
    <path v-if="name === 'ok'" d="M20 6 9 17l-5-5"/>
    <g v-else-if="name === 'bad'"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></g>
    <g v-else-if="name === 'warn'"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></g>
    <path v-else-if="name === 'back'" d="m15 18-6-6 6-6"/>
    <path v-else d="M5 12h14"/></svg>`,
};

const pct = (x) => (typeof x === "number" ? `${(100 * x).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} %` : "нет данных");
const money = (x) => (typeof x === "number" ? x.toLocaleString("ru-RU", { maximumFractionDigits: 1 }) : "?");
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  return m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many;
};

/* ---------- исход ноги: значок и подпись, тон не единственный носитель смысла ---------- */
const Verdict = {
  props: { leg: String, o: String, outcomes: Object },
  computed: {
    d() { return ((this.outcomes || {})[this.leg] || {})[this.o] || { label: this.o || "нет данных", tone: "" }; },
  },
  template: `<span class="badge" :class="d.tone" :title="o"><icon :name="d.tone || 'none'"></icon>{{ d.label }}</span>`,
};

/* ---------- доля: число и полоска ---------- */
const MeterBar = {
  props: { v: null, tone: String },
  computed: { w() { return typeof this.v === "number" ? `${Math.min(100, Math.max(0, 100 * this.v))}%` : "0"; } },
  setup: () => ({ pct }),
  template: `<span class="meter"><span class="meter-v mono">{{ pct(v) }}</span><span class="meter-track" aria-hidden="true"><i :class="tone" :style="{width: w}"></i></span></span>`,
};

const RunStatus = {
  props: { s: Object },
  computed: { pct() { return this.s.cells_total ? Math.round((100 * this.s.cells_done) / this.s.cells_total) : 0; } },
  template: `<div class="run-status">
    <template v-if="s.status === 'running'">
      <div>Идёт прогон<template v-if="s.cells_total">: ячейка {{ s.cells_done || 0 }} из {{ s.cells_total }}</template> <span class="mono hint">{{ s.run_id }}</span></div>
      <div class="bar" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100"><i :style="{width: pct + '%'}"></i></div>
    </template>
    <p v-else-if="s.status === 'done'"><span class="badge ok"><icon name="ok"></icon>готово</span> <span class="mono">{{ s.manifest.run_id }}</span></p>
    <p v-else-if="s.status === 'error'"><span class="badge bad"><icon name="bad"></icon>ошибка</span> <span class="mono">{{ s.error }}</span></p>
  </div>`,
};

/* ---------- приложение ---------- */
const app = createApp({
  data: () => ({
    tabs: [
      { id: "results", label: "Результаты" }, { id: "dialogs", label: "Диалоги" },
      { id: "run", label: "Запуск" }, { id: "system", label: "Система" },
    ],
    tab: "results",
    meta: { terms: {}, labels: {} },
    spec: {},
    probeSpec: {},
    volumeText: "",
    probeOut: "",
    status: { status: "idle" },
    rows: [],
    summaryLoaded: false,
    model: null,
    openKey: null,
    withRemote: true,
    busy: false,
    resultsNote: "",
    df: { config: null, attack: null, run_id: null },
    limit: 100,
    pairsRes: { total: 0, pairs: [], configs: [], runs: [] },
    pair: null,
    trace: [],
    health: {},
    chain: null,
    error: "",
    timer: null,
  }),
  computed: {
    L() { return this.meta.labels || {}; },
    healthTotal() { return Object.keys(this.meta.health || {}).length; },
    healthUp() { return Object.values(this.meta.health || {}).filter((v) => v === "ok").length; },
    healthOk() { return this.healthTotal > 0 && this.healthUp === this.healthTotal; },
    modelOptions() {
      const seen = new Map();
      for (const g of this.rows) seen.set(JSON.stringify(g.model_spec), g.model_spec);
      return [...seen].map(([k, m]) => ({ value: k, label: m.name }));
    },
    shownRows() {
      const order = this.meta.axes ? this.meta.axes[0].universe : [];
      const rows = this.rows.filter((g) => JSON.stringify(g.model_spec) === this.model);
      const ref = rows.find((g) => g.config_name === "g0");
      // сначала строки с тем же набором атак, что у эталона; несопоставимые - в конце
      const rank = (g) => (ref && g.final.n_attack !== ref.final.n_attack ? 1 : 0);
      return rows.sort((a, b) => rank(a) - rank(b) || order.indexOf(a.config_name) - order.indexOf(b.config_name));
    },
    shownRemote() { return this.shownRows.some((g) => g.mode === "remote"); },
    dConfigOptions() { return [{ value: null, label: "все" }, ...this.pairsRes.configs.map((c) => ({ value: c, label: `${this.cfgLabel(c)} (${c})` }))]; },
    attackOptions() {
      const o = (this.L.outcomes || {}).attack || {};
      return [{ value: null, label: "любой" }, ...Object.keys(o).map((k) => ({ value: k, label: o[k].label }))];
    },
    runOptions() { return [{ value: null, label: "все прогоны" }, ...this.pairsRes.runs.map((r) => ({ value: r, label: r }))]; },
    pairsNote() {
      const { total, pairs } = this.pairsRes;
      if (!total) return "Пар с такими условиями нет.";
      const head = `Найдено ${total} ${plural(total, "пара", "пары", "пар")}`;
      return total > pairs.length ? `${head}, показаны первые ${pairs.length}.` : `${head}.`;
    },
    simpleFields() {
      if (!this.meta.axes) return [];
      const uni = Object.fromEntries(this.meta.axes.map((a) => [a.name, a.universe || []]));
      return [
        { axis: "configs", label: "Защита", options: uni.configs.map((v) => ({ value: v, label: `${this.cfgLabel(v)} (${v})` })), about: (v) => this.cfgAbout(v) },
        { axis: "goals", label: "Чего добивается атакующий", options: uni.goals.map((v) => ({ value: v, label: this.goalLabel(v) })), about: (v) => `Код цели: ${v}.` },
        { axis: "tactics", label: "Как давит", options: uni.tactics, about: (v) => (this.L.tactics || {})[v] || "" },
      ];
    },
    modelLine() {
      const m = this.meta.remote_models || {};
      return m.agent
        ? `Модель агента: ${m.agent}, модель атакующего: ${m.attacker || "та же"}.`
        : "Модели не подключены: вместо LLM работает заглушка, прогон займёт секунды. Модели задаются переменными окружения (README).";
    },
  },
  watch: {
    df: { deep: true, handler() { this.limit = 100; this.guard(this.loadPairs()); } },
    spec: { deep: true, handler() { if (this.meta.axes) this.volume(); } },
  },
  methods: {
    pct, money,
    guard(p) { this.error = ""; return p.catch((e) => { this.error = e.message; }); },
    cfgLabel(c) { return ((this.L.configs || {})[c] || {}).label || c; },
    cfgAbout(c) { return ((this.L.configs || {})[c] || {}).about || ""; },
    goalLabel(g) { return (this.L.goals || {})[g] || g; },
    open(id) {
      this.tab = id;
      if (id === "results") this.guard(this.loadSummary());
      if (id === "dialogs") this.guard(this.loadPairs());
      if (id === "system") this.guard(this.loadSystem());
    },
    rowKey(g) { return g.config_name + JSON.stringify(g.model_spec) + g.mode; },
    // разный знаменатель атак с эталоном g0 той же модели: доли и L* несопоставимы
    otherSet(g) {
      const ref = this.shownRows.find((r) => r.config_name === "g0");
      return ref && g !== ref && ref.final.n_attack !== g.final.n_attack;
    },
    toggleRow(g) { this.openKey = this.openKey === this.rowKey(g) ? null : this.rowKey(g); },
    breakEven(g) {
      const t = (this.L.break_even || {})[g.final.break_even_status];
      return t ? t.replace("{L}", money(g.final.L_star)) : "нет данных";
    },
    async loadSummary() {
      this.rows = (await api.get("/api/summary")).rows || [];
      this.summaryLoaded = true;
      if (!this.modelOptions.some((o) => o.value === this.model)) this.model = this.modelOptions.length ? this.modelOptions[0].value : null;
    },
    recompute() {
      this.busy = true;
      this.resultsNote = "";
      return this.guard(api.post("/api/compute", { config_name: null, model_spec: null, include_probe: false, include_remote: this.withRemote })
        .then((r) => { this.resultsNote = `Пересчитано, сохранено строк: ${r.computed}.`; return this.loadSummary(); }))
        .finally(() => { this.busy = false; });
    },
    async loadPairs() {
      const q = new URLSearchParams({ limit: this.limit });
      for (const [k, v] of Object.entries(this.df)) if (v) q.set(k, v);
      this.pairsRes = await api.get(`/api/pairs?${q}`);
    },
    morePairs() { this.limit += 100; return this.guard(this.loadPairs()); },
    openPair(p) {
      this.pair = p;
      const legs = [
        { id: p.legal_episode_id, channel: "legal", outcome: p.legal && p.legal.outcome },
        { id: p.attack_episode_id, channel: "attack", outcome: p.attack && p.attack.outcome },
      ].filter((l) => l.id);
      this.trace = [];
      window.scrollTo(0, 0);
      return this.guard(Promise.all(legs.map((l) => api.get(`/api/dialog/${encodeURIComponent(l.id)}`).then((t) => ({ ...l, episode_id: l.id, lines: t.lines || [] }))))
        .then((t) => { this.trace = t; }));
    },
    showRun(runId) { this.pair = null; this.df.run_id = runId; this.open("dialogs"); },
    fill(spec) {
      // состояние формы = спецификация осей + запасные ключи всех режимов, чтобы переключение режима не теряло значений
      for (const a of this.meta.axes) {
        const d = spec[a.name] || a.default;
        const first = a.kind === "enum" ? a.universe[0] : d.point;
        const last = a.kind === "enum" ? a.universe[a.universe.length - 1] : d.point;
        this.spec[a.name] = reactive({ point: first, range: [first, last], values: [], offset: 0, limit: 1, ...d });
      }
      for (const f of this.meta.run_fields) this.spec[f.name] = f.name in spec ? spec[f.name] : f.default;
    },
    applyPreset(p) { this.fill(p.spec); },
    payload() {
      const out = {};
      for (const a of this.meta.axes) {
        const v = this.spec[a.name];
        out[a.name] = { mode: v.mode };
        for (const k of MODE_KEYS[v.mode]) if (v[k] !== undefined) out[a.name][k] = v[k];
      }
      for (const f of this.meta.run_fields) out[f.name] = this.spec[f.name];
      return out;
    },
    volume() {
      return api.post("/api/volume", { spec: this.payload() })
        .then((v) => { this.volumeText = `Будет ${v.episodes} ${plural(v.episodes, "пара", "пары", "пар")} диалогов в ${v.cells} ${plural(v.cells, "ячейке", "ячейках", "ячейках")}.`; })
        .catch((e) => { this.volumeText = `Настройки не сходятся: ${e.message}`; });
    },
    run(confirm) {
      const body = { ...this.payload(), ...(confirm ? { confirm: true } : {}) };
      return this.guard(api.post("/api/run", body).then((r) => {
        if (r.needs_confirm) {
          if (window.confirm(`Объём ${r.episodes} эпизодов выше порога ${r.guard}. Запустить?`)) return this.run(true);
          return null;
        }
        this.volumeText = `Запущено: ${r.episodes} ${plural(r.episodes, "пара", "пары", "пар")}.`;
        return this.poll();
      }));
    },
    probe() {
      const body = {};
      for (const f of this.meta.probe_fields) {
        const v = this.probeSpec[f.name];
        body[f.name] = v === "" || v === undefined ? null : v;
      }
      return this.guard(api.post("/api/probe", body).then((r) => { this.probeOut = JSON.stringify(r); }));
    },
    async poll() {
      clearTimeout(this.timer);
      this.status = await api.get("/api/run/status").catch(() => this.status);
      if (this.status.status === "running") this.timer = setTimeout(() => this.poll(), 1000);
    },
    async loadSystem() {
      this.meta.health = this.health = (await api.get("/api/meta")).health;
      this.chain = await api.get("/api/chain").catch(() => ({ error: true }));
    },
  },
  async mounted() {
    await this.guard(api.get("/api/meta").then((m) => {
      this.meta = m;
      this.health = m.health;
      this.fill({});
      for (const f of m.probe_fields) this.probeSpec[f.name] = f.default;
    }));
    this.poll();
    this.open("results");
  },
});
app.component("pick", Pick);
app.component("term-label", TermLabel);
app.component("icon", Icon);
app.component("verdict", Verdict);
app.component("meter-bar", MeterBar);
app.component("value-view", ValueView);
app.component("axis-control", AxisControl);
app.component("field-control", FieldControl);
app.component("run-status", RunStatus);
app.mount("#app");
