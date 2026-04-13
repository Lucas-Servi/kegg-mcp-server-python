"""Async KEGG REST API client with caching and batch support."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

    from kegg_mcp_server.cache import TTLCache

# KEGG allows max 10 entries per GET request
_BATCH_SIZE = 10


class KEGGClient:
    """Thin async wrapper around the KEGG REST API (https://rest.kegg.jp).

    Operations:
        info   /info/{database}
        list   /list/{database}
        find   /find/{database}/{query}[/{option}]
        get    /get/{dbentries}[/{option}]
        conv   /conv/{target_db}/{source_db_or_entries}
        link   /link/{target_db}/{source_db_or_entries}
        ddi    /ddi/{dbentries}
    """

    def __init__(self, http: httpx.AsyncClient, cache: TTLCache) -> None:
        self._http = http
        self._cache = cache

    async def info(self, database: str) -> str:
        return await self._cached_get(f"/info/{database}")

    async def list(self, database: str) -> str:
        return await self._cached_get(f"/list/{database}")

    async def find(self, database: str, query: str, option: str | None = None) -> str:
        path = f"/find/{database}/{query}"
        if option:
            path += f"/{option}"
        return await self._cached_get(path)

    async def get(self, dbentries: str, option: str | None = None) -> str:
        path = f"/get/{dbentries}"
        if option:
            path += f"/{option}"
        return await self._cached_get(path)

    async def conv(self, target_db: str, source: str) -> str:
        return await self._cached_get(f"/conv/{target_db}/{source}")

    async def link(self, target_db: str, source: str) -> str:
        return await self._cached_get(f"/link/{target_db}/{source}")

    async def ddi(self, dbentries: str) -> str:
        return await self._cached_get(f"/ddi/{dbentries}")

    async def get_batch(self, entry_ids: list[str], option: str | None = None) -> list[str]:
        """Fetch multiple entries, chunking into groups of 10 and running concurrently."""
        chunks = [entry_ids[i : i + _BATCH_SIZE] for i in range(0, len(entry_ids), _BATCH_SIZE)]
        tasks = [self.get("+".join(chunk), option) for chunk in chunks]
        return list(await asyncio.gather(*tasks))

    async def _cached_get(self, path: str) -> str:
        cached = self._cache.get(path)
        if cached is not None:
            return cached
        resp = await self._http.get(path)
        resp.raise_for_status()
        text = resp.text
        self._cache.set(path, text)
        return text
