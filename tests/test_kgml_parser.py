"""Unit tests for KGML XML parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from kegg_mcp_server.ascii.kgml import parse_kgml

FIXTURES = Path(__file__).parent / "fixtures" / "kgml"


@pytest.fixture
def hsa00010_xml() -> str:
    return (FIXTURES / "hsa00010_sample.xml").read_text()


@pytest.fixture
def signaling_xml() -> str:
    return (FIXTURES / "signaling_only.xml").read_text()


@pytest.fixture
def empty_xml() -> str:
    return (FIXTURES / "empty.xml").read_text()


def test_parse_hsa00010_node_count(hsa00010_xml: str) -> None:
    pathway = parse_kgml(hsa00010_xml)
    assert len(pathway.nodes) == 6


def test_parse_hsa00010_reaction_count(hsa00010_xml: str) -> None:
    pathway = parse_kgml(hsa00010_xml)
    assert len(pathway.reactions) == 3


def test_parse_hsa00010_relation_count(hsa00010_xml: str) -> None:
    pathway = parse_kgml(hsa00010_xml)
    assert len(pathway.relations) == 2


def test_parse_signaling_node_count(signaling_xml: str) -> None:
    pathway = parse_kgml(signaling_xml)
    assert len(pathway.nodes) == 4


def test_parse_signaling_no_reactions(signaling_xml: str) -> None:
    pathway = parse_kgml(signaling_xml)
    assert len(pathway.reactions) == 0


def test_parse_signaling_relation_count(signaling_xml: str) -> None:
    pathway = parse_kgml(signaling_xml)
    assert len(pathway.relations) == 3


def test_parse_empty_no_nodes(empty_xml: str) -> None:
    pathway = parse_kgml(empty_xml)
    assert len(pathway.nodes) == 0


def test_parse_empty_no_reactions(empty_xml: str) -> None:
    pathway = parse_kgml(empty_xml)
    assert len(pathway.reactions) == 0


def test_parse_empty_no_relations(empty_xml: str) -> None:
    pathway = parse_kgml(empty_xml)
    assert len(pathway.relations) == 0


def test_nodes_have_correct_labels(hsa00010_xml: str) -> None:
    pathway = parse_kgml(hsa00010_xml)
    labels = {n.label for n in pathway.nodes.values()}
    assert "D-Glucose" in labels
    assert "G6P" in labels
    assert "F6P" in labels
    assert "GCK" in labels
    assert "PFKM" in labels
    assert "GPI" in labels


def test_reaction_substrates_products_linked(hsa00010_xml: str) -> None:
    pathway = parse_kgml(hsa00010_xml)
    # First reaction: substrate id=1 (D-Glucose), product id=2 (G6P)
    rxn = pathway.reactions[0]
    assert 1 in rxn.substrate_ids
    assert 2 in rxn.product_ids


def test_malformed_xml_raises() -> None:
    import defusedxml.ElementTree as ET

    with pytest.raises(ET.ParseError):
        parse_kgml("<not valid xml<<<")
