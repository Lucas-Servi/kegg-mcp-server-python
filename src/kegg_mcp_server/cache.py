"""TTL-based in-memory cache for KEGG REST API responses."""

from __future__ import annotations

from typing import Any

import cachetools


class TTLCache:
    """Simple TTL cache backed by cachetools.TTLCache."""

    def __init__(self, maxsize: int = 1024, default_ttl: float = 300) -> None:
        self._cache: cachetools.TTLCache[str, Any] = cachetools.TTLCache(
            maxsize=maxsize, ttl=default_ttl
        )

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
