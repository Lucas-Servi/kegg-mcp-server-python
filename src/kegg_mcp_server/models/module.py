from __future__ import annotations

from pydantic import BaseModel

from kegg_mcp_server.models.common import Reference


class ModuleInfo(BaseModel):
    entry: str
    name: str | list[str]
    definition: str | None = None
    cls: str | None = None
    pathway: dict[str, str] | None = None
    reaction: dict[str, str] | None = None
    compound: dict[str, str] | None = None
    enzyme: dict[str, str] | None = None
    orthology: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None
