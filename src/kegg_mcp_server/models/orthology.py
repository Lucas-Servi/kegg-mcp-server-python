from __future__ import annotations

from pydantic import BaseModel

from kegg_mcp_server.models.common import Reference


class KOInfo(BaseModel):
    entry: str
    name: str | list[str]
    definition: str | None = None
    pathway: dict[str, str] | None = None
    module: dict[str, str] | None = None
    disease: dict[str, str] | None = None
    network: dict[str, str] | None = None
    # KEGG BRITE can be either a structured map or a free-text hierarchy block.
    brite: dict[str, str] | str | None = None
    genes: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None
