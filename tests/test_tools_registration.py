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
    assert len(fake_mcp.tools) == 34


def test_every_tool_has_read_only_annotation(fake_mcp: FakeMCP) -> None:
    # snake_case: mcp>=2 renamed every wire field on the Python side. The
    # camelCase spellings raise AttributeError, so this test is also the guard
    # that the annotations constant was migrated and not just constructed.
    for name, annot in fake_mcp.annotations.items():
        assert annot is not None, f"{name} missing annotations"
        assert annot.read_only_hint is True, f"{name} must be readOnly"
        assert annot.idempotent_hint is True
        assert annot.destructive_hint is False


def test_server_module_registers_same_33_tools() -> None:
    tools = asyncio.run(real_mcp.list_tools())
    assert len(tools) == 34


@pytest.mark.parametrize(
    "tool_name,fixture_file,entry_id",
    [
        ("get_pathway_info", "pathway_entry.txt", "hsa00010"),
        ("get_gene_info", "gene_entry.txt", "hsa:1956"),
    ],
)
def test_get_info_summary_returns_entry_summary(
    fake_mcp: FakeMCP, tool_name: str, fixture_file: str, entry_id: str
) -> None:
    fake = FakeKEGG(get_response=(FIXTURES / fixture_file).read_text())
    result = asyncio.run(
        fake_mcp.tools[tool_name](
            entry_id,
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
        fake_mcp.tools["get_pathway_info"]("hsa00010", detail_level="full", ctx=_make_ctx(fake))
    )
    assert isinstance(result, PathwayInfo)


@pytest.mark.parametrize(
    "tool_name,entry_id",
    [
        ("get_pathway_info", "hsa00010"),
        ("get_gene_info", "hsa:1956"),
        ("get_compound_info", "C00002"),
        ("get_reaction_info", "R00756"),
        ("get_enzyme_info", "1.1.1.1"),
        ("get_disease_info", "H00004"),
        ("get_drug_info", "D00001"),
        ("get_module_info", "M00001"),
        ("get_ko_info", "K00844"),
        ("get_glycan_info", "G00001"),
        ("get_brite_info", "br00001"),
    ],
)
def test_get_info_empty_response_returns_not_found(
    fake_mcp: FakeMCP, tool_name: str, entry_id: str
) -> None:
    result = asyncio.run(fake_mcp.tools[tool_name](entry_id, ctx=_make_ctx(FakeKEGG())))

    assert isinstance(result, ErrorResult)
    assert result.code == "not_found"
    assert result.status == 404
    assert result.retryable is False
    assert entry_id in result.error


def test_get_gene_info_omits_sequences_unless_requested(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.gene import GeneInfo

    fake = FakeKEGG(get_response=(FIXTURES / "gene_entry.txt").read_text())
    result = asyncio.run(
        fake_mcp.tools["get_gene_info"](
            "hsa:1956",
            detail_level="full",
            include_sequence=False,
            ctx=_make_ctx(fake),
        )
    )

    assert isinstance(result, GeneInfo)
    assert result.aaseq is None
    assert result.ntseq is None


def test_get_gene_info_fetches_only_missing_requested_sequence(fake_mcp: FakeMCP) -> None:
    from kegg_mcp_server.models.gene import GeneInfo

    class PartialSequenceKEGG(FakeKEGG):
        def __init__(self) -> None:
            super().__init__()
            self.options: list[str | None] = []

        async def get(self, _dbentries: str, option: str | None = None) -> str:
            self.options.append(option)
            if option == "ntseq":
                return ">hsa:1956\nATGGCC"
            return (
                "ENTRY       1956      CDS\nNAME        EGFR\n"
                "AASEQ       3\n            MAA\n///"
            )

    fake = PartialSequenceKEGG()
    result = asyncio.run(
        fake_mcp.tools["get_gene_info"](
            "hsa:1956",
            detail_level="full",
            include_sequence=True,
            ctx=_make_ctx(fake),
        )
    )

    assert isinstance(result, GeneInfo)
    assert result.aaseq == "MAA"
    assert result.ntseq == "ATGGCC"
    assert fake.options == [None, "ntseq"]


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
    result = asyncio.run(
        fake_mcp.tools["batch_entry_lookup"](
            entry_ids=[f"C{i:05d}" for i in range(51)], ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, ErrorResult)
    assert "Maximum 50" in result.error


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


class _RecordingConvKEGG(FakeKEGG):
    """Records the (target_db, source) pair each conv call would put in the URL."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.conv_calls: list[tuple[str, str]] = []

    async def conv(self, target_db: str, source: str) -> str:  # noqa: ANN101
        self.conv_calls.append((target_db, source))
        return self._conv


def test_convert_identifiers_prefixes_entry_ids_with_source_db(fake_mcp: FakeMCP) -> None:
    """The D4 regression: source_db was discarded whenever entry_ids was given.

    `/conv/uniprot/1956` is a 400 — KEGG needs every id namespaced by its own
    database — so the entry_ids path failed on every call while looking valid.
    """
    fake = _RecordingConvKEGG(conv_response="hsa:1956\tup:P00533\n")
    result = asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="hsa", target_db="uniprot", entry_ids=["1956"], ctx=_make_ctx(fake)
        )
    )
    assert fake.conv_calls == [("uniprot", "hsa:1956")]
    assert result.count == 1


def test_convert_identifiers_does_not_double_prefix(fake_mcp: FakeMCP) -> None:
    fake = _RecordingConvKEGG(conv_response="hsa:1956\tup:P00533\n")
    asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="hsa", target_db="uniprot", entry_ids=["hsa:1956"], ctx=_make_ctx(fake)
        )
    )
    assert fake.conv_calls == [("uniprot", "hsa:1956")]


def test_convert_identifiers_joins_multiple_ids_and_caps_at_ten(fake_mcp: FakeMCP) -> None:
    """KEGG's GET limit is 10 entries; each still carries its own prefix."""
    fake = _RecordingConvKEGG(conv_response="")
    asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="compound",
            target_db="chebi",
            entry_ids=[f"C{i:05d}" for i in range(12)],
            ctx=_make_ctx(fake),
        )
    )
    (_, source), = fake.conv_calls
    ids = source.split("+")
    assert len(ids) == 10
    assert ids[0] == "compound:C00000"


def test_convert_identifiers_rejects_kegg_target_without_calling_kegg(
    fake_mcp: FakeMCP,
) -> None:
    """The docstring used to steer callers at target_db='kegg'; /conv/kegg/… is 400.

    The rejection must happen before the HTTP call — otherwise every bad pair
    still costs a round-trip to KEGG and a rate-limit slot.
    """
    fake = _RecordingConvKEGG(conv_response="")
    result = asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="compound", target_db="kegg", entry_ids=["C00002"], ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, ErrorResult)
    assert result.code == "validation_error"
    assert fake.conv_calls == []


