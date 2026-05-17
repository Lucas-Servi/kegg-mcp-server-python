"""Unit tests for the render_pathway_ascii MCP tool."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from kegg_mcp_server.models.ascii import AsciiPathway
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.tools import ascii_pathway

FIXTURES = Path(__file__).parent / "fixtures" / "kgml"


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, *args, **kwargs):  # noqa: ANN001, ANN201, ANN002, ANN003
        def decorator(func):  # noqa: ANN001, ANN202
            self.tools[func.__name__] = func
            return func

        return decorator


class FakeKEGG:
    def __init__(self, get_response: str = "") -> None:
        self.get_response = get_response
        self.get_calls: list[tuple[str, str]] = []

    async def get(self, entry_id: str, option: str = "") -> str:
        self.get_calls.append((entry_id, option))
        return self.get_response


def _make_ctx(fake_kegg: FakeKEGG):
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(kegg=fake_kegg))
    )


def _get_render_tool():
    fake_mcp = FakeMCP()
    ascii_pathway.register(fake_mcp)
    return fake_mcp.tools["render_pathway_ascii"]


def test_happy_path_chain_mode() -> None:
    kgml_xml = (FIXTURES / "hsa00010_sample.xml").read_text()
    render_tool = _get_render_tool()
    fake_kegg = FakeKEGG(get_response=kgml_xml)

    result = asyncio.run(
        render_tool(
            pathway_id="hsa00010",
            style="chain",
            max_width=100,
            max_height=40,
            ctx=_make_ctx(fake_kegg),
        )
    )

    assert isinstance(result, AsciiPathway)
    assert result.pathway_id == "hsa00010"
    assert result.title == "Glycolysis / Gluconeogenesis"
    assert result.organism == "hsa"
    assert result.style == "chain"
    assert result.node_count == 6
    assert result.reaction_count == 3
    assert result.relation_count == 2
    assert "D-Glucose" in result.ascii
    assert fake_kegg.get_calls == [("hsa00010", "kgml")]


def test_happy_path_grid_mode() -> None:
    kgml_xml = (FIXTURES / "hsa00010_sample.xml").read_text()
    render_tool = _get_render_tool()
    fake_kegg = FakeKEGG(get_response=kgml_xml)

    result = asyncio.run(
        render_tool(
            pathway_id="hsa00010",
            style="grid",
            max_width=100,
            max_height=40,
            ctx=_make_ctx(fake_kegg),
        )
    )

    assert isinstance(result, AsciiPathway)
    assert result.style == "grid"
    assert result.node_count == 6
    assert "Legend:" in result.ascii


def test_empty_kgml_returns_error() -> None:
    render_tool = _get_render_tool()
    fake_kegg = FakeKEGG(get_response="")

    result = asyncio.run(
        render_tool(
            pathway_id="hsa00010",
            style="chain",
            max_width=100,
            max_height=40,
            ctx=_make_ctx(fake_kegg),
        )
    )

    assert isinstance(result, ErrorResult)
    assert result.code == "kgml_not_available"
    assert "hsa00010" in result.error


def test_invalid_pathway_id_returns_error() -> None:
    render_tool = _get_render_tool()
    fake_kegg = FakeKEGG(get_response="")

    result = asyncio.run(
        render_tool(
            pathway_id="../../etc",
            style="chain",
            max_width=100,
            max_height=40,
            ctx=_make_ctx(fake_kegg),
        )
    )

    assert isinstance(result, ErrorResult)
    assert result.code == "validation_error"
