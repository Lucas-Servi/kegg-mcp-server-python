"""Pydantic model for ASCII pathway rendering results.

Part of the KEGG MCP Server by Elytron Biotech.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AsciiPathway(BaseModel):
    """Result of rendering a KEGG pathway as ASCII art."""

    pathway_id: str
    title: str
    organism: str | None = None
    style: Literal["chain", "grid"]
    ascii: str
    legend: list[dict[str, str]] = []
    node_count: int
    reaction_count: int
    relation_count: int = 0
    truncated: bool = False
