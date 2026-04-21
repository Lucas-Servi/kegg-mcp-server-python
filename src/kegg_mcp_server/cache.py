"""Per-operation TTL cache for KEGG REST API responses.

The TTL for each entry is chosen from the first segment of its cache key (the
KEGG REST op). This lets us cache stable metadata (`info`, `list`) for much
longer than volatile entry fetches without paying for a separate cache
instance per op.
"""

from __future__ import annotations

import time
from typing import Any

import cachetools

_DEFAULT_TTL_SECONDS = 300.0

# Per-op TTLs. `info` is release metadata (stable for weeks); `list` enumerates
# a whole database (stable for hours); other ops fetch entry data that can
# change on KEGG curator edits but realistically churn is low.
_TTL_BY_OP: dict[str, float] = {
    "info": 24 * 3600.0,
    "list": 3600.0,
    "get": 300.0,
    "find": 300.0,
    "conv": 300.0,
    "link": 300.0,
    "ddi": 300.0,
}


def _op_from_path(key: str) -> str:
    # KEGG paths look like "/info/kegg", "/get/hsa00010", "/find/pathway/gly".
    stripped = key.lstrip("/")
    head, _, _ = stripped.partition("/")
    return head


class TTLCache:
    """TTL cache keyed on KEGG REST paths with per-op expiries.

    Backed by `cachetools.TLRUCache`; the timer uses monotonic time so expiry
    is robust to wall-clock changes.
    """

    def __init__(
        self, maxsize: int = 1024, default_ttl: float = _DEFAULT_TTL_SECONDS
    ) -> None:
        self._default_ttl = default_ttl
        self._cache: cachetools.TLRUCache[str, Any] = cachetools.TLRUCache(
            maxsize=maxsize,
            ttu=self._ttu,
            timer=time.monotonic,
        )

    def _ttu(self, key: str, _value: Any, now: float) -> float:
        return now + _TTL_BY_OP.get(_op_from_path(key), self._default_ttl)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
