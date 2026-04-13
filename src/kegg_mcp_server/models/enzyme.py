from __future__ import annotations
from pydantic import BaseModel
from kegg_mcp_server.models.common import Reference


class EnzymeInfo(BaseModel):
    entry: str
    name: str | list[str]
    cls: str | None = None
    sysname: str | None = None
    reaction: dict[str, str] | None = None
    substrate: str | None = None
    product: str | None = None
    comment: str | None = None
    pathway: dict[str, str] | None = None
    orthology: dict[str, str] | None = None
    genes: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None
