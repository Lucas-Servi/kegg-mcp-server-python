from __future__ import annotations
from pydantic import BaseModel
from kegg_mcp_server.models.common import Reference


class CompoundInfo(BaseModel):
    entry: str
    name: str | list[str]
    formula: str | None = None
    exact_mass: float | None = None
    mol_weight: float | None = None
    remark: str | None = None
    comment: str | None = None
    reaction: dict[str, str] | None = None
    pathway: dict[str, str] | None = None
    module: dict[str, str] | None = None
    enzyme: dict[str, str] | None = None
    network: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None
