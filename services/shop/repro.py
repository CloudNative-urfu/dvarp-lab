"""Canonical hashes, files, seed derivation and trajectory helpers (from dvarp-prototype repro).

Only standard library. No wall-clock in anything that feeds a hash.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Iterable
from pathlib import Path
from typing import Any

IGNORED_DIRS = frozenset({"__pycache__", ".git", ".venv", "venv", "venvs", "tmp", ".runtime"})
IGNORED_SUFFIXES = (".pyc", ".pyo")


class HashingError(ValueError):
    """Object cannot be serialized unambiguously (NaN, set, arbitrary class)."""


def _check(obj: Any, path: str = "$") -> None:
    if isinstance(obj, float) and not math.isfinite(obj):
        raise HashingError(f"non-finite number at {path}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise HashingError(f"non-string key {k!r} at {path}")
            _check(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _check(v, f"{path}[{i}]")
    elif obj is not None and not isinstance(obj, (str, int, float, bool)):
        raise HashingError(f"type {type(obj).__name__} is not canonically serializable at {path}")


def canonical_json(obj: Any) -> bytes:
    """Canonical JSON: sorted keys, no spaces, UTF-8."""
    _check(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj: Any) -> str:
    """SHA-256 of the canonical JSON form of the object."""
    return sha256_bytes(canonical_json(obj))


def _normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return data.replace(b"\r\n", b"\n")


def sha256_file(path: str | Path) -> str:
    return sha256_bytes(_normalized_bytes(Path(path)))


def _iter_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        if p.is_file() and not p.name.endswith(IGNORED_SUFFIXES):
            yield p


def file_hashes(root: str | Path) -> dict[str, str]:
    """Per-file hashes of a directory: {relative POSIX path: sha256}."""
    root = Path(root)
    if root.is_file():
        return {root.name: sha256_file(root)}
    if not root.is_dir():
        raise FileNotFoundError(f"no such file or directory: {root}")
    return {p.relative_to(root).as_posix(): sha256_file(p) for p in _iter_files(root)}


def hash_tree(root: str | Path) -> str:
    """Directory hash: file names and contents; renaming changes the hash."""
    return hash_obj(file_hashes(root))


# ------------------------------------------------------------------ seeds

SEED_BITS = 63  # fits signed int64: fine for SQLite and model seed fields


class SeedError(ValueError):
    pass


def check_seed(seed: object) -> int:
    """Seed must be an explicit non-negative int; None/bool/str are errors."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SeedError(f"seed must be an integer, got {seed!r}")
    if seed < 0 or seed >= 2**SEED_BITS:
        raise SeedError(f"seed out of range [0, 2^{SEED_BITS}): {seed}")
    return seed


def derive_seed(master_seed: int, *labels: object) -> int:
    check_seed(master_seed)
    material = "\x1f".join([str(master_seed), *(str(x) for x in labels)]).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big") >> (64 - SEED_BITS)


def make_rng(master_seed: int, *labels: object) -> random.Random:
    """Isolated generator for one consumer; the global random is untouched."""
    return random.Random(derive_seed(master_seed, *labels))


# ------------------------------------------------------------------ trajectories

# Volatile step fields: time and latency measurements are excluded from comparison.
VOLATILE_KEYS = frozenset(
    {
        "ts",
        "time",
        "created_at",
        "wall_ms",
        "wall_s",
        "latency_ms",
        "cpu_ms",
        "cpu_s",
        "duration_ms",
    }
)
# Floating version references: a run with them is not reproducible.
FLOATING_VERSIONS = frozenset({"", "latest", "main", "master", "head", "default", "*", "any"})


def strip_volatile(obj: Any, volatile: frozenset[str] = VOLATILE_KEYS) -> Any:
    if isinstance(obj, dict):
        return {k: strip_volatile(v, volatile) for k, v in obj.items() if k not in volatile}
    if isinstance(obj, (list, tuple)):
        return [strip_volatile(v, volatile) for v in obj]
    return obj


def trajectory_fingerprint(steps: Iterable[Any]) -> str:
    """Hash of an ordered trajectory without timestamps and latency measurements."""
    return hash_obj([strip_volatile(s) for s in steps])


def compare_trajectories(a: list[Any], b: list[Any], *, episode_id: str = "") -> dict | None:
    """None if the trajectories match; otherwise a reproducibility defect record."""
    ha, hb = trajectory_fingerprint(a), trajectory_fingerprint(b)
    if ha == hb:
        return None
    sa, sb = [strip_volatile(s) for s in a], [strip_volatile(s) for s in b]
    first = next(
        (i for i, (x, y) in enumerate(zip(sa, sb)) if hash_obj(x) != hash_obj(y)),
        min(len(sa), len(sb)),
    )
    return {
        "kind": "reproducibility_defect",
        "episode_id": episode_id,
        "first_divergence": first,
        "len_a": len(sa),
        "len_b": len(sb),
        "step_a": sa[first] if first < len(sa) else None,
        "step_b": sb[first] if first < len(sb) else None,
        "sha256_a": ha,
        "sha256_b": hb,
    }
