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
#: Accepts every id shape KEGG itself hands out: the canonical `br:br08303` /
#: `br:ko00001`, the unprefixed `br08303` / `ko00001` emitted by `/list/brite`,
#: and the bare `08303` / `00001` emitted by `/find/brite/<query>`.
#: `normalize_brite_id` is what turns any of them into a URL that works.
BRITE_ID = re.compile(r"^(br:)?((br|ko|[a-z]{3,4})?)\d{5}$")
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

#: Outside databases KEGG's ``conv`` operation maps *gene/protein* entries to and from.
CONV_GENE_OUTSIDE_DATABASES = frozenset({"ncbi-geneid", "ncbi-proteinid", "uniprot"})

#: Outside databases KEGG's ``conv`` operation maps *chemical* entries to and from.
CONV_CHEMICAL_OUTSIDE_DATABASES = frozenset({"pubchem", "chebi"})

#: KEGG-side chemical databases, with the short entry prefixes KEGG also accepts
#: (``/conv/chebi/cpd:C00002`` and ``/conv/chebi/compound:C00002`` are both 200).
CONV_CHEMICAL_KEGG_DATABASES = frozenset({"compound", "cpd", "drug", "dr", "glycan", "gl"})

_CONV_PAIRINGS_HINT = (
    "conv maps a KEGG database to an outside one of the same kind: "
    "genes (an organism code like 'hsa'/'eco', or a T-number) <-> "
    "ncbi-geneid/ncbi-proteinid/uniprot; chemical entries "
    "(compound/drug/glycan) <-> pubchem/chebi."
)

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


#: The two BRITE hierarchy families. `/list/brite` is 97 `br#####` + 59 `ko#####`,
#: and the 156 ids have 156 distinct digit suffixes — so a bare `08303` resolves
#: to exactly one family, we just cannot tell WHICH one without asking KEGG.
_BRITE_FAMILIES = ("br", "ko")


def brite_get_candidates(brite_id: str) -> list[str]:
    """Return the `/get` ids to try for a validated BRITE id, best first.

    **`/get` requires the `br:` prefix on every BRITE id** — `/get/br08303` and
    `/get/ko00001` are both 404, only `/get/br:br08303` and `/get/br:ko00001` are
    200 (probed live). That matters because neither of the two ids KEGG *hands the
    caller* carries it: `/list/brite` emits `br08901` and `/find/brite/<query>`
    strips the family prefix entirely, emitting `08303` for `br08303` and `00001`
    for `ko00001`. So the ids produced by `search_brite` used to 404 as
    "not_found" — a real entry reported as nonexistent.

    A bare digit id is unambiguous but not locally decidable, so both families are
    returned in order. A 404 costs one cached empty response, so trying the second
    is cheap.
    """
    value = brite_id.strip()
    if value.startswith("br:"):
        return [value]
    for family in _BRITE_FAMILIES:
        if value.startswith(family):
            return [f"br:{value}"]
    return [f"br:{family}{value}" for family in _BRITE_FAMILIES]


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


def _classify_conv_database(db: str) -> tuple[str, str]:
    """Return ``(normalized_name, kind)`` for one side of a ``conv`` pair.

    ``kind`` is ``gene_kegg`` / ``gene_outside`` / ``chem_kegg`` / ``chem_outside``.
    Raises ``ValueError`` for names ``conv`` does not accept at all.

    Order matters: ``kegg``, ``compound``, ``drug`` and ``genes`` are all 3-4
    lowercase letters, so they match ``KEGG_DATABASE_IDENTIFIER`` and would be
    misread as organism codes if the named sets were not checked first.
    """
    value = db.strip()
    if not value:
        raise ValueError("Database name must not be empty")
    normalized = value.lower()
    if normalized in CONV_GENE_OUTSIDE_DATABASES:
        return normalized, "gene_outside"
    if normalized in CONV_CHEMICAL_OUTSIDE_DATABASES:
        return normalized, "chem_outside"
    if normalized in CONV_CHEMICAL_KEGG_DATABASES:
        return normalized, "chem_kegg"
    if normalized == "genes":
        return normalized, "gene_kegg"
    if normalized in _RESERVED_DATABASE_NAMES:
        raise ValueError(
            f"Database {db!r} is not supported by the KEGG conv operation. "
            f"{_CONV_PAIRINGS_HINT}"
        )
    dynamic = value.upper() if re.fullmatch(r"t\d{5}", value, re.IGNORECASE) else normalized
    if KEGG_DATABASE_IDENTIFIER.fullmatch(dynamic):
        return dynamic, "gene_kegg"
    raise ValueError(f"Unknown KEGG database for conv: {db!r}. {_CONV_PAIRINGS_HINT}")


def validate_conv_pair(
    source_db: str, target_db: str, *, has_entry_ids: bool = False
) -> tuple[str, str]:
    """Validate a ``conv`` source/target **pair** and return both normalized.

    The pair is the unit of validation, not each side: every name below is a
    legitimate conv database, yet ``pathway``/``ncbi-geneid``,
    ``compound``/``ncbi-geneid`` and ``hsa``/``chebi`` are all HTTP 400. KEGG
    only converts within one kind, KEGG side <-> outside side:

    * genes — an organism code (``hsa``) or T-number (``T01001``) <->
      ``ncbi-geneid`` / ``ncbi-proteinid`` / ``uniprot``
    * chemistry — ``compound`` / ``drug`` / ``glycan`` (or their ``cpd`` /
      ``dr`` / ``gl`` prefixes) <-> ``pubchem`` / ``chebi``

    Two asymmetries are verified against the live API and encoded here:

    * ``genes`` is a valid **target** only, and only with ``entry_ids``:
      ``/conv/genes/uniprot:P00533`` is 200 (it resolves the organism for you)
      while ``/conv/genes/ncbi-geneid`` and ``/conv/uniprot/genes`` are 400.
    * a 200 does not imply a meaningful pair — ``/conv/pathway/ncbi-geneid:1956``
      returns 200 with an empty body while ``/conv/pathway/hsa`` is 400, so
      per-entry probing cannot be used to discover the vocabulary.
    """
    source, source_kind = _classify_conv_database(source_db)
    target, target_kind = _classify_conv_database(target_db)

    source_family, source_side = source_kind.split("_")
    target_family, target_side = target_kind.split("_")
    if source_family != target_family or source_side == target_side:
        raise ValueError(
            f"KEGG cannot convert {source_db!r} to {target_db!r}. {_CONV_PAIRINGS_HINT}"
        )

    if source == "genes":
        raise ValueError(
            "'genes' is not a valid conv source — use the organism code (e.g. 'hsa') "
            "or its T-number (e.g. 'T01001')"
        )
    if target == "genes" and not has_entry_ids:
        raise ValueError(
            "Converting to 'genes' requires entry_ids (KEGG rejects the whole-database "
            "form); pass e.g. entry_ids=['P00533'] with source_db='uniprot'"
        )
    return source, target


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
