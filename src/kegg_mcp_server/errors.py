"""KEGG client exceptions."""

from __future__ import annotations


class KEGGAPIError(Exception):
    """KEGG REST API failed in a way the caller should surface to the model.

    Distinguished from an empty/not-found result (HTTP 404 → empty string),
    which is treated as a normal empty outcome and never raised.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        path: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.path = path
        self.retryable = retryable
