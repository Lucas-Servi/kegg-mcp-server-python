from __future__ import annotations

from pydantic import BaseModel


class ErrorResult(BaseModel):
    """Structured error returned by a tool when the KEGG API fails.

    A tool returns this instead of raising so the model can reason about
    the failure and decide whether to retry, change inputs, or give up.
    A point lookup that receives a 404 uses code ``not_found``; an empty search
    remains a successful result with no items.
    """

    error: str
    code: str = "kegg_api_error"
    retryable: bool = False
    status: int | None = None
    path: str | None = None
    hint: str | None = None
