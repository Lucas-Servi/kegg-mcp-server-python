"""Unit tests for KEGG identifier validators."""

from __future__ import annotations

import pytest

from kegg_mcp_server.validators import (
    validate_brite_id,
    validate_compound_id,
    validate_database,
    validate_disease_id,
    validate_drug_id,
    validate_enzyme_id,
    validate_gene_id,
    validate_glycan_id,
    validate_ko_id,
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


# --- validate_database ---


@pytest.mark.parametrize(
    "value",
    ["pathway", "compound", "kegg"],
)
def test_validate_database_valid(value: str) -> None:
    result = validate_database(value)
    assert result == value


@pytest.mark.parametrize(
    "value",
    ["nonexist", ""],
)
def test_validate_database_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_database(value)


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
