"""Async KEGG REST API client with caching, retry, and batch support."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import httpx
import tenacity

from kegg_mcp_server.errors import KEGGAPIError

if TYPE_CHECKING:
    from kegg_mcp_server.cache import TTLCache

# KEGG allows max 10 entries per GET request
_BATCH_SIZE = 10

# Cap concurrent in-flight requests to KEGG. KEGG asks API users to be gentle;
# 3 concurrent requests is conservative and shared across all tool invocations.
_KEGG_SEMAPHORE = asyncio.Semaphore(3)

_RETRIABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

logger = logging.getLogger("kegg_mcp_server.client")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.ReadTimeout, httpx.ConnectTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRIABLE_STATUSES
    return False


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
        """Fetch multiple entries, chunking to respect KEGG's max-10-per-GET limit.

        Concurrency across chunks is gated by the module-level semaphore, so a large
        batch does not fan out beyond the configured in-flight cap.
        """
        chunks = [entry_ids[i : i + _BATCH_SIZE] for i in range(0, len(entry_ids), _BATCH_SIZE)]
        tasks = [self.get("+".join(chunk), option) for chunk in chunks]
        return list(await asyncio.gather(*tasks))

    async def _cached_get(self, path: str) -> str:
        cached = self._cache.get(path)
        if cached is not None:
            logger.debug("kegg cache hit", extra={"path": path, "cache_hit": True})
            return cached
        try:
            text = await self._fetch(path)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info(
                    "kegg not found",
                    extra={"path": path, "status": 404, "cache_hit": False},
                )
                self._cache.set(path, "")
                return ""
            raise KEGGAPIError(
                f"KEGG API error: HTTP {exc.response.status_code}",
                status=exc.response.status_code,
                path=path,
                retryable=exc.response.status_code in _RETRIABLE_STATUSES,
            ) from exc
        except httpx.TransportError as exc:
            raise KEGGAPIError(
                f"KEGG API network error: {exc.__class__.__name__}",
                path=path,
                retryable=True,
            ) from exc
        self._cache.set(path, text)
        return text

    @tenacity.retry(
        retry=tenacity.retry_if_exception(_should_retry),
        wait=tenacity.wait_exponential(multiplier=0.5, max=8),
        stop=tenacity.stop_after_attempt(3),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _fetch(self, path: str) -> str:
        async with _KEGG_SEMAPHORE:
            start = time.perf_counter()
            resp = await self._http.get(path)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning(
                    "kegg http error",
                    extra={
                        "path": path,
                        "status": resp.status_code,
                        "duration_ms": duration_ms,
                        "cache_hit": False,
                    },
                )
                raise
            logger.info(
                "kegg request",
                extra={
                    "path": path,
                    "status": resp.status_code,
                    "duration_ms": duration_ms,
                    "cache_hit": False,
                },
            )
            return resp.text
