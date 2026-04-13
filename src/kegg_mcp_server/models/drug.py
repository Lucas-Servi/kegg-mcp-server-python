from __future__ import annotations

from pydantic import BaseModel

from kegg_mcp_server.models.common import Reference


class DrugInfo(BaseModel):
    entry: str
    name: str | list[str]
    formula: str | None = None
    exact_mass: float | None = None
    mol_weight: float | None = None
    remark: str | None = None
    comment: str | None = None
    cls: str | None = None
    pathway: dict[str, str] | None = None
    target: dict[str, str] | None = None
    network: dict[str, str] | None = None
    interaction: dict[str, str] | None = None
    dblinks: dict[str, list[str]] | None = None
    references: list[Reference] | None = None


class DrugInteraction(BaseModel):
    drug1: str
    drug2: str
    interaction: str


class DrugInteractionResult(BaseModel):
    drug_ids: list[str]
    interactions: list[DrugInteraction]
    count: int
