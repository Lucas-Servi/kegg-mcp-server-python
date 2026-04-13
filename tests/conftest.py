"""Pytest fixtures loading real KEGG response data from fixture files."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def pathway_text() -> str:
    return (FIXTURES / "pathway_entry.txt").read_text()


@pytest.fixture
def gene_text() -> str:
    return (FIXTURES / "gene_entry.txt").read_text()


@pytest.fixture
def compound_text() -> str:
    return (FIXTURES / "compound_entry.txt").read_text()


@pytest.fixture
def tab_list_text() -> str:
    return (FIXTURES / "tab_list.txt").read_text()


@pytest.fixture
def ddi_text() -> str:
    return (FIXTURES / "drug_interaction.txt").read_text()
