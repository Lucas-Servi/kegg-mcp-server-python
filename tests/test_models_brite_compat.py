"""Model compatibility tests for KEGG BRITE payload variants."""

from kegg_mcp_server.models.gene import GeneInfo
from kegg_mcp_server.models.orthology import KOInfo


def test_ko_info_accepts_brite_text_block() -> None:
    item = KOInfo(
        entry="K15654",
        name="sfp",
        brite="KEGG Orthology (KO) [BR:ko00001]\n  Metabolism; Lipid metabolism",
    )
    assert isinstance(item.brite, str)
    assert "KEGG Orthology" in item.brite


def test_gene_info_accepts_brite_text_block() -> None:
    item = GeneInfo(
        entry="bsu:BSU_00010",
        name="test_gene",
        brite="Genes and proteins [BR:bsu00001]",
    )
    assert isinstance(item.brite, str)
    assert item.brite.startswith("Genes and proteins")


def test_ko_info_accepts_brite_mapping() -> None:
    item = KOInfo(
        entry="K00001",
        name="some_ko",
        brite={"ko01000": "Enzymes"},
    )
    assert isinstance(item.brite, dict)
    assert item.brite["ko01000"] == "Enzymes"
