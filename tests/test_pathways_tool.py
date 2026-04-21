"""Unit tests for pathway search tool behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from kegg_mcp_server.tools import pathways


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):  # noqa: ANN001, ANN201, ANN002, ANN003
        def decorator(func):  # noqa: ANN001, ANN202
            self.tools[func.__name__] = func
            return func

        return decorator


class FakeKEGG:
    def __init__(self, find_response: str = "", list_response: str = "", link_response: str = "") -> None:
        self.find_response = find_response
        self.list_response = list_response
        self.link_response = link_response
        self.find_calls: list[tuple[str, str]] = []
        self.list_calls: list[str] = []
        self.link_calls: list[tuple[str, str]] = []

    async def find(self, database: str, query: str) -> str:
        self.find_calls.append((database, query))
        return self.find_response

    async def list(self, database: str) -> str:
        self.list_calls.append(database)
        return self.list_response

    async def link(self, target_db: str, source: str) -> str:
        self.link_calls.append((target_db, source))
        return self.link_response


def _make_ctx(fake_kegg: FakeKEGG):
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(kegg=fake_kegg))
    )


def _get_search_pathways_tool():
    fake_mcp = FakeMCP()
    pathways.register(fake_mcp)
    return fake_mcp.tools["search_pathways"]


def _get_link_tools():
    fake_mcp = FakeMCP()
    pathways.register(fake_mcp)
    return (
        fake_mcp.tools["get_pathway_genes"],
        fake_mcp.tools["get_pathway_compounds"],
        fake_mcp.tools["get_pathway_reactions"],
    )


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


# --- path: prefix normalization tests ---


def test_get_pathway_genes_adds_path_prefix() -> None:
    get_pathway_genes, _, _ = _get_link_tools()
    link_resp = "path:pae00405\tpae:PA0001\npath:pae00405\tpae:PA0002\n"
    fake_kegg = FakeKEGG(link_response=link_resp)

    asyncio.run(get_pathway_genes(pathway_id="pae00405", ctx=_make_ctx(fake_kegg)))

    assert fake_kegg.link_calls == [("genes", "path:pae00405")]


def test_get_pathway_genes_keeps_existing_prefix() -> None:
    get_pathway_genes, _, _ = _get_link_tools()
    fake_kegg = FakeKEGG(link_response="")

    asyncio.run(get_pathway_genes(pathway_id="path:pae00405", ctx=_make_ctx(fake_kegg)))

    assert fake_kegg.link_calls == [("genes", "path:pae00405")]


def test_get_pathway_compounds_adds_path_prefix() -> None:
    _, get_pathway_compounds, _ = _get_link_tools()
    fake_kegg = FakeKEGG(link_response="")

    asyncio.run(get_pathway_compounds(pathway_id="map00010", ctx=_make_ctx(fake_kegg)))

    assert fake_kegg.link_calls == [("compound", "path:map00010")]


def test_get_pathway_reactions_adds_path_prefix() -> None:
    _, _, get_pathway_reactions = _get_link_tools()
    fake_kegg = FakeKEGG(link_response="")

    asyncio.run(get_pathway_reactions(pathway_id="hsa00010", ctx=_make_ctx(fake_kegg)))

    assert fake_kegg.link_calls == [("reaction", "path:hsa00010")]
