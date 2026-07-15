"""Input validation for KEGG identifiers and search queries."""

from __future__ import annotations

import re

ORGANISM_CODE = re.compile(r"^[a-z]{3,4}$")
PATHWAY_ID = re.compile(r"^(path:)?([a-z]{2,4}|map)\d{5}$")
GENE_ID = re.compile(r"^[a-z]{3,4}:[\w.\-]+$")
COMPOUND_ID = re.compile(r"^(cpd:)?C\d{5}$")
REACTION_ID = re.compile(r"^(rn:)?R\d{5}$")
ENZYME_ID = re.compile(r"^(ec:)?\d+\.\d+\.\d+\.\d+$")
KO_ID = re.compile(r"^(ko:)?K\d{5}$")
DISEASE_ID = re.compile(r"^(ds:)?H\d{5}$")
DRUG_ID = re.compile(r"^(dr:)?D\d{5}$")
MODULE_ID = re.compile(r"^(md:)?M\d{5}$")
GLYCAN_ID = re.compile(r"^(gl:)?G\d{5}$")
BRITE_ID = re.compile(r"^(br:)?(br|ko|[a-z]{3,4})\d{5}$")
KEGG_DATABASE_IDENTIFIER = re.compile(r"^(?:[a-z]{3,4}|T\d{5})$")

INFO_DATABASES = frozenset(
    {
        "kegg",
        "pathway",
        "brite",
        "module",
        "ko",
        "genes",
        "ag",
        "vg",
        "vp",
        "genome",
        "vtax",
        "vgenome",
        "compound",
        "glycan",
        "reaction",
        "rclass",
        "rmodule",
        "enzyme",
        "network",
        "ntmap",
        "variant",
        "disease",
        "drug",
        "dgroup",
    }
)

LINK_DATABASES = frozenset(
    {
        "pathway",
        "brite",
        "module",
        "ko",
        "genes",
        "ag",
        "vg",
        "vp",
        "genome",
        "vtax",
        "vgenome",
        "compound",
        "glycan",
        "reaction",
        "rclass",
        "rmodule",
        "enzyme",
        "network",
        "ntmap",
        "variant",
        "disease",
        "drug",
        "dgroup",
        "pubmed",
        "taxonomy",
        "atc",
        "jtc",
        "ndc",
        "yk",
    }
)

_RESERVED_DATABASE_NAMES = INFO_DATABASES | LINK_DATABASES | {"organism", "ligand"}

_QUERY_MAX_LEN = 200
_QUERY_ILLEGAL = re.compile(r"[\x00-\x1f\x7f<>{}|\\^`]")


def validate_identifier(value: str, pattern: re.Pattern[str], name: str) -> str:
    """Validate and return stripped value, or raise ValueError."""
    value = value.strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    if not pattern.match(value):
        raise ValueError(
            f"Invalid {name}: {value!r} — expected format: {pattern.pattern}"
        )
    return value


def validate_pathway_id(pathway_id: str) -> str:
    return validate_identifier(pathway_id, PATHWAY_ID, "pathway ID")


def validate_gene_id(gene_id: str) -> str:
    return validate_identifier(gene_id, GENE_ID, "gene ID")


def validate_compound_id(compound_id: str) -> str:
    return validate_identifier(compound_id, COMPOUND_ID, "compound ID")


def validate_reaction_id(reaction_id: str) -> str:
    return validate_identifier(reaction_id, REACTION_ID, "reaction ID")


def validate_enzyme_id(enzyme_id: str) -> str:
    return validate_identifier(enzyme_id, ENZYME_ID, "enzyme ID")


def validate_ko_id(ko_id: str) -> str:
    return validate_identifier(ko_id, KO_ID, "KO ID")


def validate_disease_id(disease_id: str) -> str:
    return validate_identifier(disease_id, DISEASE_ID, "disease ID")


def validate_drug_id(drug_id: str) -> str:
    return validate_identifier(drug_id, DRUG_ID, "drug ID")


def validate_module_id(module_id: str) -> str:
    return validate_identifier(module_id, MODULE_ID, "module ID")


def validate_glycan_id(glycan_id: str) -> str:
    return validate_identifier(glycan_id, GLYCAN_ID, "glycan ID")


def validate_brite_id(brite_id: str) -> str:
    return validate_identifier(brite_id, BRITE_ID, "BRITE ID")


def validate_organism_code(code: str) -> str:
    """Validate organism code. Also accepts 'map' as a special token."""
    code = code.strip().lower()
    if not code:
        raise ValueError("Organism code must not be empty")
    if code == "map":
        return code
    if not ORGANISM_CODE.match(code):
        raise ValueError(
            f"Invalid organism code: {code!r} — expected 3-4 lowercase letters"
        )
    return code


def _validate_operation_database(db: str, allowed: frozenset[str], operation: str) -> str:
    value = db.strip()
    if not value:
        raise ValueError("Database name must not be empty")
    normalized = value.lower()
    if normalized in allowed:
        return normalized
    if normalized in _RESERVED_DATABASE_NAMES:
        raise ValueError(f"Database {db!r} is not supported by the KEGG {operation} operation")
    dynamic = value.upper() if re.fullmatch(r"t\d{5}", value, re.IGNORECASE) else normalized
    if KEGG_DATABASE_IDENTIFIER.fullmatch(dynamic):
        return dynamic
    raise ValueError(f"Unknown KEGG database for {operation}: {db!r}")


def validate_info_database(db: str) -> str:
    """Validate a database accepted by KEGG's info operation."""
    return _validate_operation_database(db, INFO_DATABASES, "info")


def validate_link_database(db: str) -> str:
    """Validate a target database accepted by KEGG's link operation."""
    return _validate_operation_database(db, LINK_DATABASES, "link")


def validate_query(query: str, *, max_len: int = _QUERY_MAX_LEN) -> str:
    """Validate a free-text search query."""
    query = query.strip()
    if not query:
        raise ValueError("Search query must not be empty")
    if len(query) > max_len:
        raise ValueError(f"Query too long ({len(query)} chars, max {max_len})")
    if _QUERY_ILLEGAL.search(query):
        raise ValueError("Query contains illegal characters")
    return query
