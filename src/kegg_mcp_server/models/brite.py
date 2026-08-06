from __future__ import annotations

from pydantic import BaseModel, Field


class BriteInfo(BaseModel):
    entry: str
    name: str | list[str]
    definition: str | None = None
    dblinks: dict[str, list[str]] | None = None
    raw_content: str | None = None


class BriteHierarchy(BaseModel):
    """Bounded projection of a KEGG BRITE ``A``/``B``/``C``/… tree.

    BRITE entries are hierarchies, not flat-file entries: ``/get/br:ko00001`` is
    4.3 MB / 65,337 lines and ``/get/br:hsa00001`` is 6.8 MB. Returning the raw
    text would overflow the context window of the model this feeds, so the
    default projection keeps the navigational skeleton (per-level line counts +
    the top two levels' labels) and drops the leaves. ``raw_content`` is
    populated only for ``detail_level="full"``, and is itself capped.
    """

    entry: str
    #: Deepest level letter declared by the ``+<letter>`` header (``D`` for ko00001).
    deepest_level: str | None = None
    #: Leaf column names from the header (``["KO"]``, ``["GENES", "KO"]``).
    columns: list[str] = Field(default_factory=list)
    #: Lines per level letter, e.g. ``{"A": 8, "B": 57, "C": 571, "D": 64695}``.
    level_counts: dict[str, int] = Field(default_factory=dict)
    total_lines: int = 0
    #: Labels for the top levels only (see ``parsers.BRITE_LABEL_MAX_DEPTH``).
    labels: dict[str, list[str]] = Field(default_factory=dict)
    #: Levels whose label list hit the per-level cap.
    labels_truncated: list[str] = Field(default_factory=list)
    last_updated: str | None = None
    detail_level: str = "summary"
    #: Only set for ``detail_level="full"``, and truncated to a token-safe size.
    raw_content: str | None = None
    #: True when ``raw_content`` was cut to fit the cap.
    raw_truncated: bool = False
