from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    from kegg_mcp_server.tools import (
        ascii_pathway,
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
        ascii_pathway,
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
    ]:
        mod.register(mcp)
