"""Сквозной смок dvarp-lab: поднимает 5 сервисов, гоняет launcher, считает метрики.

Запуск: `uv run python scripts/smoke.py [--episodes 1]`.
Не требует живых моделей: агент/атакующий/клиент работают в stub-режиме.
"""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

SERVICES = {
    9411: "services.shop.app:app",
    9412: "services.traffic.app:app",
    9413: "services.attack.app:app",
    9414: "services.filter.app:app",
    9415: "services.metrics.app:app",
    9410: "services.ui.app:app",
}
PROCS: list[subprocess.Popen] = []


def _spawn(ports: dict[int, str], tmp: Path, episodes: int, compute: bool) -> None:
    env = os.environ.copy()
    env.update(
        {
            "LAB_SHOP_DB_URL": f"sqlite:///{tmp}/shop.db",
            "LAB_SHOP_RUNTIME": str(tmp / "shop_runtime"),
            "LAB_FILTER_URL": "http://127.0.0.1:9414",
            "LAB_SHOP_URL": "http://127.0.0.1:9411",
            "LAB_RAW_DB_URL": f"sqlite:///{tmp}/raw.db",
            "LAB_RAW_DIR": str(tmp / "raw"),
            "LAB_METRICS_DB_URL": f"sqlite:///{tmp}/metrics.db",
            "LAB_RUNS_DIR": str(tmp / "runs"),
            "LAB_ATTACKER_LLM_BASE_URL": "",
            "LAB_CUSTOMER_LLM_BASE_URL": "",
        }
    )
    for port, module in ports.items():
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                module,
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            env=env,
            cwd=Path(__file__).resolve().parent.parent,
        )
        PROCS.append(proc)
    deadline = time.time() + 30
    for port in ports:
        while time.time() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.3)
        else:
            raise SystemExit(f"сервис на {port} не поднялся")

    argv = [
        "launcher",
        "--config",
        "g0",
        "--goals",
        "refund_expired",
        "--tactics",
        "direct_task",  # пин метода: ось all после каталога v3 (#52) раздувает объём
        "--episodes",
        str(episodes),
        "--seed",
        "7",
        "--budget",
        "6",
    ]
    if compute:
        argv.append("--compute")
    r = subprocess.run([sys.executable, "-m", *argv], env=env, check=True)
    assert r.returncode == 0

    metrics = httpx.get("http://127.0.0.1:9415/metrics/g0", timeout=30).json()
    print("metrics/g0:", metrics)
    chain = httpx.get("http://127.0.0.1:9414/chain/verify", timeout=30).json()
    assert chain.get("defects") == [], chain
    print("chain: ok")


def _cleanup() -> None:
    for proc in PROCS:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
    for proc in PROCS:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--no-compute", action="store_true")
    parser.add_argument("--tmp", default=None)
    args = parser.parse_args()
    tmp = Path(args.tmp or "/tmp/opencode/dvarp-lab-smoke")
    atexit.register(_cleanup)
    try:
        _spawn(SERVICES, tmp, args.episodes, not args.no_compute)
    finally:
        _cleanup()
    print("SMOKE OK")


if __name__ == "__main__":
    main()