def test_convert_identifiers_rejects_cross_kind_pair(fake_mcp: FakeMCP) -> None:
    """`compound` and `uniprot` are both real conv databases; the pair is 400."""
    fake = _RecordingConvKEGG(conv_response="")
    result = asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="compound", target_db="uniprot", ctx=_make_ctx(fake)
        )
    )
    assert isinstance(result, ErrorResult)
    assert result.code == "validation_error"
    assert fake.conv_calls == []


def test_convert_identifiers_normalizes_the_pair(fake_mcp: FakeMCP) -> None:
    """A lowercase T-number reaches KEGG uppercased, as /conv requires."""
    fake = _RecordingConvKEGG(conv_response="hsa:1956\tup:P00533\n")
    result = asyncio.run(
        fake_mcp.tools["convert_identifiers"](
            source_db="t01001", target_db="UniProt", entry_ids=["1956"], ctx=_make_ctx(fake)
        )
    )
    assert fake.conv_calls == [("uniprot", "T01001:1956")]
    assert result.source_db == "T01001"
    assert result.target_db == "uniprot"


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
    """Tolerated fallback shape. NOTE: the live endpoint returns 2 columns —
    see test_list_organisms_parses_genome_two_column_rows for the real shape."""
    from kegg_mcp_server.models.common import ListResult

    fake = FakeKEGG(list_response="T01001\thsa\tHomo sapiens\nT01002\tmmu\tMus musculus\n")
    result = asyncio.run(fake_mcp.tools["list_organisms"](ctx=_make_ctx(fake)))
    assert isinstance(result, ListResult)
    assert result.total == 2
    assert "hsa" in result.items


