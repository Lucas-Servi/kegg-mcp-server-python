"""Parsers for KEGG REST API response formats.

KEGG returns two main formats:
  1. Tab-delimited lists  — /list, /find, /conv, /link, /ddi
  2. Flat-file entries    — /get  (ENTRY ... /// blocks)
"""

from __future__ import annotations

import re
from typing import Any

# ------------------------------------------------------------------
# Tab-delimited parsers
# ------------------------------------------------------------------


def parse_tab_list(text: str) -> dict[str, str]:
    """Parse a KEGG tab-delimited list into {id: description}.

    Used by /list and /find responses.
    """
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
        elif len(parts) == 1 and parts[0].strip():
            result[parts[0].strip()] = ""
    return result


def parse_link_response(text: str) -> list[tuple[str, str]]:
    """Parse /link response into [(source, target)] pairs."""
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs


def parse_conv_response(text: str) -> dict[str, str]:
    """Parse /conv response into {source_id: target_id}."""
    return dict(parse_link_response(text))


def parse_ddi_response(text: str) -> list[dict[str, str]]:
    """Parse /ddi drug-drug interaction response.

    Each line: drug1\\tdrug2\\tinteraction_type
    """
    interactions: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            interactions.append(
                {
                    "drug1": parts[0].strip(),
                    "drug2": parts[1].strip(),
                    "interaction": parts[2].strip(),
                }
            )
        elif len(parts) == 2:
            interactions.append(
                {
                    "drug1": parts[0].strip(),
                    "drug2": parts[1].strip(),
                    "interaction": "",
                }
            )
    return interactions


# ------------------------------------------------------------------
# KEGG flat-file parser
# ------------------------------------------------------------------

# Sections where each line is "ID  description" → stored as dict[str, str]
_MAP_SECTIONS = frozenset(
    {
        "PATHWAY",
        "MODULE",
        "DISEASE",
        "DRUG",
        "GENE",
        "COMPOUND",
        "REACTION",
        "ENZYME",
        "ORTHOLOGY",
        "MOTIF",
        "NETWORK",
        "VARIANT",
        "TARGET",
    }
)

# Sections that are raw multi-line text blocks, joined with newlines
_TEXT_SECTIONS = frozenset(
    {"AASEQ", "NTSEQ", "COMMENT", "REMARK", "STRUCTURE", "SEQUENCE", "BRITE"}
)

# Pattern matching KEGG-style identifiers: C00002, R00756, K01234, D00001, G00001,
# M00001, H00004, or EC-style numbers like 1.1.1.1
_KEGG_ID_RE = re.compile(r"^[A-Za-z]\d{4,}$|^\d+\.\d+\.\d+\.\d+$")


def parse_flat_entry(text: str) -> dict[str, Any]:
    """Parse a single KEGG flat-file entry into a structured dict.

    KEGG flat-file format:
      - Top-level field names start at column 0 (no leading space)
      - Content starts at column 12
      - Continuation lines have spaces in columns 0–11
      - Sub-section fields (e.g. AUTHORS under REFERENCE) start with spaces
        in columns 0–11 but have a non-empty field label
      - Entries end with "///"
    """
    result: dict[str, Any] = {}
    current_section: str | None = None
    buffer: list[str] = []

    for line in text.splitlines():
        if line.startswith("///"):
            break

        if not line.strip():
            continue

        # A new top-level section starts at column 0 (no leading whitespace).
        # Sub-sections (e.g. "  AUTHORS   ...") have leading spaces and are
        # treated as continuation lines belonging to the current section.
        is_new_section = len(line) > 0 and not line[0].isspace()

        if is_new_section:
            # Extract field name and content
            if len(line) >= 12:
                field_name = line[:12].strip()
                content = line[12:].strip()
            else:
                field_name = line.strip()
                content = ""

            # Flush previous section
            if current_section is not None:
                _flush_section(result, current_section, buffer)

            current_section = field_name
            buffer = [content] if content else []
        else:
            # Continuation or sub-section line — include sub-field labels
            # (e.g. "  AUTHORS   Smith J" becomes "AUTHORS   Smith J")
            line_content = line.lstrip()
            if line_content:
                buffer.append(line_content)

    # Flush final section
    if current_section is not None:
        _flush_section(result, current_section, buffer)

    return result


_SUMMARY_SCALAR_FIELDS = (
    "entry",
    "entry_type",
    "name",
    "cls",
    "definition",
    "description",
    "formula",
    "equation",
    "organism",
    "exact_mass",
    "mol_weight",
)

# Linked-entity sections whose length is useful as a count in a summary
_SUMMARY_COUNT_FIELDS = (
    "gene",
    "compound",
    "reaction",
    "enzyme",
    "pathway",
    "module",
    "disease",
    "drug",
    "orthology",
    "network",
    "target",
    "motif",
    "brite",
    "variant",
)

# Number of DB xrefs to surface in a summary (keep size bounded)
_SUMMARY_DBLINKS_LIMIT = 5


