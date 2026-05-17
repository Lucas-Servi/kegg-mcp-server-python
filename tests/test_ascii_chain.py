"""Unit tests for ASCII chain renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from kegg_mcp_server.ascii.chain import render_chain
from kegg_mcp_server.ascii.kgml import parse_kgml

FIXTURES = Path(__file__).parent / "fixtures" / "kgml"


@pytest.fixture
def hsa00010_pathway():
    xml = (FIXTURES / "hsa00010_sample.xml").read_text()
    return parse_kgml(xml)


@pytest.fixture
def signaling_pathway():
    xml = (FIXTURES / "signaling_only.xml").read_text()
    return parse_kgml(xml)


@pytest.fixture
def empty_pathway():
    xml = (FIXTURES / "empty.xml").read_text()
    return parse_kgml(xml)


def test_render_chain_hsa00010_contains_node_labels(hsa00010_pathway) -> None:
    output = render_chain(hsa00010_pathway)
    assert "D-Glucose" in output
    assert "G6P" in output
    assert "F6P" in output


def test_render_chain_hsa00010_contains_reaction_arrows(hsa00010_pathway) -> None:
    output = render_chain(hsa00010_pathway)
    assert "▶" in output


def test_render_chain_signaling_renders_relations(signaling_pathway) -> None:
    output = render_chain(signaling_pathway)
    # Should contain relation type info
    assert "PPrel" in output or "activation" in output or "phosphorylation" in output


def test_render_chain_signaling_contains_node_labels(signaling_pathway) -> None:
    output = render_chain(signaling_pathway)
    assert "MAPK1" in output
    assert "MAPK3" in output


def test_render_chain_empty_pathway(empty_pathway) -> None:
    output = render_chain(empty_pathway)
    assert "(No reactions or relations found" in output


def test_render_chain_max_width_wrapping(hsa00010_pathway) -> None:
    output = render_chain(hsa00010_pathway, max_width=40)
    for line in output.split("\n"):
        # Allow some overflow for unicode arrows and wrap continuation, but reasonable
        assert len(line) <= 50, f"Line too long ({len(line)}): {line!r}"


def test_render_chain_header_contains_title(hsa00010_pathway) -> None:
    output = render_chain(hsa00010_pathway)
    assert "Glycolysis / Gluconeogenesis" in output
