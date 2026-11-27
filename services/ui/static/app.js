/* Консоль dvarp-lab: только рисует. Оси, поля, пресеты и словарь терминов приходят из
   /api/meta; запуск, расчёт и трейс - вызовы /api/*. Расчётов и оркестрации здесь нет. */
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
    <button ref="btn" type="button" class="pick-btn mono" :aria-label="label" aria-haspopup="listbox" :aria-expanded="open"
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

const Outcome = {
  props: { o: String, terms: Object },
  computed: {
    cls() {
      if (["refund_granted", "violation"].includes(this.o)) return "bad";
      if (["refused", "closed", "attacker_stopped"].includes(this.o)) return "ok";
      if (["escalated", "turn_limit", "budget_exhausted"].includes(this.o)) return "warn";
      return "";
    },
  },
  template: `<span class="badge" :class="cls" :title="terms ? terms[o] : null">{{ o || "?" }}</span>`,
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

const RunStatus = {
  props: { s: Object, terms: Object },
  computed: { pct() { return this.s.cells_total ? Math.round((100 * this.s.cells_done) / this.s.cells_total) : 0; } },
  template: `<div>
    <p v-if="!s.status || s.status === 'idle'" class="hint">прогон не выполняется</p>
    <template v-else-if="s.status === 'running'">
      <div>ячейка {{ s.cells_done || 0 }}/{{ s.cells_total || "?" }}, эпизодов {{ s.episodes_total || "?" }} <span class="mono hint">{{ s.run_id }}</span></div>
      <div class="bar" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100"><i :style="{width: pct + '%'}"></i></div>
      <div v-if="s.current" class="mono hint">{{ s.current.config }} · {{ s.current.scenario.style }} · {{ s.current.scenario.tactic }} · сид {{ s.current.seed }}</div>
    </template>
    <p v-else-if="s.status === 'done'"><span class="badge ok">готово</span> <span class="mono">{{ s.manifest.run_id }}</span></p>
    <p v-else-if="s.status === 'error'"><span class="badge bad">ошибка</span> <span class="mono">{{ s.error }}</span></p>
  </div>`,
};

/* ---------- приложение ---------- */
const app = createApp({
  data: () => ({
    tabs: [
      { id: "run", label: "Запуск" }, { id: "runs", label: "Прогоны" }, { id: "trace", label: "Трейс" },
      { id: "metrics", label: "Метрики" }, { id: "system", label: "Система" },
    ],
    tab: "run",
    meta: { terms: {} },
    spec: {},
    probeSpec: {},
    volumeText: "",
    probeOut: "",
    status: { status: "idle" },
    runs: [],
    runDetail: null,
    episodes: [],
    episodePick: "",
    trace: [],
    models: [],
    mf: { config_name: null, model_spec: null, include_probe: false, include_remote: false },
    metricGroups: [],
    metricsNote: "",
    health: {},
    chain: null,
    error: "",
    timer: null,
  }),
  computed: {
    cellCols: () => ["config", "style", "tactic", "seed", "agent_models", "attacker_models"],
    episodeOptions() {
      return this.episodes.map((e) => ({ value: e.episode_id, label: `${e.episode_id} · ${e.config_name} · ${e.channels.join("+")} · ${e.n_turns} ходов` }));
    },
    configOptions() { return [{ value: null, label: "все" }, ...this.meta.axes[0].universe]; },
    modelOptions() { return [{ value: null, label: "все" }, ...this.models.map((m) => ({ value: m, label: `${m.name} · ${m.role} · ${m.revision}` }))]; },
  },
  methods: {
    guard(p) { this.error = ""; return p.catch((e) => { this.error = e.message; }); },
    open(id) {
      this.tab = id;
      if (id === "runs") this.guard(this.loadRuns());
      if (id === "trace") this.guard(this.loadEpisodes());
      if (id === "metrics") this.guard(Promise.all([this.loadModels(), this.loadStored()]));
      if (id === "system") this.guard(this.loadSystem());
    },
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
    applyPreset(p) { this.fill(p.spec); this.volumeText = `пресет: ${p.label}`; },
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
      return this.guard(api.post("/api/volume", { spec: this.payload() }).then((v) => { this.volumeText = `${v.cells} ячеек, ${v.episodes} эпизодов`; }));
    },
    run(confirm) {
      const body = { ...this.payload(), ...(confirm ? { confirm: true } : {}) };
      return this.guard(api.post("/api/run", body).then((r) => {
        if (r.needs_confirm) {
          if (window.confirm(`Объём ${r.episodes} эпизодов выше guard ${r.guard}. Запустить?`)) return this.run(true);
          return null;
        }
        this.volumeText = `запущено: ${r.episodes} эпизодов`;
        this.poll();
        this.open("runs");
        return null;
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
      if (this.status.status === "running") this.timer = setTimeout(() => this.poll(), 2000);
      else if (this.status.status === "done" && this.tab === "runs") this.loadRuns();
    },
    async loadRuns() { this.runs = (await api.get("/api/runs")).runs || []; },
    async openRun(id) { this.runDetail = await this.guard(api.get(`/api/runs/${encodeURIComponent(id)}`)) || null; },
    async loadEpisodes() { this.episodes = (await api.get("/api/episodes")).episodes || []; },
    openPair(e) {
      const legs = [];
      if (e.legal_episode_id) legs.push({ id: e.legal_episode_id, channel: e.attack_episode_id ? "legal" : "", outcome: e.legal && e.legal.outcome });
      if (e.attack_episode_id) legs.push({ id: e.attack_episode_id, channel: "attack", outcome: e.attack && e.attack.outcome });
      this.tab = "trace";
      return this.guard(Promise.all(legs.map((l) => api.get(`/api/dialog/${encodeURIComponent(l.id)}`).then((t) => ({ ...l, episode_id: l.id, lines: t.lines || [] }))))
        .then((t) => { this.trace = t; }));
    },
    async loadModels() { this.models = (await api.get("/api/metric-models")).models || []; },
    filters() {
      return { config_name: this.mf.config_name, model_spec: this.mf.model_spec, include_probe: this.mf.include_probe, include_remote: this.mf.include_remote };
    },
    compute(persist) {
      if (persist) {
        return this.guard(api.post("/api/compute", this.filters()).then((r) => { this.metricsNote = `сохранено строк: ${r.computed}`; return this.loadStored(); }));
      }
      return this.guard(api.post("/api/preview", this.filters()).then((r) => {
        this.metricsNote = `рассчитано без сохранения: ${r.groups.length} групп`;
        this.metricGroups = r.groups.map((g) => ({ ...g, key: g.config_name + JSON.stringify(g.model_spec) + g.mode, ephemeral: true }));
      }));
    },
    async loadStored() {
      const cfgs = (await api.get("/api/metric-configs")).configs || [];
      const all = await Promise.all(cfgs.map((c) => api.get(`/api/metrics/${encodeURIComponent(c)}`)));
      this.metricGroups = all.flatMap((m) => m.groups || []).map((g) => ({ ...g, key: g.config_name + JSON.stringify(g.model_spec) + g.mode }));
      this.metricsNote = this.metricGroups.length ? "сохранённые результаты" : "сохранённых результатов нет";
    },
    async loadSystem() {
      this.health = (await api.get("/api/meta")).health;
      this.chain = await api.get("/api/chain").catch(() => ({ error: true }));
    },
  },
  async mounted() {
    await this.guard(api.get("/api/meta").then((m) => {
      this.meta = m;
      this.fill({});
      for (const f of m.probe_fields) this.probeSpec[f.name] = f.default;
    }));
    this.poll();
  },
});
app.component("pick", Pick);
app.component("term-label", TermLabel);
app.component("outcome", Outcome);
app.component("value-view", ValueView);
app.component("axis-control", AxisControl);
app.component("field-control", FieldControl);
app.component("run-status", RunStatus);
app.mount("#app");