def summarize_flat_entry(parsed: dict[str, Any]) -> dict[str, Any]:
    """Project a `parse_flat_entry` result down to a compact summary.

    Keeps scalar header fields (entry, name, class, definition, …) and replaces
    long linked-entity dicts (genes, compounds, reactions, …) with counts. A
    small sample of DB xrefs is retained; references, sequences, and long text
    blocks are omitted. Mirrors `EntrySummary` in models/common.py.
    """
    out: dict[str, Any] = {}
    for field in _SUMMARY_SCALAR_FIELDS:
        if field in parsed:
            out[field] = parsed[field]

    counts: dict[str, int] = {}
    for field in _SUMMARY_COUNT_FIELDS:
        value = parsed.get(field)
        if isinstance(value, dict) and value:
            counts[field] = len(value)
        elif isinstance(value, list) and value:
            counts[field] = len(value)
    if counts:
        out["counts"] = counts

    dblinks = parsed.get("dblinks")
    if isinstance(dblinks, dict) and dblinks:
        sampled = dict(list(dblinks.items())[:_SUMMARY_DBLINKS_LIMIT])
        out["dblinks_sample"] = sampled

    return out


def parse_multi_flat(text: str) -> list[dict[str, Any]]:
    """Parse a KEGG response containing multiple flat-file entries (separated by ///)."""
    entries: list[dict[str, Any]] = []
    current: list[str] = []
    for line in text.splitlines():
        current.append(line)
        if line.startswith("///"):
            parsed = parse_flat_entry("\n".join(current))
            if parsed:
                entries.append(parsed)
            current = []
    if current:
        parsed = parse_flat_entry("\n".join(current))
        if parsed:
            entries.append(parsed)
    return entries


def _is_kegg_id(token: str) -> bool:
    """Check if a token looks like a KEGG identifier."""
    return bool(_KEGG_ID_RE.match(token))


def _flush_section(result: dict[str, Any], section: str, lines: list[str]) -> None:
    if not lines:
        return

    section_upper = section.upper()

    if section_upper == "ENTRY":
        parts = lines[0].split()
        result["entry"] = parts[0] if parts else ""
        result["entry_type"] = parts[1] if len(parts) > 1 else ""

    elif section_upper == "NAME":
        full = " ".join(lines)
        names = [n.strip().rstrip(";") for n in full.split(";") if n.strip()]
        result["name"] = names if len(names) > 1 else (names[0] if names else "")

    elif section_upper == "DBLINKS":
        dblinks: dict[str, list[str]] = {}
        for line in lines:
            if ":" in line:
                db, ids_str = line.split(":", 1)
                dblinks[db.strip()] = ids_str.strip().split()
        result["dblinks"] = dblinks

    elif section_upper == "REFERENCE":
        refs = _parse_references(lines)
        result.setdefault("references", []).extend(refs)

    elif section_upper in _MAP_SECTIONS:
        mapping: dict[str, str] = {}
        for line in lines:
            # Detect flat ID lists (e.g. "R00002 R00076 R00085 R00086" in compound
            # REACTION sections, or "1.1.1.37 1.1.1.40" in compound ENZYME sections).
            # If ALL tokens on the line look like KEGG IDs, store each as a separate key.
            all_tokens = line.split()
            if len(all_tokens) > 1 and all(_is_kegg_id(t) for t in all_tokens):
                for token in all_tokens:
                    mapping[token] = ""
            else:
                parts = line.split(None, 1)
                if len(parts) == 2:
                    mapping[parts[0]] = parts[1]
                elif parts:
                    mapping[parts[0]] = ""
        result[section.lower()] = mapping

    elif section_upper in _TEXT_SECTIONS:
        # For sequence sections, skip the numeric length line (first line)
        if section_upper in ("AASEQ", "NTSEQ") and lines and lines[0].strip().isdigit():
            result[section.lower()] = "\n".join(lines[1:]) if len(lines) > 1 else ""
        else:
            result[section.lower()] = "\n".join(lines)

    elif section_upper in ("EXACT_MASS", "MOL_WEIGHT"):
        try:
            result[section.lower()] = float(lines[0])
        except ValueError:
            result[section.lower()] = lines[0]

    elif section_upper == "FORMULA":
        result["formula"] = lines[0] if lines else ""

    elif section_upper == "CLASS":
        result["cls"] = " ".join(lines)

    elif section_upper == "SYSNAME":
        result["sysname"] = " ".join(lines)

    elif section_upper == "EQUATION":
        result["equation"] = " ".join(lines)

    elif section_upper == "DEFINITION":
        result["definition"] = " ".join(lines)

    elif section_upper == "DESCRIPTION":
        result["description"] = " ".join(lines)

    elif section_upper == "ORGANISM":
        result["organism"] = " ".join(lines)

    elif section_upper == "POSITION":
        result["position"] = " ".join(lines)

    else:
        result[section.lower()] = " ".join(lines)


def _parse_references(lines: list[str]) -> list[dict[str, str]]:
    """Parse lines within a REFERENCE section.

    Lines may include sub-field labels (AUTHORS, TITLE, JOURNAL) from the
    sub-section parsing, plus optional PMID identifiers.
    """
    refs: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in lines:
        if "PMID:" in line:
            current["pmid"] = line.split("PMID:")[1].strip().rstrip(")")
        elif line.startswith("AUTHORS"):
            current["authors"] = line[len("AUTHORS") :].strip()
        elif line.startswith("TITLE"):
            current["title"] = line[len("TITLE") :].strip()
        elif line.startswith("JOURNAL"):
            current["journal"] = line[len("JOURNAL") :].strip()
        elif line.strip():
            current.setdefault("ref_id", line.strip())

    if current:
        refs.append(current)
    return refs
