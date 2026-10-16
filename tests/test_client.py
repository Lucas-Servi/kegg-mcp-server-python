"""Tests for the KEGGClient HTTP layer: caching, 404-as-empty, retry, errors."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
import respx
import tenacity

from kegg_mcp_server.cache import TTLCache
from kegg_mcp_server.client import (
    KEGGClient,
    _AsyncRateLimiter,
    _encode_find_query,
    _retry_after_seconds,
    _should_retry,
    _wait_for_retry,
)
from kegg_mcp_server.errors import KEGGAPIError


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapse tenacity's exponential backoff to zero so retry tests run fast."""
    monkeypatch.setattr(KEGGClient._fetch.retry, "wait", tenacity.wait_none())


@pytest.fixture
def cache() -> TTLCache:
    return TTLCache()


@pytest.fixture
async def client(cache: TTLCache):  # noqa: ANN201
    async with httpx.AsyncClient(base_url="https://rest.kegg.jp") as http:
        yield KEGGClient(http, cache)


@respx.mock
async def test_get_200_returns_text_and_caches(client: KEGGClient, cache: TTLCache) -> None:
    route = respx.get("https://rest.kegg.jp/info/kegg").mock(
        return_value=httpx.Response(200, text="kegg info body")
    )
    assert await client.info("kegg") == "kegg info body"
    # Second call hits the cache, not the network
    assert await client.info("kegg") == "kegg info body"
    assert route.call_count == 1
    assert cache.get("/info/kegg") == "kegg info body"


@respx.mock
async def test_get_404_returns_empty_not_error(client: KEGGClient, cache: TTLCache) -> None:
    respx.get("https://rest.kegg.jp/get/hsa99999").mock(
        return_value=httpx.Response(404, text="")
    )
    result = await client.get("hsa99999")
    assert result == ""
    # Empty response is cached to suppress repeated 404 roundtrips
    assert cache.get("/get/hsa99999") == ""


@respx.mock
async def test_retries_on_5xx_then_succeeds(client: KEGGClient) -> None:
    respx.get("https://rest.kegg.jp/info/kegg").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, text="finally"),
        ]
    )
    assert await client.info("kegg") == "finally"


@respx.mock
async def test_exhausted_retries_raise_kegg_api_error(client: KEGGClient) -> None:
    respx.get("https://rest.kegg.jp/info/kegg").mock(return_value=httpx.Response(500))
    with pytest.raises(KEGGAPIError) as exc:
        await client.info("kegg")
    assert exc.value.status == 500
    assert exc.value.retryable is True
    assert exc.value.path == "/info/kegg"


@respx.mock
async def test_network_error_raises_retryable_kegg_api_error(client: KEGGClient) -> None:
    respx.get("https://rest.kegg.jp/info/kegg").mock(
        side_effect=httpx.ConnectError("boom")
    )
    with pytest.raises(KEGGAPIError) as exc:
        await client.info("kegg")
    assert exc.value.retryable is True
    assert exc.value.path == "/info/kegg"


@respx.mock
async def test_non_retriable_4xx_raises_without_retrying(client: KEGGClient) -> None:
    route = respx.get("https://rest.kegg.jp/get/bad-id").mock(
        return_value=httpx.Response(400, text="bad request")
    )
    with pytest.raises(KEGGAPIError) as exc:
        await client.get("bad-id")
    assert exc.value.status == 400
    assert exc.value.retryable is False
    assert route.call_count == 1


@respx.mock
async def test_get_batch_chunks_ids_by_ten(client: KEGGClient) -> None:
    captured_paths: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        return httpx.Response(200, text=f"body for {request.url.path}")

    respx.get(url__startswith="https://rest.kegg.jp/get/").mock(side_effect=record)

    ids = [f"C{i:05d}" for i in range(25)]
    results = await client.get_batch(ids)

    assert len(results) == 3  # 10 + 10 + 5
    assert len(captured_paths) == 3
    # Each chunk request joins ids with '+'
    for path in captured_paths:
        assert path.startswith("/get/")
        ids_in_chunk = path[len("/get/") :].split("+")
        assert 1 <= len(ids_in_chunk) <= 10


async def test_rate_limiter_spaces_request_starts_without_real_sleep() -> None:
    now = 100.0
    sleeps: list[float] = []

    def clock() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        sleeps.append(delay)
        now += delay

    limiter = _AsyncRateLimiter(clock=clock, sleep=sleep)
    await asyncio.gather(*(limiter.wait() for _ in range(4)))

    assert sleeps == pytest.approx([1 / 3, 1 / 3, 1 / 3])


async def test_cache_hit_does_not_consume_rate_limit(client: KEGGClient, cache: TTLCache) -> None:
    class CountingLimiter:
        calls = 0

        async def wait(self) -> None:
            self.calls += 1

    limiter = CountingLimiter()
    client._rate_limiter = limiter
    cache.set("/info/kegg", "cached")

    assert await client.info("kegg") == "cached"
    assert limiter.calls == 0


