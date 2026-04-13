from __future__ import annotations
from pydantic import BaseModel


class BriteInfo(BaseModel):
    entry: str
    name: str | list[str]
    definition: str | None = None
    dblinks: dict[str, list[str]] | None = None
    raw_content: str | None = None
