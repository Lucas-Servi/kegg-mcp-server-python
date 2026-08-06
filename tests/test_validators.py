"""Unit tests for KEGG identifier validators."""

from __future__ import annotations

import pytest

from kegg_mcp_server.validators import (
    validate_brite_id,
    validate_compound_id,
    validate_conv_pair,
    validate_disease_id,
    validate_drug_id,
    validate_enzyme_id,
    validate_gene_id,
    validate_glycan_id,
    validate_info_database,
    validate_ko_id,
    validate_link_database,
    validate_module_id,
    validate_organism_code,
    validate_pathway_id,
    validate_query,
    validate_reaction_id,
)

# --- validate_pathway_id ---


@pytest.mark.parametrize(
    "value",
    ["hsa00010", "path:map00010", "eco00350"],
)
def test_validate_pathway_id_valid(value: str) -> None:
    result = validate_pathway_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["../../etc", "123", "", "NOTVALID"],
)
def test_validate_pathway_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_pathway_id(value)


# --- validate_gene_id ---


@pytest.mark.parametrize(
    "value",
    ["hsa:1956", "eco:b0001"],
)
def test_validate_gene_id_valid(value: str) -> None:
    result = validate_gene_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["hsa", "1956", ""],
)
def test_validate_gene_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_gene_id(value)


# --- validate_compound_id ---


@pytest.mark.parametrize(
    "value",
    ["C00002", "cpd:C00031"],
)
def test_validate_compound_id_valid(value: str) -> None:
    result = validate_compound_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["X00001", "C0002", ""],
)
def test_validate_compound_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_compound_id(value)


# --- validate_reaction_id ---


@pytest.mark.parametrize(
    "value",
    ["R00756", "rn:R00001"],
)
def test_validate_reaction_id_valid(value: str) -> None:
    result = validate_reaction_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["X00001", ""],
)
def test_validate_reaction_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_reaction_id(value)


# --- validate_enzyme_id ---


@pytest.mark.parametrize(
    "value",
    ["1.1.1.1", "ec:2.7.1.1"],
)
def test_validate_enzyme_id_valid(value: str) -> None:
    result = validate_enzyme_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["1.1.1", "abc", ""],
)
def test_validate_enzyme_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_enzyme_id(value)


# --- validate_ko_id ---


@pytest.mark.parametrize(
    "value",
    ["K00844", "ko:K00001"],
)
def test_validate_ko_id_valid(value: str) -> None:
    result = validate_ko_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["K0084", ""],
)
def test_validate_ko_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_ko_id(value)


# --- validate_disease_id ---


@pytest.mark.parametrize(
    "value",
    ["H00004"],
)
def test_validate_disease_id_valid(value: str) -> None:
    result = validate_disease_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["D00001", ""],
)
def test_validate_disease_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_disease_id(value)


# --- validate_drug_id ---


@pytest.mark.parametrize(
    "value",
    ["D00001"],
)
def test_validate_drug_id_valid(value: str) -> None:
    result = validate_drug_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["H00004", ""],
)
def test_validate_drug_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_drug_id(value)


# --- validate_module_id ---


@pytest.mark.parametrize(
    "value",
    ["M00001"],
)
def test_validate_module_id_valid(value: str) -> None:
    result = validate_module_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["K00001", ""],
)
def test_validate_module_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_module_id(value)


# --- validate_glycan_id ---


@pytest.mark.parametrize(
    "value",
    ["G00001"],
)
def test_validate_glycan_id_valid(value: str) -> None:
    result = validate_glycan_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["C00001", ""],
)
def test_validate_glycan_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_glycan_id(value)


# --- validate_brite_id ---


@pytest.mark.parametrize(
    "value",
    ["br00001", "ko00001"],
)
def test_validate_brite_id_valid(value: str) -> None:
    result = validate_brite_id(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["xx", ""],
)
def test_validate_brite_id_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_brite_id(value)


# --- validate_organism_code ---


@pytest.mark.parametrize(
    "value",
    ["hsa", "eco", "mmu", "map"],
)
def test_validate_organism_code_valid(value: str) -> None:
    result = validate_organism_code(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["a", "ABCDE", "12", ""],
)
def test_validate_organism_code_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_organism_code(value)


# --- operation-specific database validators ---


@pytest.mark.parametrize(
    "value",
    ["pathway", "vp", "vtax", "vgenome", "rmodule", "ntmap", "dgroup", "hsa", "T01001"],
)
def test_validate_info_database_valid(value: str) -> None:
    result = validate_info_database(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["nonexist", "organism", "taxonomy", ""],
)
def test_validate_info_database_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_info_database(value)


