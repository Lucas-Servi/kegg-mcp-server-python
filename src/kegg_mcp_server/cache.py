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

_DEFAULT_TTL_SECONDS = 6 * 3600.0

# Per-op TTLs. `info` is release metadata (stable for weeks); `list` enumerates
# a whole database (stable for hours); entry ops change at most on KEGG's daily update.
_TTL_BY_OP: dict[str, float] = {
    "info": 24 * 3600.0,
    "list": 3600.0,
    "get": 6 * 3600.0,
    "find": 6 * 3600.0,
    "conv": 6 * 3600.0,
    "link": 6 * 3600.0,
    "ddi": 6 * 3600.0,
}

_MAX_CACHE_BYTES = 64 * 1024 * 1024


def _op_from_path(key: str) -> str:
    # KEGG paths look like "/info/kegg", "/get/hsa00010", "/find/pathway/gly".
    stripped = key.lstrip("/")
    head, _, _ = stripped.partition("/")
    return head


class TTLCache:
    """TTL cache keyed on KEGG REST paths with per-op expiries.

    Backed by `cachetools.TLRUCache`, bounded by response bytes rather than
    entry count (a single BRITE hierarchy body can be several MB on its own).
    The timer uses monotonic time so expiry is robust to wall-clock changes.
    """

    def __init__(
        self, maxsize: int = _MAX_CACHE_BYTES, default_ttl: float = _DEFAULT_TTL_SECONDS
    ) -> None:
        self._default_ttl = default_ttl
        self._cache: cachetools.TLRUCache[str, Any] = cachetools.TLRUCache(
            maxsize=maxsize,
            ttu=self._ttu,
            getsizeof=len,
            timer=time.monotonic,
        )

    def _ttu(self, key: str, _value: Any, now: float) -> float:
        return now + _TTL_BY_OP.get(_op_from_path(key), self._default_ttl)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        try:
            self._cache[key] = value
        except ValueError:
            pass  # value bigger than maxsize (cachetools can't cache it) — just skip

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
