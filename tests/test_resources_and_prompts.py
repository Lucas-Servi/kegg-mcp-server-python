"""Tests for MCP resource templates and prompt functions."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

from kegg_mcp_server.prompts import register_prompts
from kegg_mcp_server.resources import register_resources


class FakeKEGG:
    def __init__(
        self,
        *,
        get_response: str = "",
        list_response: str = "",
        find_response: str = "",
    ) -> None:
        self._get = get_response
        self._list = list_response
        self._find = find_response
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def get(self, dbentries: str, option: str | None = None) -> str:
        self.calls.append(("get", (dbentries, option)))
        return self._get

    async def list(self, database: str) -> str:
        self.calls.append(("list", (database,)))
        return self._list

    async def find(self, database: str, query: str, option: str | None = None) -> str:
        self.calls.append(("find", (database, query, option)))
        return self._find


class _FakeMCP:
    def __init__(self) -> None:
        self.resources: dict[str, Any] = {}
        self.prompts: dict[str, Any] = {}

    def resource(self, uri: str):  # noqa: ANN201
        def decorator(func):  # noqa: ANN001, ANN202
            self.resources[uri] = func
            return func

        return decorator

    def prompt(self):  # noqa: ANN201
        def decorator(func):  # noqa: ANN001, ANN202
            self.prompts[func.__name__] = func
            return func

        return decorator


def _ctx(fake: FakeKEGG) -> SimpleNamespace:
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(kegg=fake))
    )


@pytest.fixture
def mcp() -> _FakeMCP:
    m = _FakeMCP()
    register_resources(m)
    register_prompts(m)
    return m


def test_registers_nine_resource_templates(mcp: _FakeMCP) -> None:
    assert len(mcp.resources) == 9
    assert "kegg://pathway/{pathway_id}" in mcp.resources
    assert "kegg://pathway/{pathway_id}/ascii" in mcp.resources
    assert "kegg://search/{database}/{query}" in mcp.resources


def test_registers_four_prompts(mcp: _FakeMCP) -> None:
    assert set(mcp.prompts) == {
        "pathway_enrichment_analysis",
        "drug_target_investigation",
        "metabolic_pathway_comparison",
        "visualize_pathway",
    }


@pytest.mark.parametrize(
    "uri,arg,fake_kwarg",
    [
        ("kegg://pathway/{pathway_id}", "hsa00010", "get_response"),
        ("kegg://gene/{gene_id}", "hsa:1956", "get_response"),
        ("kegg://compound/{compound_id}", "C00002", "get_response"),
        ("kegg://reaction/{reaction_id}", "R00756", "get_response"),
        ("kegg://disease/{disease_id}", "H00004", "get_response"),
        ("kegg://drug/{drug_id}", "D00001", "get_response"),
    ],
)
def test_entry_resources_return_json_parse_of_get(
    mcp: _FakeMCP, uri: str, arg: str, fake_kwarg: str
) -> None:
    fake = FakeKEGG(**{fake_kwarg: "ENTRY       X00001            Type\n///\n"})
    func = mcp.resources[uri]
    out = asyncio.run(func(arg, ctx=_ctx(fake)))
    parsed = json.loads(out)
    assert parsed["entry"] == "X00001"


def test_entry_resource_raises_not_found_on_empty_response(mcp: _FakeMCP) -> None:
    """Was: `'{}'` on a 404, which looks like a valid empty entry."""
    fake = FakeKEGG(get_response="")
    func = mcp.resources["kegg://gene/{gene_id}"]
    with pytest.raises(ResourceNotFoundError):
        asyncio.run(func("hsa:1956", ctx=_ctx(fake)))


def test_entry_resource_validates_the_identifier(mcp: _FakeMCP) -> None:
    """A path-traversal/injection id must be rejected before it reaches the client,
    not percent-decoded straight into the `/get` path."""
    fake = FakeKEGG(get_response="ENTRY       X00001            Type\n///\n")
    func = mcp.resources["kegg://gene/{gene_id}"]
    with pytest.raises(ValueError):
        asyncio.run(func("hsa:1956/aaseq", ctx=_ctx(fake)))
    assert fake.calls == []


def test_entry_resource_output_is_capped_and_compact(mcp: _FakeMCP) -> None:
    """Every dict field is bounded, and the JSON isn't pretty-printed."""
    from kegg_mcp_server.tools._common import MAX_ENTRIES_CAP

    pathway_lines = "\n".join(f"            hsa{i:05d}  Pathway {i}" for i in range(150))
    raw = f"ENTRY       X00001            Type\nPATHWAY{pathway_lines[7:]}\n///\n"
    fake = FakeKEGG(get_response=raw)
    func = mcp.resources["kegg://pathway/{pathway_id}"]
    out = asyncio.run(func("hsa00010", ctx=_ctx(fake)))
    assert "\n" not in out  # compact, not indent=2
    parsed = json.loads(out)
    assert len(parsed["pathway"]) == MAX_ENTRIES_CAP
    assert parsed["pathway_truncated"] is True


def test_organism_resource_uses_list(mcp: _FakeMCP) -> None:
    fake = FakeKEGG(list_response="bsu00010\tGlycolysis - B. subtilis\n")
    out = asyncio.run(
        mcp.resources["kegg://organism/{org_code}"]("bsu", ctx=_ctx(fake))
    )
    parsed = json.loads(out)
    assert parsed["organism"] == "bsu"
    assert parsed["count"] == 1


def test_search_resource_uses_find(mcp: _FakeMCP) -> None:
    fake = FakeKEGG(find_response="path:map00010\tGlycolysis\n")
    out = asyncio.run(
        mcp.resources["kegg://search/{database}/{query}"](
            "pathway", "glycolysis", ctx=_ctx(fake)
        )
    )
    parsed = json.loads(out)
    assert parsed["database"] == "pathway"
    assert parsed["count"] == 1


def test_pathway_enrichment_prompt_includes_inputs(mcp: _FakeMCP) -> None:
    text = mcp.prompts["pathway_enrichment_analysis"](
        gene_list="EGFR,TP53", organism="hsa"
    )
    assert "EGFR,TP53" in text
    assert "hsa" in text
    assert "search_genes" in text


def test_drug_prompt_names_the_drug(mcp: _FakeMCP) -> None:
    text = mcp.prompts["drug_target_investigation"](drug_name="imatinib")
    assert "imatinib" in text
    assert "search_drugs" in text


def test_visualize_pathway_prompt_does_not_double_prefix_a_map_id(mcp: _FakeMCP) -> None:
    """`pathway_id='map00010'` + default organism='hsa' must stay 'map00010',
    not become the nonsensical 'hsamap00010'."""
    text = mcp.prompts["visualize_pathway"](pathway_id="map00010")
    assert "map00010" in text
    assert "hsamap00010" not in text


def test_visualize_pathway_prompt_prefixes_a_bare_number(mcp: _FakeMCP) -> None:
    text = mcp.prompts["visualize_pathway"](pathway_id="00010", organism="eco")
    assert "eco00010" in text


def test_metabolic_comparison_prompt_expands_organisms(mcp: _FakeMCP) -> None:
    text = mcp.prompts["metabolic_pathway_comparison"](
        pathway_id="map00010", organisms="hsa,eco"
    )
    # Both organisms should appear in the generated plan
    assert "hsa00010" in text
    assert "eco00010" in text
