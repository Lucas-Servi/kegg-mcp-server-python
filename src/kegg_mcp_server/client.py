"""Async KEGG REST API client with caching, retry, and batch support."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import httpx
import tenacity

from kegg_mcp_server.errors import KEGGAPIError

if TYPE_CHECKING:
    from kegg_mcp_server.cache import TTLCache

# KEGG allows max 10 entries per GET request
_BATCH_SIZE = 10

_REQUESTS_PER_SECOND = 3.0
_MAX_CONCURRENT_REQUESTS = 3

_RETRIABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

_MAX_RESPONSE_BYTES = 25 * 1024 * 1024  # 25 MB

logger = logging.getLogger("kegg_mcp_server.client")


def _redact_path(path: str) -> str:
    """Keep the KEGG operation prefix, replace user-supplied segment with a hash."""
    parts = path.strip("/").split("/", 1)
    if len(parts) < 2:
        return path
    op = parts[0]
    payload_hash = hashlib.sha1(parts[1].encode(), usedforsecurity=False).hexdigest()[:8]
    return f"/{op}/sha1:{payload_hash}"


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.ReadTimeout, httpx.ConnectTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRIABLE_STATUSES
    return False


def _retry_after_seconds(exc: BaseException, *, now: datetime | None = None) -> float | None:
    """Parse an HTTP Retry-After header as seconds or an HTTP date."""
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 429:
        return None
    value = exc.response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        return max(0.0, (retry_at - current).total_seconds())


def _wait_for_retry(retry_state: tenacity.RetryCallState) -> float:
    """Honor Retry-After on 429, otherwise use capped exponential backoff."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    retry_after = _retry_after_seconds(exc) if exc else None
    if retry_after is not None:
        return retry_after
    return min(8.0, 0.5 * (2 ** (retry_state.attempt_number - 1)))


class _AsyncRateLimiter:
    """Space all request starts made by a client to stay at 3 requests/s."""

    def __init__(
        self,
        requests_per_second: float = _REQUESTS_PER_SECOND,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._interval = 1.0 / requests_per_second
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._next_start = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_start - now)
            if delay:
                await self._sleep(delay)
                now = self._clock()
            self._next_start = max(now, self._next_start) + self._interval


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
        self._rate_limiter = _AsyncRateLimiter()
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

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

        Concurrency across chunks is gated by the client semaphore and request starts
        are rate-limited, so a large batch stays within KEGG's usage policy.
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
        wait=_wait_for_retry,
        stop=tenacity.stop_after_attempt(3),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _fetch(self, path: str) -> str:
        await self._rate_limiter.wait()
        async with self._semaphore:
            start = time.perf_counter()
            resp = await self._http.get(path)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning(
                    "kegg http error",
                    extra={
                        "path": _redact_path(path),
                        "status": resp.status_code,
                        "duration_ms": duration_ms,
                        "cache_hit": False,
                    },
                )
                raise
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > _MAX_RESPONSE_BYTES:
                raise KEGGAPIError(
                    f"Response too large ({content_length} bytes, limit {_MAX_RESPONSE_BYTES})",
                    path=path,
                    retryable=False,
                )
            text = resp.text
            if len(text.encode("utf-8")) > _MAX_RESPONSE_BYTES:
                raise KEGGAPIError(
                    f"Response body exceeds {_MAX_RESPONSE_BYTES} byte limit",
                    path=path,
                    retryable=False,
                )
            logger.info(
                "kegg request",
                extra={
                    "path": _redact_path(path),
                    "status": resp.status_code,
                    "duration_ms": duration_ms,
                    "cache_hit": False,
                },
            )
            return text
