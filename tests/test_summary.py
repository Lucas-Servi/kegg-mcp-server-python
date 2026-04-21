"""Tests for summarize_flat_entry and EntrySummary projection."""

from __future__ import annotations

import json
from pathlib import Path

from kegg_mcp_server.models.common import EntrySummary
from kegg_mcp_server.parsers import parse_flat_entry, summarize_flat_entry

FIXTURES = Path(__file__).parent / "fixtures"


def test_summary_keeps_scalar_header_fields() -> None:
    parsed = parse_flat_entry((FIXTURES / "pathway_entry.txt").read_text())
    summary = summarize_flat_entry(parsed)
    assert summary["entry"] == parsed["entry"]
    assert summary["name"] == parsed["name"]
    # cls / description are scalar fields; they should survive
    if "cls" in parsed:
        assert summary["cls"] == parsed["cls"]


def test_summary_replaces_linked_entities_with_counts() -> None:
    parsed = parse_flat_entry((FIXTURES / "gene_entry.txt").read_text())
    summary = summarize_flat_entry(parsed)
    # The gene fixture has a PATHWAY section; the summary should expose a count,
    # not the full dict.
    if isinstance(parsed.get("pathway"), dict) and parsed["pathway"]:
        assert summary["counts"]["pathway"] == len(parsed["pathway"])
        assert "pathway" not in summary  # raw list not surfaced


def test_summary_drops_long_text_sections() -> None:
    parsed = parse_flat_entry((FIXTURES / "gene_entry.txt").read_text())
    summary = summarize_flat_entry(parsed)
    for big_field in ("aaseq", "ntseq", "comment", "remark", "raw_content"):
        assert big_field not in summary


def test_summary_is_dramatically_smaller_than_full_parse() -> None:
    parsed = parse_flat_entry((FIXTURES / "gene_entry.txt").read_text())
    full_size = len(json.dumps(parsed, default=str))
    summary_size = len(json.dumps(summarize_flat_entry(parsed), default=str))
    # Gene entries contain long sequences — summary must shrink them substantially
    assert summary_size * 5 < full_size, (
        f"Expected summary to be <=20% of full size, got "
        f"{summary_size} vs {full_size}"
    )


def test_summary_loads_into_entry_summary_model() -> None:
    parsed = parse_flat_entry((FIXTURES / "pathway_entry.txt").read_text())
    model = EntrySummary(**summarize_flat_entry(parsed))
    assert model.entry == parsed["entry"]
    assert model.detail_level == "summary"


def test_summary_samples_top_dblinks() -> None:
    # Construct a parsed dict with many dblinks; ensure sampling caps to 5
    parsed = {
        "entry": "X00001",
        "name": "example",
        "dblinks": {f"DB{i}": [f"id{i}"] for i in range(20)},
    }
    summary = summarize_flat_entry(parsed)
    assert len(summary["dblinks_sample"]) == 5
