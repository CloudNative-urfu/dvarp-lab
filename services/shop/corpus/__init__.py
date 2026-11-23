"""Компонент `corpus`: размеченный корпус атак по трём осям FR-1.21 (механизм, цель,
доставка) и сопоставимых чистых контролей FR-1.22 с ground truth, происхождением и
хешем; тексты — «dirty English» (NFR-2.7), данные синтетические (NFR-2.13).

Только стандартная библиотека. CLI: `python3 -m services.shop.corpus --help`.
"""

from .bind import UNIVERSAL_FORBIDDEN, BoundEpisode, bind, pick_accounts
from .dirty import MARKER_NAMES, dirty_markers
from .schema import (
    CONTROL_TYPES,
    DELIVERIES,
    GOALS,
    MECHANISMS,
    PREDICATES,
    CorpusError,
    coverage,
    dirty_rates,
    entry_texts,
    validate_corpus,
    validate_entry,
    volume,
)
from .store import CORPUS_FILE, DEFAULT_DIR, MANIFEST_FILE, load_corpus

__all__ = [
    "CONTROL_TYPES",
    "CORPUS_FILE",
    "DEFAULT_DIR",
    "DELIVERIES",
    "GOALS",
    "MANIFEST_FILE",
    "MARKER_NAMES",
    "MECHANISMS",
    "PREDICATES",
    "UNIVERSAL_FORBIDDEN",
    "BoundEpisode",
    "CorpusError",
    "bind",
    "coverage",
    "dirty_markers",
    "dirty_rates",
    "entry_texts",
    "freeze",
    "load_corpus",
    "pick_accounts",
    "validate_corpus",
    "validate_entry",
    "volume",
]
