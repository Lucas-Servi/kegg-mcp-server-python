"""Tests for the BRITE hierarchy parser and `get_brite_info`.

`get_brite_info` failed on EVERY valid BRITE id. The URL was fine
(`/get/br:ko00001` → 200); the bug was parse + model. BRITE returns an indented
`A`/`B`/`C`/`D` tree, not an ENTRY/NAME flat file, so `parse_flat_entry` produced
garbage keys (`'a09100 metab'`, `'b  09101 car'`, …) and no `entry` at all —
`EntrySummary.entry` is the one field without a default, so the tool returned a
`validation_error` blaming the caller's identifier for a server-side parse bug.

Two things these tests pin that a plausible implementation gets wrong:

* **Depth comes from the leading LETTER, not the indent width.** `br:br08303`
  emits `AA ALIMENTARY TRACT AND METABOLISM` — no space after the level letter —
  so an indent-width parser reads its top level as depth 0 labelled
  `A ALIMENTARY…`. Hence the second fixture.
* **The output cap is mandatory.** `/get/br:ko00001` is 4,299,881 bytes and
  `/get/br:hsa00001` is 6.8 MB. Before the fix the tool errored out, which
  *accidentally* protected the caller's context window; fixing the parser without
  a cap would trade a confusing error for a multi-megabyte context bomb.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from kegg_mcp_server.models.brite import BriteHierarchy
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import (
    BRITE_LABEL_MAX_DEPTH,
    BRITE_LABELS_PER_LEVEL,
    parse_brite_hierarchy,
)
from kegg_mcp_server.tools.brite import _RAW_CONTENT_MAX_CHARS

from .test_tools_registration import FakeKEGG, FakeMCP, _make_ctx

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_mcp() -> FakeMCP:
    from kegg_mcp_server.tools import register_all_tools

    m = FakeMCP()
    register_all_tools(m)
    return m


def _hierarchy_text() -> str:
    return (FIXTURES / "brite_hierarchy.txt").read_text()


def _atc_text() -> str:
    return (FIXTURES / "brite_hierarchy_atc.txt").read_text()


def _call(fake_mcp: FakeMCP, raw: str, **kwargs):
    return asyncio.run(
        fake_mcp.tools["get_brite_info"](
            kwargs.pop("brite_id", "br:ko00001"),
            ctx=_make_ctx(FakeKEGG(get_response=raw)),
            **kwargs,
        )
    )


# ── Parser ──────────────────────────────────────────────────────────────────

class TestParseBriteHierarchy:
    def test_reads_the_depth_declaration_header(self):
        parsed = parse_brite_hierarchy(_hierarchy_text())
        assert parsed["deepest_level"] == "D"
        assert parsed["columns"] == ["KO"]

    def test_multi_column_header(self):
        """`br:hsa00001` declares `+D\\tGENES\\tKO` — two leaf columns."""
        parsed = parse_brite_hierarchy("+D\tGENES\tKO\n!\nA09100 Metabolism\n")
        assert parsed["columns"] == ["GENES", "KO"]

    def test_counts_lines_per_level(self):
        parsed = parse_brite_hierarchy(_hierarchy_text())
        assert parsed["level_counts"] == {"A": 2, "B": 2, "C": 3, "D": 8}
        assert parsed["total_lines"] == 15

    def test_keeps_top_level_labels_and_drops_the_leaves(self):
        parsed = parse_brite_hierarchy(_hierarchy_text())
        assert parsed["labels"]["A"] == [
            "09100 Metabolism",
            "09120 Genetic Information Processing",
        ]
        assert "09101 Carbohydrate metabolism" in parsed["labels"]["B"]
        # Level C/D are the bulk (64,695 of ko00001's 65,337 lines are level D).
        for level in "CD":
            assert level not in parsed["labels"]
            assert level in parsed["level_counts"]

    def test_extracts_last_updated_trailer(self):
        assert parse_brite_hierarchy(_hierarchy_text())["last_updated"] == "August 6, 2026"

    def test_separator_and_comment_lines_are_not_counted_as_nodes(self):
        parsed = parse_brite_hierarchy(_hierarchy_text())
        assert parsed["total_lines"] == sum(parsed["level_counts"].values())
        assert "!" not in parsed["level_counts"]
        assert "#" not in parsed["level_counts"]

    def test_depth_comes_from_the_letter_not_the_indent(self):
        """The `br:br08303` regression: `AA ALIMENTARY…` has no space after `A`."""
        parsed = parse_brite_hierarchy(_atc_text())
        assert parsed["deepest_level"] == "F"
        assert parsed["labels"]["A"] == [
            "A ALIMENTARY TRACT AND METABOLISM",
            "B BLOOD AND BLOOD FORMING ORGANS",
        ]
        # An indent-width parser would have bucketed these as depth 0.
        assert parsed["level_counts"]["A"] == 2
        assert parsed["level_counts"]["F"] == 2

    def test_deep_hierarchy_still_reports_every_level(self):
        parsed = parse_brite_hierarchy(_atc_text())
        assert set(parsed["level_counts"]) == set("ABCDEF")

    def test_labels_are_capped_per_level(self):
        wide = ["+D\tKO", "!"] + [f"A{i:05d} Node {i}" for i in range(BRITE_LABELS_PER_LEVEL + 25)]
        parsed = parse_brite_hierarchy("\n".join(wide))
        assert len(parsed["labels"]["A"]) == BRITE_LABELS_PER_LEVEL
        assert parsed["labels_truncated"] == ["A"]
        # The count is exact even though the labels were cut.
        assert parsed["level_counts"]["A"] == BRITE_LABELS_PER_LEVEL + 25

    def test_label_depth_bound_is_two_levels(self):
        assert BRITE_LABEL_MAX_DEPTH == 2

    def test_empty_text_yields_an_empty_but_valid_summary(self):
        parsed = parse_brite_hierarchy("")
        assert parsed["total_lines"] == 0
        assert parsed["level_counts"] == {}
        assert BriteHierarchy(entry="br:ko00001", **parsed).total_lines == 0

    def test_header_only_response(self):
        parsed = parse_brite_hierarchy("+D\tKO\n!\n#\n#Last updated: May 1, 2026\n")
        assert parsed["deepest_level"] == "D"
        assert parsed["total_lines"] == 0
        assert parsed["last_updated"] == "May 1, 2026"


# ── Tool ────────────────────────────────────────────────────────────────────

class TestGetBriteInfo:
    def test_summary_returns_a_hierarchy_not_an_error(self, fake_mcp: FakeMCP):
        """The regression: this used to be `ErrorResult(code="validation_error")`."""
        result = _call(fake_mcp, _hierarchy_text())
        assert isinstance(result, BriteHierarchy)
        assert result.entry == "br:ko00001"
        assert result.detail_level == "summary"
        assert result.level_counts["D"] == 8

    def test_valid_id_no_longer_reports_validation_error(self, fake_mcp: FakeMCP):
        for raw in (_hierarchy_text(), _atc_text()):
            result = _call(fake_mcp, raw)
            assert not isinstance(result, ErrorResult), result

    def test_summary_omits_raw_content(self, fake_mcp: FakeMCP):
        result = _call(fake_mcp, _hierarchy_text())
        assert result.raw_content is None
        assert result.raw_truncated is False

    def test_full_includes_raw_content_when_small(self, fake_mcp: FakeMCP):
        raw = _hierarchy_text()
        result = _call(fake_mcp, raw, detail_level="full")
        assert result.raw_content == raw
        assert result.raw_truncated is False

    def test_full_truncates_a_huge_hierarchy(self, fake_mcp: FakeMCP):
        """Sized like the real `br:ko00001` (4.3 MB)."""
        raw = _hierarchy_text() + "D      K99999  filler; padding\n" * 200_000
        assert len(raw) > 4_000_000
        result = _call(fake_mcp, raw, detail_level="full")
        assert result.raw_truncated is True
        assert len(result.raw_content) < _RAW_CONTENT_MAX_CHARS + 500
        assert "truncated" in result.raw_content

    def test_summary_of_a_huge_hierarchy_stays_tiny(self, fake_mcp: FakeMCP):
        """The whole point of the summary projection."""
        raw = _hierarchy_text() + "D      K99999  filler; padding\n" * 200_000
        result = _call(fake_mcp, raw)
        assert len(result.model_dump_json()) < 8_000
        # …while still reporting the true size.
        assert result.total_lines > 200_000

    def test_atc_hierarchy_summary(self, fake_mcp: FakeMCP):
        result = _call(fake_mcp, _atc_text(), brite_id="br:br08303")
        assert result.entry == "br:br08303"
        assert result.deepest_level == "F"
        assert result.labels["A"][0].startswith("A ALIMENTARY")

    def test_empty_response_is_still_not_found(self, fake_mcp: FakeMCP):
        """The empty-response branch precedes parsing, so it is unaffected."""
        result = _call(fake_mcp, "")
        assert isinstance(result, ErrorResult)
        assert result.code == "not_found"
        assert result.status == 404

    def test_invalid_id_is_still_a_validation_error(self, fake_mcp: FakeMCP):
        """`ValueError` must keep meaning 'bad input' after the _common split."""
        result = _call(fake_mcp, _hierarchy_text(), brite_id="not-a-brite-id")
        assert isinstance(result, ErrorResult)
        assert result.code == "validation_error"

    def test_result_is_json_serializable(self, fake_mcp: FakeMCP):
        result = _call(fake_mcp, _atc_text())
        assert json.loads(result.model_dump_json())["level_counts"]["F"] == 2
