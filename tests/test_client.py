"""Tests for the KEGGClient HTTP layer: caching, 404-as-empty, retry, errors."""

from __future__ import annotations

import httpx
import pytest
import respx
import tenacity

from kegg_mcp_server.cache import TTLCache
from kegg_mcp_server.client import KEGGClient
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
