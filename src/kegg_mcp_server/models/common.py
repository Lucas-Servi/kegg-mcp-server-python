from __future__ import annotations

from pydantic import BaseModel, Field


class Reference(BaseModel):
    pmid: str | None = None
    authors: str | None = None
    title: str | None = None
    journal: str | None = None
    ref_id: str | None = None


class SearchResult(BaseModel):
    query: str
    database: str
    total_found: int
    returned_count: int
    results: dict[str, str]
    truncated: bool = False


class EntrySummary(BaseModel):
    """Compact projection of a KEGG flat-file entry.

    Returned from `get_*_info` tools when `detail_level="summary"` (the default) to
    keep response size small. Counts replace long linked-entity lists; long text
    blocks (sequences, comments, raw content) and per-entry xref/reference dumps
    are omitted. Request `detail_level="full"` for the complete entry.
    """

    entry: str
    entry_type: str | None = None
    name: str | list[str] = ""
    cls: str | None = None
    definition: str | None = None
    description: str | None = None
    formula: str | None = None
    equation: str | None = None
    organism: str | None = None
    exact_mass: float | None = None
    mol_weight: float | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    dblinks_sample: dict[str, list[str]] = Field(default_factory=dict)
    detail_level: str = "summary"


class ListResult(BaseModel):
    database: str
    total: int
    items: dict[str, str]


class ConversionResult(BaseModel):
    source_db: str
    target_db: str
    mappings: dict[str, str]
    count: int


class LinkResult(BaseModel):
    source: str
    target_db: str
    pairs: list[tuple[str, str]]
    count: int


class BatchLookupResult(BaseModel):
    requested: list[str]
    found: int
    entries: list[dict]
