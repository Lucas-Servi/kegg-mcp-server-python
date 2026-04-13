from __future__ import annotations

from pydantic import BaseModel

from kegg_mcp_server.models.common import Reference


class PathwayInfo(BaseModel):
    entry: str
    name: str | list[str]
    cls: str | None = None
    description: str | None = None
    organism: str | None = None
    gene: dict[str, str] | None = None
    compound: dict[str, str] | None = None
    reaction: dict[str, str] | None = None
    module: dict[str, str] | None = None
    disease: dict[str, str] | None = None
    drug: dict[str, str] | None = None
    network: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None


class PathwayLinks(BaseModel):
    pathway_id: str
    linked_db: str
    pairs: list[tuple[str, str]]
    count: int
