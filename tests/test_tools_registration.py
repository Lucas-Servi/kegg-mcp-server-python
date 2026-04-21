"""Cross-module tests: every tool registers, has readOnly annotations, and
the common summary/full detail_level branch works end-to-end."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from kegg_mcp_server.models.common import EntrySummary, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.server import mcp as real_mcp
from kegg_mcp_server.tools import register_all_tools

FIXTURES = Path(__file__).parent / "fixtures"


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}
        self.annotations: dict[str, Any] = {}

    def tool(self, *_args: Any, **kwargs: Any):  # noqa: ANN201
        annotations = kwargs.get("annotations")

        def decorator(func):  # noqa: ANN001, ANN202
            self.tools[func.__name__] = func
            self.annotations[func.__name__] = annotations
            return func

        return decorator


class FakeKEGG:
    """Stub KEGG client returning canned responses per operation."""

    def __init__(
        self,
        *,
        get_response: str = "",
        find_response: str = "",
        list_response: str = "",
        link_response: str = "",
        conv_response: str = "",
        ddi_response: str = "",
        info_response: str = "",
    ) -> None:
        self._get = get_response
        self._find = find_response
        self._list = list_response
        self._link = link_response
        self._conv = conv_response
        self._ddi = ddi_response
        self._info = info_response

    async def get(self, _dbentries: str, option: str | None = None) -> str:
        return self._get

    async def find(self, _database: str, _query: str, option: str | None = None) -> str:
        return self._find

    async def list(self, _database: str) -> str:
        return self._list

    async def link(self, _target_db: str, _source: str) -> str:
        return self._link

    async def conv(self, _target_db: str, _source: str) -> str:
        return self._conv

    async def ddi(self, _dbentries: str) -> str:
        return self._ddi

    async def info(self, _database: str) -> str:
        return self._info

    async def get_batch(
        self, _entry_ids: list[str], option: str | None = None
    ) -> list[str]:
        return [self._get]


def _make_ctx(fake: FakeKEGG) -> SimpleNamespace:
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(kegg=fake))
    )


@pytest.fixture
def fake_mcp() -> FakeMCP:
    m = FakeMCP()
    register_all_tools(m)
    return m


def test_all_33_tools_register(fake_mcp: FakeMCP) -> None:
    assert len(fake_mcp.tools) == 33


def test_every_tool_has_read_only_annotation(fake_mcp: FakeMCP) -> None:
    for name, annot in fake_mcp.annotations.items():
        assert annot is not None, f"{name} missing annotations"
        assert annot.readOnlyHint is True, f"{name} must be readOnly"
        assert annot.idempotentHint is True
        assert annot.destructiveHint is False


def test_server_module_registers_same_33_tools() -> None:
    tools = asyncio.run(real_mcp.list_tools())
    assert len(tools) == 33


@pytest.mark.parametrize(
    "tool_name,fixture_file",
    [
        ("get_pathway_info", "pathway_entry.txt"),
        ("get_gene_info", "gene_entry.txt"),
    ],
)
def test_get_info_summary_returns_entry_summary(
    fake_mcp: FakeMCP, tool_name: str, fixture_file: str
) -> None:
    fake = FakeKEGG(get_response=(FIXTURES / fixture_file).read_text())
    result = asyncio.run(
        fake_mcp.tools[tool_name](
            # pathway_id / gene_id positional arg
            "x",
            detail_level="summary",
            ctx=_make_ctx(fake),
        )
    )
    assert isinstance(result, EntrySummary)
    assert result.entry  # should have pulled ENTRY field


def test_get_pathway_info_full_returns_pathway_info(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.pathway import PathwayInfo

    fake = FakeKEGG(get_response=(FIXTURES / "pathway_entry.txt").read_text())
    result = asyncio.run(
        fake_mcp.tools["get_pathway_info"]("x", detail_level="full", ctx=_make_ctx(fake))
    )
    assert isinstance(result, PathwayInfo)


def test_search_tool_applies_max_results_cap(fake_mcp: FakeMCP) -> None:
    # 200 fake rows should be clamped to MAX_ENTRIES_CAP (100) when max_results > cap
    rows = "\n".join(f"item{i}\tdescription{i}" for i in range(200))
    fake = FakeKEGG(find_response=rows)
    result = asyncio.run(
        fake_mcp.tools["search_reactions"](
            query="x", max_results=500, ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, SearchResult)
    assert result.total_found == 200
    assert result.returned_count == 100
    assert result.truncated is True


def test_search_tool_marks_not_truncated_when_fits(fake_mcp: FakeMCP) -> None:
    fake = FakeKEGG(find_response="one\tfirst\ntwo\tsecond\n")
    result = asyncio.run(
        fake_mcp.tools["search_reactions"](
            query="x", max_results=25, ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, SearchResult)
    assert result.total_found == 2
    assert result.returned_count == 2
    assert result.truncated is False


def test_batch_entry_lookup_rejects_oversize(fake_mcp: FakeMCP) -> None:
    fake = FakeKEGG()
    with pytest.raises(ValueError, match="Maximum 50"):
        asyncio.run(
            fake_mcp.tools["batch_entry_lookup"](
                entry_ids=[f"C{i:05d}" for i in range(51)], ctx=_make_ctx(fake)
            )
        )


def test_convert_identifiers_returns_conversion_result(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.common import ConversionResult

    fake = FakeKEGG(conv_response="hsa:1956\tup:P00533\n")
    result = asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="hsa", target_db="uniprot", ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, ConversionResult)
    assert result.count == 1


def test_find_related_entries_returns_link_result(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.common import LinkResult

    fake = FakeKEGG(link_response="hsa:1956\tpath:hsa04010\n")
    result = asyncio.run(
        fake_mcp.tools["find_related_entries"](
            entry_id="hsa:1956", target_db="pathway", ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, LinkResult)
    assert result.count == 1


def test_drug_interactions_parses_ddi(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.drug import DrugInteractionResult

    fake = FakeKEGG(ddi_response="D00001\tD00564\tCYP interaction\n")
    result = asyncio.run(
        fake_mcp.tools["get_drug_interactions"](
            drug_ids="D00001+D00564", ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, DrugInteractionResult)
    assert result.count == 1


def test_list_organisms_parses_three_column_rows(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.common import ListResult

    fake = FakeKEGG(list_response="T01001\thsa\tHomo sapiens\nT01002\tmmu\tMus musculus\n")
    result = asyncio.run(fake_mcp.tools["list_organisms"](ctx=_make_ctx(fake)))
    assert isinstance(result, ListResult)
    assert result.total == 2
    assert "hsa" in result.items


def test_database_info_parses_release_and_entries(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.organism import DatabaseInfo

    info_body = (
        "kegg             Kyoto Encyclopedia of Genes and Genomes\n"
        "kegg             Release 110.0+/04-20, Apr 26\n"
        "                 (total: 20,501,232 entries)\n"
    )
    fake = FakeKEGG(info_response=info_body)
    result = asyncio.run(
        fake_mcp.tools["get_database_info"](database="kegg", ctx=_make_ctx(fake))
    )
    assert isinstance(result, DatabaseInfo)
    assert result.release is not None
    assert result.entries == 20501232


def test_pathway_genes_link_tool(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.pathway import PathwayLinks

    fake = FakeKEGG(link_response="path:hsa00010\thsa:3098\npath:hsa00010\thsa:3099\n")
    result = asyncio.run(
        fake_mcp.tools["get_pathway_genes"](pathway_id="hsa00010", ctx=_make_ctx(fake))
    )
    assert isinstance(result, PathwayLinks)
    assert result.count == 2


def test_kegg_api_error_from_client_becomes_error_result(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.errors import KEGGAPIError

    class FailingKEGG(FakeKEGG):
        async def get(self, _dbentries: str, option: str | None = None) -> str:
            raise KEGGAPIError("boom", status=500, path="/get/x", retryable=True)

    result = asyncio.run(
        fake_mcp.tools["get_pathway_info"](
            "hsa00010", detail_level="summary", ctx=_make_ctx(FailingKEGG())
        )
    )
    assert isinstance(result, ErrorResult)
    assert result.retryable is True
    assert result.status == 500
