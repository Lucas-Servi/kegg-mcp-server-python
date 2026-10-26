"""Pydantic models for drawn pathway maps.

Part of the KEGG MCP Server by Elytron Biotech.
"""

from __future__ import annotations

from pydantic import BaseModel


class MapGroup(BaseModel):
    """One highlight group (e.g. one genome) and what it matched on the map."""

    label: str
    color: str
    ids_given: int
    """Distinct KO and EC ids the caller supplied for this group."""
    kos_on_map: list[str] = []
    """Map KOs this group has, matched directly or through an EC number."""
    matched_by_ec: list[str] = []
    """The subset of ``kos_on_map`` matched only through an EC number."""
    ec_matches: dict[str, list[str]] = {}
    """For each ``matched_by_ec`` KO, the EC numbers KEGG links to it, all of which one
    item (gene) of the group carries."""
    boxes_colored: int = 0
    steps_covered: int = 0


class MapStep(BaseModel):
    """One reaction step (substrates → products). Its boxes are ALTERNATIVE enzymes for the
    same conversion across all organisms: one coloured box covers the step."""

    step: str
    reactions: list[str] = []
    boxes: list[str]
    present_in: list[str] = []


class MapBox(BaseModel):
    """One gene/ortholog box of the map."""

    entry_id: int
    label: str
    kos: list[str]
    present_in: list[str] = []
    """Group labels that have at least one of this box's KOs."""


class PathwayMapSummary(BaseModel):
    """What a drawn map shows, exactly, so a caller can check it without seeing the image."""

    pathway_id: str
    title: str
    url: str
    image_width: int
    image_height: int
    groups: list[MapGroup] = []
    box_count: int
    boxes_with_any_group: int = 0
    boxes: list[MapBox] = []
    boxes_truncated: bool = False
    step_count: int = 0
    steps_with_any_group: int = 0
    steps: list[MapStep] = []
    steps_truncated: bool = False
    map_ko_count: int
    unrecognized_ids: list[str] = []
    notes: list[str] = []