@pytest.mark.parametrize(
    "value",
    [
        "pathway",
        "genes",
        "vp",
        "vtax",
        "vgenome",
        "rmodule",
        "ntmap",
        "dgroup",
        "taxonomy",
        "atc",
        "hsa",
        "T01001",
    ],
)
def test_validate_link_database_valid(value: str) -> None:
    assert validate_link_database(value) == value


@pytest.mark.parametrize("value", ["nonexist", "organism", "kegg", ""])
def test_validate_link_database_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_link_database(value)


def test_database_validators_normalize_case() -> None:
    assert validate_info_database(" HSA ") == "hsa"
    assert validate_link_database("t01001") == "T01001"


# --- validate_conv_pair ---
#
# Every pair below was probed against the live API (rest.kegg.jp) — the comments
# record the observed status, not a guess. The reason this validates the *pair*
# and not each side is the second block: `pathway`, `compound`, `uniprot` and
# `chebi` are all legitimate conv names, yet those combinations are 400.


@pytest.mark.parametrize(
    "source,target",
    [
        ("hsa", "uniprot"),  # 200
        ("hsa", "ncbi-geneid"),  # 200
        ("hsa", "ncbi-proteinid"),  # 200
        ("uniprot", "hsa"),  # 200
        ("ncbi-geneid", "hsa"),  # 200
        ("eco", "uniprot"),  # 200
        ("T01001", "uniprot"),  # 200
        ("uniprot", "T01001"),  # 200
        ("compound", "chebi"),  # 200
        ("compound", "pubchem"),  # 200
        ("cpd", "chebi"),  # 200
        ("chebi", "compound"),  # 200
        ("pubchem", "compound"),  # 200
        ("drug", "chebi"),  # 200
        ("dr", "pubchem"),  # 200
        ("glycan", "pubchem"),  # 200
        ("gl", "chebi"),  # 200
        ("chebi", "glycan"),  # 200
    ],
)
def test_validate_conv_pair_accepts_live_200_pairs(source: str, target: str) -> None:
    validated_source, validated_target = validate_conv_pair(source, target)
    assert validated_source == source
    assert validated_target == target


@pytest.mark.parametrize(
    "source,target",
    [
        ("compound", "kegg"),  # 400 — 'kegg' is not a conv database at all
        ("hsa", "kegg"),  # 400 — what the old docstring recommended
        ("kegg", "hsa"),  # 400
        ("pathway", "hsa"),  # 400 — a per-side validator would let this through
        ("compound", "ncbi-geneid"),  # 400 — cross-kind
        ("compound", "uniprot"),  # 400 — cross-kind
        ("hsa", "chebi"),  # 400 — cross-kind
        ("hsa", "pubchem"),  # 400 — cross-kind
        ("drug", "ncbi-geneid"),  # 400 — cross-kind
        ("uniprot", "ncbi-geneid"),  # 400 — both sides are outside databases
        ("chebi", "pubchem"),  # 400 — both sides are outside databases
        ("hsa", "hsa"),  # 400 — both sides are KEGG
        ("compound", "drug"),  # 400 — both sides are KEGG
        ("hsa", "nonexist"),
        ("", "uniprot"),
        ("hsa", ""),
    ],
)
def test_validate_conv_pair_rejects_live_400_pairs(source: str, target: str) -> None:
    with pytest.raises(ValueError):
        validate_conv_pair(source, target)


def test_validate_conv_pair_normalizes_case_and_t_numbers() -> None:
    assert validate_conv_pair(" t01001 ", "UniProt") == ("T01001", "uniprot")
    assert validate_conv_pair("ChEBI", "COMPOUND") == ("chebi", "compound")


def test_validate_conv_pair_treats_genes_as_a_target_only() -> None:
    """`/conv/genes/uniprot:P00533` is 200; `/conv/uniprot/genes` is 400."""
    assert validate_conv_pair("uniprot", "genes", has_entry_ids=True) == ("uniprot", "genes")
    with pytest.raises(ValueError, match="not a valid conv source"):
        validate_conv_pair("genes", "uniprot", has_entry_ids=True)


def test_validate_conv_pair_requires_entry_ids_for_a_genes_target() -> None:
    """`/conv/genes/ncbi-geneid` (whole-database form) is 400."""
    with pytest.raises(ValueError, match="requires entry_ids"):
        validate_conv_pair("ncbi-geneid", "genes")


def test_validate_conv_pair_error_names_the_valid_pairings() -> None:
    """The message is the model's only route out of a rejected call."""
    with pytest.raises(ValueError) as exc:
        validate_conv_pair("compound", "uniprot")
    message = str(exc.value)
    assert "ncbi-geneid" in message
    assert "chebi" in message


# --- validate_query ---


@pytest.mark.parametrize(
    "value",
    ["kinase", "glucose-6-phosphate"],
)
def test_validate_query_valid(value: str) -> None:
    result = validate_query(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["", "x" * 201, "test<script>"],
)
def test_validate_query_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_query(value)