def test_list_organisms_queries_the_genome_database(fake_mcp: FakeMCP) -> None:
    """/list/organism was retired and now 400s; /list/genome is the live path."""
    requested: list[str] = []

    class RecordingKEGG(FakeKEGG):
        async def list(self, database: str) -> str:  # noqa: ANN101
            requested.append(database)
            return self._list

    fake = RecordingKEGG(list_response="T01001\thsa; Homo sapiens (human)\n")
    asyncio.run(fake_mcp.tools["list_organisms"](ctx=_make_ctx(fake)))
    assert requested == ["genome"]


def test_list_organisms_parses_genome_two_column_rows(fake_mcp: FakeMCP) -> None:
    """Real /list/genome rows are "T-number\\tcode; description"."""
    from kegg_mcp_server.models.common import ListResult

    fake = FakeKEGG(
        list_response=(
            "T01001\thsa; Homo sapiens (human)\n"
            "T01005\tptr; Pan troglodytes (chimpanzee)\n"
        )
    )
    result = asyncio.run(fake_mcp.tools["list_organisms"](ctx=_make_ctx(fake)))
    assert isinstance(result, ListResult)
    assert result.total == 2
    # Keyed by organism code, NOT the T-number, and the code is stripped
    # out of the description.
    assert result.items["hsa"] == "Homo sapiens (human)"
    assert result.items["ptr"] == "Pan troglodytes (chimpanzee)"
    assert "T01001" not in result.items
    assert result.truncated is False


def test_list_organisms_filters_by_query(fake_mcp: FakeMCP) -> None:
    fake = FakeKEGG(
        list_response=(
            "T01001\thsa; Homo sapiens (human)\n"
            "T00010\tbsu; Bacillus subtilis subsp. subtilis 168\n"
        )
    )
    result = asyncio.run(
        fake_mcp.tools["list_organisms"](query="bacillus", ctx=_make_ctx(fake))
    )
    assert set(result.items) == {"bsu"}
    assert result.total == 1

    by_code = asyncio.run(
        fake_mcp.tools["list_organisms"](query="hsa", ctx=_make_ctx(fake))
    )
    assert set(by_code.items) == {"hsa"}


def test_list_organisms_bounds_output_and_flags_truncation(fake_mcp: FakeMCP) -> None:
    """~12k organisms must never all land in one tool response."""
    from kegg_mcp_server.tools._common import MAX_ENTRIES_CAP

    rows = "".join(f"T{i:05d}\torg{i}; Organism {i}\n" for i in range(250))
    fake = FakeKEGG(list_response=rows)

    result = asyncio.run(fake_mcp.tools["list_organisms"](ctx=_make_ctx(fake)))
    assert result.total == 250
    assert len(result.items) == MAX_ENTRIES_CAP
    assert result.truncated is True

    # A pathological max_results is clamped, not honoured.
    huge = asyncio.run(
        fake_mcp.tools["list_organisms"](max_results=100_000, ctx=_make_ctx(fake))
    )
    assert len(huge.items) == MAX_ENTRIES_CAP

    small = asyncio.run(
        fake_mcp.tools["list_organisms"](max_results=5, ctx=_make_ctx(fake))
    )
    assert len(small.items) == 5
    assert small.truncated is True


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
