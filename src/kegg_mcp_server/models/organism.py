from __future__ import annotations
from pydantic import BaseModel


class OrganismInfo(BaseModel):
    code: str
    name: str
    taxonomy: str | None = None


class DatabaseInfo(BaseModel):
    database: str
    release: str | None = None
    entries: int | None = None
    raw_info: str
