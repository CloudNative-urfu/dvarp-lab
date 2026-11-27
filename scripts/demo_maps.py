"""Демо-карты метрик dvarp-lab: SVG без зависимостей, рендер снаружи сервисов.

Читает `/metrics/{config}` metrics_svc (JSON-строки config × model_spec × metric)
и рисует пять карт в каталог вывода (по умолчанию `runs/dev/demo/`):

1. `map_config_metric.svg` — конфигурация × метрика (V, R, E, G-τ, C_ep, C_guard,
   TPR/FPR); «плохие» метрики инвертированы (меньше = зеленее);
2. `map_breakeven.svg` — L* и решения по цене пропуска L_viol {50, 500, 5000}
   (зелёный — окупается, красный — нет, жёлтый — зависит от цен);
3. `map_real_frame.svg` — L* реального фрейма по сценариям p_att (фрейм A);
4. `map_gtau.svg` — G-τ полосками с Wilson 95% CI и порогом 5%;
5. `map_pareto.svg` — защита (V) ↔ вред честным (R + G-τ), пузырь = C_ep;
6. `index.html` + `metrics_dump.json` — оглавление и сырые числа.

Запуск: `python3 scripts/demo_maps.py [--out runs/dev/demo] [--metrics-url URL]`.
Сервисы не требуются, если указан `--metrics-url`; для remote-прогонов сначала
`POST /compute {"include_remote": true}`. Скрипт — инструмент показа, в измерительный
путь не входит (сбор ≠ расчёт не затронут); рендер без зависимостей — чистый SVG.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

METRICS = ("V", "R", "E", "G_tau_rate", "C_ep", "C_guard", "detection_tpr", "detection_fpr")
BAD_METRICS = frozenset({"V", "R", "E", "G_tau_rate"})  # меньше = лучше
L_VIOLS = ("50", "500", "5000")
MAPS = (
    "map_config_metric.svg",
    "map_breakeven.svg",
    "map_real_frame.svg",
    "map_gtau.svg",
    "map_pareto.svg",
)


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def rows_by_config(base: str) -> dict[str, dict]:
    """(config/model/role) → {metric: value}; группы моделей не схлопываются."""
    out: dict[str, dict] = {}
    for cfg in fetch(base + "/configs")["configs"]:
        for r in fetch(f"{base}/metrics/{cfg}")["results"]:
            spec = r["model_spec"]
            key = f"{cfg}/{spec.get('name', '?')}/{spec.get('role', '')}"
            out.setdefault(key, {})[r["metric"]] = r["value"]
    return out


def esc(value) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;")


def fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def color(value, lo: float = 0.0, hi: float = 1.0, invert: bool = False) -> str:
    if value is None:
        return "#f0f0f0"
    x = 0.0 if hi == lo else max(0.0, min(1.0, (value - lo) / (hi - lo)))
    if invert:
        x = 1.0 - x
    return f"#{int(255 * x):02x}{int(255 * (1 - x)):02x}60"


def header(w: int, h: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="monospace">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="16" y="28" font-size="18" font-weight="bold">{esc(title)}</text>',
    ]


def label(x: float, y: float, text: str, size: int = 12, anchor: str = "middle") -> str:
    return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" text-anchor="{anchor}">{esc(text)}</text>'


def rect(x: float, y: float, w: float, h: float, fill: str) -> str:
    return f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{fill}" rx="4"/>'


def map_config_metric(rows: dict[str, dict], out: Path) -> None:
    cw, ch, x0, y0 = 130, 34, 220, 70
    names = [m for m in METRICS if any(m in r for r in rows.values())]
    s = header(1240, y0 + ch * (len(rows) + 1) + 20, "Конфигурация × метрика (/metrics)")
    for j, metric in enumerate(names):
        y = y0 + ch * j
        s.append(label(x0 - 10, y + 22, metric, 13, "end"))
        col = [r.get(metric) for r in rows.values()]
        nums = [v for v in col if isinstance(v, (int, float))]
        lo, hi = (min(nums), max(nums)) if nums else (0.0, 1.0)
        for i, key in enumerate(rows):
            v = rows[key].get(metric)
            s.append(
                rect(x0 + cw * i, y, cw - 4, ch - 4, color(v, lo, hi, invert=metric in BAD_METRICS))
                + label(x0 + cw * i + (cw - 4) / 2, y + ch / 2, fmt(v), 12)
            )
    for i, key in enumerate(rows):
        s.append(label(x0 + cw * i + (cw - 4) / 2, y0 - 8, "/".join(key.split("/")[-2:]), 11))
    s.append("</svg>")
    (out / "map_config_metric.svg").write_text("\n".join(s), encoding="utf-8")


def map_breakeven(rows: dict[str, dict], out: Path) -> None:
    ch, x0, y0 = 44, 260, 70
    s = header(
        1000, y0 + ch * (len(rows) + 1) + 20, "Break-even: L* и решения по цене пропуска L_viol"
    )
    s.append(label(x0, y0 - 8, "L* (база)"))
    for j, v in enumerate(L_VIOLS):
        s.append(label(x0 + 130 + j * 120, y0 - 8, f"L_viol={v}"))
    for i, key in enumerate(rows):
        y = y0 + ch * i
        be = rows[key].get("break_even") or {}
        s.append(label(x0 - 10, y + 24, key.split("/")[-2], 13, "end"))
        ls = be.get("L_star")
        s.append(rect(x0, y, 110, ch - 4, color(ls, 0, 60, invert=True)))
        s.append(label(x0 + 55, y + 24, fmt(ls)))
        dec = be.get("decision_at_L_viol") or {}
        palette = {"True": "#40a060", "False": "#d05050"}
        for j, v in enumerate(L_VIOLS):
            d = dec.get(v)
            s.append(
                rect(x0 + 130 + j * 120, y, 110, ch - 4, palette.get(str(d), "#e0c060"))
                + label(x0 + 185 + j * 120, y + 24, fmt(d), 11)
            )
    s.append("</svg>")
    (out / "map_breakeven.svg").write_text("\n".join(s), encoding="utf-8")


def map_real_frame(rows: dict[str, dict], out: Path) -> None:
    ch, x0, y0 = 44, 260, 70
    s = header(
        1000, y0 + ch * (len(rows) + 1) + 20, "L* в реальном фрейме (сценарии p_att, фрейм A)"
    )
    for i, key in enumerate(rows):
        y = y0 + ch * i
        s.append(label(x0 - 10, y + 24, key.split("/")[-2], 13, "end"))
        for j, (p_att, ls) in enumerate(sorted((rows[key].get("L_star_real") or {}).items())):
            s.append(
                rect(x0 + j * 150, y, 140, ch - 4, color(ls, 0, 2000, invert=True))
                + label(x0 + 70 + j * 150, y + 24, f"p_att={p_att}: {fmt(ls)}")
            )
    s.append("</svg>")
    (out / "map_real_frame.svg").write_text("\n".join(s), encoding="utf-8")


def map_gtau(rows: dict[str, dict], out: Path) -> None:
    x0, y0, bh = 220, 70, 40
    s = header(
        1000, y0 + bh * (len(rows) + 1) + 30, "G-τ: ложные прерывания, Wilson 95% CI (порог 5%)"
    )
    s.append(
        f'<line x1="{x0 + 0.05 * 500:.0f}" y1="{y0 - 10}" '
        f'x2="{x0 + 0.05 * 500:.0f}" y2="{y0 + bh * len(rows)}" '
        'stroke="#d04040" stroke-dasharray="4 3"/>'
    )
    for i, key in enumerate(rows):
        y = y0 + bh * i
        s.append(label(x0 - 10, y + 26, key.split("/")[-2], 13, "end"))
        rate = rows[key].get("G_tau_rate")
        if rate is None:
            s.append(label(x0, y + 26, "нет легальных эпизодов", 12, "start"))
            continue
        low = float(rows[key].get("G_tau_wilson_low") or 0)
        high = float(rows[key].get("G_tau_wilson_high") or 0)
        s.append(
            f'<rect x="{x0 + low * 500:.0f}" y="{y + 8}" width="{max(2.0, (high - low) * 500):.0f}" '
            f'height="14" fill="#9090d0" opacity="0.5" rx="4"/>'
            f'<rect x="{x0 + float(rate) * 500:.0f}" y="{y + 4}" width="6" height="22" '
            'fill="#3050c0" rx="2"/>'
        )
        gate = rows[key].get("G_tau_gate")
        s.append(
            label(
                x0 + 520, y + 26, f"{fmt(rate)} [{fmt(low)}, {fmt(high)}] {fmt(gate)}", 12, "start"
            )
        )
    s.append("</svg>")
    (out / "map_gtau.svg").write_text("\n".join(s), encoding="utf-8")


def map_pareto(rows: dict[str, dict], out: Path) -> None:
    w, h, x0, y0, pw, ph = 1000, 560, 120, 60, 600, 400
    s = header(w, h, "Pareto: защита (V) ↔ вред честным (R + G-τ), пузырь = C_ep")
    s.append(
        f'<line x1="{x0}" y1="{y0 + ph}" x2="{x0 + pw}" y2="{y0 + ph}" stroke="black"/>'
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + ph}" stroke="black"/>'
        + label(x0 + pw / 2, y0 + ph + 34, "V — доля остановленных атак", 13)
        + label(x0 - 40, y0 + ph / 2, "R + G-τ — вред честным", 13)
    )
    s[-1] = s[-1].replace("<text", f'<text transform="rotate(-90 {x0 - 40} {y0 + ph / 2:.0f})"', 1)
    for key, r in rows.items():
        v = float(r.get("V") or 0.0)
        harm = float(r.get("R") or 0.0) + float(r.get("G_tau_rate") or 0.0)
        x, y = x0 + v * pw, y0 + ph - harm * (ph / 0.5)
        bubble = 8 + min(30.0, float(r.get("C_ep") or 0.0) * 40)
        s.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{bubble:.0f}" fill="#4060c0" opacity="0.6"/>'
            + label(x, y - bubble - 4, key.split("/")[-2], 12)
        )
    s.append("</svg>")
    (out / "map_pareto.svg").write_text("\n".join(s), encoding="utf-8")


def index(rows: dict[str, dict], out: Path) -> None:
    s = [
        "<html><head><meta charset='utf-8'><title>dvarp-lab demo maps</title></head><body>",
        "<h2>dvarp-lab: демо-карты метрик</h2>",
    ]
    s += [
        f'<p><a href="{n}">{n}</a> (<iframe src="{n}" width="1000" height="620"></iframe>)</p>'
        for n in MAPS
    ]
    s.append("</body></html>")
    (out / "index.html").write_text("\n".join(s), encoding="utf-8")
    (out / "metrics_dump.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Демо-карты метрик dvarp-lab (SVG, без зависимостей)")
    p.add_argument("--out", default="runs/dev/demo", help="каталог вывода")
    p.add_argument("--metrics-url", default="http://127.0.0.1:9415", help="база metrics_svc")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = rows_by_config(args.metrics_url.rstrip("/"))
    map_config_metric(rows, out)
    map_breakeven(rows, out)
    map_real_frame(rows, out)
    map_gtau(rows, out)
    map_pareto(rows, out)
    index(rows, out)
    print("maps:", ", ".join(sorted(q.name for q in out.glob("*"))))


if __name__ == "__main__":
    main()
