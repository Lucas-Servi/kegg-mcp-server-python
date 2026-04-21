from __future__ import annotations

from pydantic import BaseModel


class ErrorResult(BaseModel):
    """Structured error returned by a tool when the KEGG API fails.

    A tool returns this instead of raising so the model can reason about
    the failure and decide whether to retry, change inputs, or give up.
    A 404 (entry not found / empty search) is NOT an error — tools return
    their usual empty result shape in that case.
    """

    error: str
    code: str = "kegg_api_error"
    retryable: bool = False
    status: int | None = None
    path: str | None = None
    hint: str | None = None
