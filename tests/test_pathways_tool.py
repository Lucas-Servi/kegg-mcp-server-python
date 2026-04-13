"""Unit tests for pathway search tool behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from kegg_mcp_server.tools import pathways


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):  # noqa: ANN201
        def decorator(func):  # noqa: ANN001, ANN202
            self.tools[func.__name__] = func
            return func

        return decorator


class FakeKEGG:
    def __init__(self, find_response: str = "", list_response: str = "") -> None:
        self.find_response = find_response
        self.list_response = list_response
        self.find_calls: list[tuple[str, str]] = []
        self.list_calls: list[str] = []

    async def find(self, database: str, query: str) -> str:
        self.find_calls.append((database, query))
        return self.find_response

    async def list(self, database: str) -> str:
        self.list_calls.append(database)
        return self.list_response


def _make_ctx(fake_kegg: FakeKEGG):
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(kegg=fake_kegg))
    )


def _get_search_pathways_tool():
    fake_mcp = FakeMCP()
    pathways.register(fake_mcp)
    return fake_mcp.tools["search_pathways"]


def test_filter_pathways_by_query_matches_tokens_case_insensitive() -> None:
    rows = {
        "bsu00010": "Glycolysis / Gluconeogenesis - Bacillus subtilis",
        "bsu01053": "Biosynthesis of siderophore group nonribosomal peptides",
    }
    filtered = pathways._filter_pathways_by_query(rows, "nonribosomal peptide biosynthesis")
    assert filtered == {"bsu01053": "Biosynthesis of siderophore group nonribosomal peptides"}


def test_search_pathways_map_uses_find_endpoint() -> None:
    search_pathways = _get_search_pathways_tool()
    fake_kegg = FakeKEGG(find_response="path:map00010\tGlycolysis / Gluconeogenesis\n")

    result = asyncio.run(
        search_pathways(
            query="glycolysis",
            organism_code="map",
            max_results=50,
            ctx=_make_ctx(fake_kegg),
        )
    )

    assert fake_kegg.find_calls == [("pathway", "glycolysis")]
    assert fake_kegg.list_calls == []
    assert result.database == "pathway"
    assert result.total_found == 1
    assert "path:map00010" in result.results


def test_search_pathways_organism_uses_list_and_local_filter() -> None:
    search_pathways = _get_search_pathways_tool()
    fake_kegg = FakeKEGG(
        list_response=(
            "bsu00010\tGlycolysis / Gluconeogenesis - Bacillus subtilis subsp. subtilis 168\n"
            "bsu01053\tBiosynthesis of siderophore group nonribosomal peptides - "
            "Bacillus subtilis subsp. subtilis 168\n"
        )
    )

    result = asyncio.run(
        search_pathways(
            query="nonribosomal peptide biosynthesis",
            organism_code="bsu",
            max_results=50,
            ctx=_make_ctx(fake_kegg),
        )
    )

    assert fake_kegg.find_calls == []
    assert fake_kegg.list_calls == ["pathway/bsu"]
    assert result.database == "pathway/bsu"
    assert result.total_found == 1
    assert list(result.results.keys()) == ["bsu01053"]
