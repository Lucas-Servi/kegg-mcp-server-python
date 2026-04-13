from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import ListResult
from kegg_mcp_server.models.organism import DatabaseInfo
from kegg_mcp_server.parsers import parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_database_info(database: str = "kegg", ctx: Context = None) -> DatabaseInfo:
        """Get release information and statistics for a KEGG database.

        Args:
            database: Database name (e.g. 'kegg', 'pathway', 'compound', 'drug', 'genome').
        """
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

    @mcp.tool()
    async def list_organisms(ctx: Context = None) -> ListResult:
        """List all organisms available in KEGG with their codes and names."""
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.list("organism")
        organisms: dict[str, str] = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                organisms[parts[1].strip()] = parts[2].strip()
            elif len(parts) == 2:
                organisms[parts[0].strip()] = parts[1].strip()
        return ListResult(database="organism", total=len(organisms), items=organisms)
