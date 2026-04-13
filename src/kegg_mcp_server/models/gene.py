from __future__ import annotations

from pydantic import BaseModel

from kegg_mcp_server.models.common import Reference


class GeneInfo(BaseModel):
    entry: str
    name: str | list[str]
    definition: str | None = None
    orthology: dict[str, str] | None = None
    organism: str | None = None
    pathway: dict[str, str] | None = None
    module: dict[str, str] | None = None
    brite: dict[str, str] | None = None
    disease: dict[str, str] | None = None
    network: dict[str, str] | None = None
    position: str | None = None
    motif: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    aaseq: str | None = None
    ntseq: str | None = None
    references: list[Reference] | None = None
