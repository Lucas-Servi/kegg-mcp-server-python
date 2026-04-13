from __future__ import annotations
from pydantic import BaseModel


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
