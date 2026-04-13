"""Parsers for KEGG REST API response formats.

KEGG returns two main formats:
  1. Tab-delimited lists  — /list, /find, /conv, /link, /ddi
  2. Flat-file entries    — /get  (ENTRY ... /// blocks)
"""

from __future__ import annotations

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
    return {a: b for a, b in parse_link_response(text)}


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
        "BRITE",
    }
)

# Sections that are raw multi-line sequence / text blocks
_TEXT_SECTIONS = frozenset({"AASEQ", "NTSEQ", "COMMENT", "REMARK", "STRUCTURE", "SEQUENCE"})


def parse_flat_entry(text: str) -> dict[str, Any]:
    """Parse a single KEGG flat-file entry into a structured dict.

    KEGG flat-file format:
      - Field names occupy columns 0–11 (left-padded, 12 chars total)
      - Content starts at column 12
      - Continuation lines have blank field name (spaces in 0–11)
      - Entries end with "///"
    """
    result: dict[str, Any] = {}
    current_section: str | None = None
    buffer: list[str] = []

    for line in text.splitlines():
        if line.startswith("///"):
            break

        if len(line) >= 12:
            field_raw = line[:12]
            content = line[12:].strip()
        else:
            field_raw = line
            content = ""

        field_name = field_raw.strip()

        if field_name:
            if current_section is not None:
                _flush_section(result, current_section, buffer)
            current_section = field_name
            buffer = [content] if content else []
        else:
            if content:
                buffer.append(content)

    if current_section is not None:
        _flush_section(result, current_section, buffer)

    return result


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
            parts = line.split(None, 1)
            if len(parts) == 2:
                mapping[parts[0]] = parts[1]
            elif parts:
                mapping[parts[0]] = ""
        result[section.lower()] = mapping

    elif section_upper in _TEXT_SECTIONS:
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
    """Parse continuation lines under a REFERENCE section."""
    current: dict[str, str] = {}
    for line in lines:
        if "PMID:" in line:
            current["pmid"] = line.split("PMID:")[1].strip().rstrip(")")
        elif line.startswith("AUTHORS"):
            current["authors"] = line[7:].strip()
        elif line.startswith("TITLE"):
            current["title"] = line[5:].strip()
        elif line.startswith("JOURNAL"):
            current["journal"] = line[7:].strip()
        elif line.strip():
            current.setdefault("ref_id", line.strip())
    return [current] if current else []
