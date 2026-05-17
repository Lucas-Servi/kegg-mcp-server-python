"""Unit tests for ASCII grid renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from kegg_mcp_server.ascii.grid import render_grid
from kegg_mcp_server.ascii.kgml import parse_kgml

FIXTURES = Path(__file__).parent / "fixtures" / "kgml"


@pytest.fixture
def hsa00010_pathway():
    xml = (FIXTURES / "hsa00010_sample.xml").read_text()
    return parse_kgml(xml)


@pytest.fixture
def empty_pathway():
    xml = (FIXTURES / "empty.xml").read_text()
    return parse_kgml(xml)


def test_render_grid_contains_node_labels(hsa00010_pathway) -> None:
    output = render_grid(hsa00010_pathway)
    # Grid uses short labels in brackets
    assert "[" in output
    assert "]" in output
    # Should contain at least some node labels (possibly truncated)
    has_label = any(
        label in output
        for label in ("D-Gluco~", "D-Glucos", "G6P", "F6P", "GCK", "PFKM", "GPI")
    )
    assert has_label, "No expected node labels found in grid output"


def test_render_grid_includes_legend(hsa00010_pathway) -> None:
    output = render_grid(hsa00010_pathway)
    assert "Legend:" in output


def test_render_grid_respects_height(hsa00010_pathway) -> None:
    height = 30
    output = render_grid(hsa00010_pathway, height=height)
    lines = output.split("\n")
    # Total lines should be bounded: header(3) + grid(height) + legend(~nodes+2)
    # Grid portion itself should not exceed height
    # Find the grid section (between header separator and Legend:)
    grid_start = None
    grid_end = None
    for i, line in enumerate(lines):
        if line.startswith("="):
            grid_start = i + 2  # skip separator + blank line
        if line.strip() == "Legend:":
            grid_end = i
            break
    if grid_start is not None and grid_end is not None:
        grid_lines = grid_end - grid_start
        assert grid_lines <= height, f"Grid has {grid_lines} lines, expected <= {height}"


def test_render_grid_empty_falls_back_to_chain(empty_pathway) -> None:
    output = render_grid(empty_pathway)
    assert "No spatial coordinates" in output or "falling back to chain mode" in output
