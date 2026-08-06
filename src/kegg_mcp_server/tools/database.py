from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import ListResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.organism import DatabaseInfo
from kegg_mcp_server.tools._common import MAX_ENTRIES_CAP, READ_ONLY, kegg_tool
from kegg_mcp_server.validators import validate_info_database

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_database_info(
        database: str = "kegg", ctx: Context = None
    ) -> DatabaseInfo | ErrorResult:
        """Get release information and statistics for a KEGG database.

        Args:
            database: Database name (e.g. 'kegg', 'pathway', 'compound', 'drug', 'genome').
        """
        database = validate_info_database(database)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.info(database)
        release = None
        entries = None
        for line in raw.splitlines():
            if "Release" in line:
                release = line.strip()
            if "entries" in line.lower():
                for p in line.strip().split():
                    if p.replace(",", "").isdigit():
                        try:
                            entries = int(p.replace(",", ""))
                        except ValueError:
                            pass
        return DatabaseInfo(database=database, release=release, entries=entries, raw_info=raw)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def list_organisms(
        query: str = "", max_results: int = 100, ctx: Context = None
    ) -> ListResult | ErrorResult:
        """List organisms available in KEGG with their 3-4 letter codes and names.

        KEGG has ~12,000 organisms, so the full list is large. Pass `query` to
        filter by organism code or name (e.g. 'Bacillus', 'hsa') instead of
        paging through everything.

        Args:
            query: Case-insensitive substring filter on the organism code or name.
                   Empty (the default) returns the first `max_results` organisms.
            max_results: Maximum number of organisms to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        # /list/organism was retired and now returns HTTP 400; /list/genome is
        # the live endpoint. Its rows are 2-column: "T01001\thsa; Homo sapiens
        # (human)" — so the org code must be split off the description on "; ".
        raw = await kegg.list("genome")
        organisms: dict[str, str] = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                # Tolerated legacy/other shape: T-number, code, name.
                code, name = parts[1].strip(), parts[2].strip()
            elif len(parts) == 2:
                code, _, name = parts[1].partition("; ")
                code, name = code.strip(), name.strip()
                # A row with no "; " carries no separate name; keep the raw value.
                if not name:
                    name = code
            else:
                continue
            if not code:
                continue
            organisms[code] = name

        if query:
            needle = query.strip().lower()
            organisms = {
                code: name
                for code, name in organisms.items()
                if needle in code.lower() or needle in name.lower()
            }

        total = len(organisms)
        bounded = max(1, min(max_results, MAX_ENTRIES_CAP))
        limited = dict(list(organisms.items())[:bounded])
        return ListResult(
            database="organism",
            total=total,
            items=limited,
            truncated=total > len(limited),
        )
