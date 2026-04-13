from __future__ import annotations
from pydantic import BaseModel
from kegg_mcp_server.models.common import Reference


class GlycanInfo(BaseModel):
    entry: str
    name: str | list[str]
    composition: str | None = None
    mass: float | None = None
    remark: str | None = None
    reaction: dict[str, str] | None = None
    pathway: dict[str, str] | None = None
    enzyme: dict[str, str] | None = None
    orthology: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None
