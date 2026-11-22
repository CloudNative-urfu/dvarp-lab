"""Клиент между сервисами: тонкая обёртка над httpx для локальных эндпоинтов."""

from __future__ import annotations

import httpx


class Svc:
    def __init__(self, base_url: str, timeout: float = 600.0) -> None:
        self.base = base_url.rstrip("/")
        self._timeout = timeout

    def get(self, path: str, **params: object) -> dict:
        r = httpx.get(self.base + path, params=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: dict | None = None) -> dict:
        r = httpx.post(self.base + path, json=json, timeout=self._timeout)
        r.raise_for_status()
        return r.json()
