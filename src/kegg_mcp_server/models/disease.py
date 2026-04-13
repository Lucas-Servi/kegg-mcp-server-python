from __future__ import annotations

from pydantic import BaseModel

from kegg_mcp_server.models.common import Reference


class DiseaseInfo(BaseModel):
    entry: str
    name: str | list[str]
    description: str | None = None
    category: str | None = None
    gene: dict[str, str] | None = None
    pathway: dict[str, str] | None = None
    module: dict[str, str] | None = None
    network: dict[str, str] | None = None
    drug: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None
