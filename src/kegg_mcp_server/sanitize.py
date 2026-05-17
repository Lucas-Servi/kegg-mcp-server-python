"""Sanitize LLM-facing text fields against prompt injection.

Part of the KEGG MCP Server by Elytron Biotech.
Applies to narrative fields returned from KEGG (definition, comment, etc.)
but NOT to structured identifiers or biological sequences.
"""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_INJECTION_BEACONS = re.compile(
    r"("
    r"system\s*:"
    r"|<\|[^|]*\|>"
    r"|<<\s*SYS"
    r"|\[INST\]"
    r"|Human:"
    r"|Assistant:"
    r"|</?instructions>"
    r")",
    re.IGNORECASE,
)

_MAX_FIELD_LEN = 8000


def sanitize_llm_text(text: str) -> str:
    """Strip control chars, fence injection beacons, and truncate long fields."""
    text = _CONTROL_CHARS.sub("", text)
    text = _INJECTION_BEACONS.sub(r"[\1]", text)
    if len(text) > _MAX_FIELD_LEN:
        text = text[:_MAX_FIELD_LEN] + " ...[truncated]"
    return text
