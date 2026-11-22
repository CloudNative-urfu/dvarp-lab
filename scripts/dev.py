"""Dev-режим: поднять все 6 сервисов с общими dev-БД и держать до Ctrl-C.

Запуск: `uv run python scripts/dev.py [--fresh] [--port-base 9410]`.
--fresh: удалить dev-каталог runs/dev/ перед стартом (нужны права на rm — иначе
каталог оставляется как есть). После Ctrl-C сервисы гасятся корректно.
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


def _env(dev: Path) -> dict[str, str]:
    env = os.environ.copy()
    shop_db = f"sqlite:///{dev}/shop.db"
    raw_db = f"sqlite:///{dev}/raw.db"
    env.update(
        {
            "LAB_SHOP_DB_URL": shop_db,
            "LAB_SHOP_RUNTIME": str(dev / "shop_runtime"),
            "LAB_FILTER_URL": "http://127.0.0.1:9414",
            "LAB_SHOP_URL": "http://127.0.0.1:9411",
            "LAB_RAW_DB_URL": raw_db,
            "LAB_RAW_DIR": str(dev / "raw"),
            "LAB_METRICS_DB_URL": f"sqlite:///{dev}/metrics.db",
            "LAB_RUNS_DIR": str(dev / "runs"),
        }
    )
    return env


def _wait(ports: dict[int, str]) -> None:
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
    parser = argparse.ArgumentParser(prog="dev")
    parser.add_argument("--fresh", action="store_true", help="стереть runs/dev/ перед стартом")
    parser.add_argument("--tmp", default=None, help="каталог dev-данных (default: runs/dev)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    dev = Path(args.tmp) if args.tmp else root / "runs" / "dev"
    if args.fresh and dev.exists():
        import shutil

        shutil.rmtree(dev)
    dev.mkdir(parents=True, exist_ok=True)

    env = _env(dev)
    for port, module in SERVICES.items():
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
            cwd=root,
        )
        PROCS.append(proc)
    atexit.register(_cleanup)
    _wait(SERVICES)
    print(
        f"dvarp-lab dev: консоль http://127.0.0.1:9410 · данные {dev} · Ctrl-C для остановки",
        flush=True,
    )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
