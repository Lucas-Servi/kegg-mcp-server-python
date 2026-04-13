from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    from kegg_mcp_server.tools import (
        brite,
        compounds,
        cross_db,
        database,
        diseases,
        drugs,
        enzymes,
        genes,
        glycans,
        modules,
        orthology,
        pathways,
        reactions,
    )

    for mod in [
        database,
        pathways,
        genes,
        compounds,
        reactions,
        enzymes,
        diseases,
        drugs,
        modules,
        orthology,
        glycans,
        brite,
        cross_db,
    ]:
        mod.register(mcp)