async def test_client_preserves_three_request_concurrency_cap() -> None:
    active = 0
    max_active = 0
    three_started = asyncio.Event()
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        if active == 3:
            three_started.set()
        await release.wait()
        active -= 1
        return httpx.Response(200, text="ok", request=request)

    class NoWaitLimiter:
        async def wait(self) -> None:
            return None

    async with httpx.AsyncClient(
        base_url="https://rest.kegg.jp", transport=httpx.MockTransport(handler)
    ) as http:
        kegg = KEGGClient(http, TTLCache())
        kegg._rate_limiter = NoWaitLimiter()
        tasks = [asyncio.create_task(kegg._fetch(f"/info/test-{i}")) for i in range(6)]
        await asyncio.wait_for(three_started.wait(), timeout=1)
        await asyncio.sleep(0)
        assert max_active == 3
        release.set()
        assert await asyncio.gather(*tasks) == ["ok"] * 6
        assert max_active == 3


def _status_error(retry_after: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://rest.kegg.jp/info/kegg")
    response = httpx.Response(429, headers={"Retry-After": retry_after}, request=request)
    return httpx.HTTPStatusError("rate limited", request=request, response=response)


def test_retry_after_parses_seconds() -> None:
    assert _retry_after_seconds(_status_error("2.5")) == 2.5


def test_retry_after_parses_http_date() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    assert _retry_after_seconds(
        _status_error("Tue, 14 Jul 2026 12:00:05 GMT"), now=now
    ) == 5.0


def test_retry_wait_prefers_retry_after_and_falls_back_to_exponential() -> None:
    retry_state = SimpleNamespace(
        outcome=SimpleNamespace(exception=lambda: _status_error("7")),
        attempt_number=2,
    )
    assert _wait_for_retry(retry_state) == 7.0

    no_header = _status_error("")
    retry_state.outcome = SimpleNamespace(exception=lambda: no_header)
    assert _wait_for_retry(retry_state) == 1.0


def test_should_retry_gives_up_when_retry_after_exceeds_cap() -> None:
    assert _should_retry(_status_error("9")) is True
    assert _should_retry(_status_error("11")) is False


@respx.mock
async def test_long_retry_after_fails_fast_as_retryable(client: KEGGClient) -> None:
    route = respx.get("https://rest.kegg.jp/info/kegg").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "9999"})
    )
    with pytest.raises(KEGGAPIError) as exc:
        await client.info("kegg")
    assert exc.value.retryable is True
    assert route.call_count == 1  # no retry attempted


@respx.mock
async def test_timeout_raises_retryable_kegg_api_error(
    client: KEGGClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import kegg_mcp_server.client as client_mod

    monkeypatch.setattr(client_mod, "_FETCH_TIMEOUT_SECONDS", 0.01)

    async def slow_fetch(path: str) -> str:
        await asyncio.sleep(1)
        return "too slow"

    monkeypatch.setattr(client, "_fetch", slow_fetch)
    with pytest.raises(KEGGAPIError) as exc:
        await client.info("kegg")
    assert exc.value.retryable is True


def test_encode_find_query_turns_slash_into_space() -> None:
    assert _encode_find_query("Na+/K+-ATPase") == "Na+%20K+-ATPase"


def test_encode_find_query_escapes_hash_and_question_mark() -> None:
    assert _encode_find_query("C#1") == "C%231"
    assert _encode_find_query("C00002?") == "C00002%3F"


def test_encode_find_query_neutralizes_path_traversal() -> None:
    encoded = _encode_find_query("x/../../list/pathway")
    assert "/" not in encoded


@respx.mock
async def test_find_percent_encodes_query(client: KEGGClient) -> None:
    route = respx.get("https://rest.kegg.jp/find/ko/Na+%20K+-ATPase").mock(
        return_value=httpx.Response(200, text="K01539\tATP1A")
    )
    await client.find("ko", "Na+/K+-ATPase")
    assert route.called


async def test_rate_limiter_waits_while_holding_semaphore() -> None:
    """A limiter wait that starts only inside the semaphore can't burst past it."""
    active = 0
    max_active = 0

    class TrackingLimiter:
        async def wait(self) -> None:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok", request=request)

    async with httpx.AsyncClient(
        base_url="https://rest.kegg.jp", transport=httpx.MockTransport(handler)
    ) as http:
        kegg = KEGGClient(http, TTLCache())
        kegg._rate_limiter = TrackingLimiter()
        await asyncio.gather(*(kegg._fetch(f"/info/test-{i}") for i in range(6)))
        assert max_active <= 3  # the semaphore cap, not the request count


@respx.mock
async def test_get_batch_second_call_only_fetches_new_ids(client: KEGGClient) -> None:
    requested_paths: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        ids = request.url.path.removeprefix("/get/").split("+")
        body = "\n".join(f"ENTRY       {i}\n///" for i in ids)
        return httpx.Response(200, text=body)

    respx.get(url__startswith="https://rest.kegg.jp/get/").mock(side_effect=record)

    first = await client.get_batch(["C00002", "C00031"])
    assert len(requested_paths) == 1
    assert len(first) == 2

    second = await client.get_batch(["C00002", "C00031", "C00033"])
    assert len(requested_paths) == 2
    assert requested_paths[1] == "/get/C00033"  # only the new id was fetched
    assert len(second) == 3


@respx.mock
async def test_get_batch_dedupes_duplicate_ids(client: KEGGClient) -> None:
    requested_paths: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(200, text="ENTRY       C00002\n///")

    respx.get(url__startswith="https://rest.kegg.jp/get/").mock(side_effect=record)

    results = await client.get_batch(["C00002", "C00002", "C00002"])
    assert len(requested_paths) == 1
    assert requested_paths[0] == "/get/C00002"
    assert len(results) == 1
