"""Детерминированные части прогона: производные seed от базового и состава эпизода."""

from __future__ import annotations

import hashlib


def derive_seed(base_seed: int, *parts: object) -> int:
    data = "|".join(str(p) for p in (base_seed, *parts)).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big") % (2**31)
