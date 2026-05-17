"""MCP tool for rendering KEGG pathways as ASCII art.

Part of the KEGG MCP Server by Elytron Biotech.
Provides LLM-friendly text visualization of metabolic and signaling pathways.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.ascii.chain import render_chain
from kegg_mcp_server.ascii.grid import render_grid
from kegg_mcp_server.ascii.kgml import parse_kgml
from kegg_mcp_server.models.ascii import AsciiPathway
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.tools._common import READ_ONLY, kegg_tool
from kegg_mcp_server.validators import validate_pathway_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def render_pathway_ascii(
        pathway_id: str,
        style: Literal["chain", "grid"] = "chain",
        max_width: int = 100,
        max_height: int = 40,
        ctx: Context = None,
    ) -> AsciiPathway | ErrorResult:
        """Render a KEGG pathway as ASCII text optimized for LLM consumption.

        Two styles available:
        - 'chain': Linear reaction flow text showing substrate->enzyme->product chains.
          Robust and compact. Best for understanding reaction sequences.
        - 'grid': 2D spatial layout using KGML coordinates. Shows the pathway topology
          with box-and-arrow rendering. Best for seeing spatial relationships.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010' for human glycolysis).
                Must be organism-specific; reference pathways (map*) have limited KGML.
            style: 'chain' (default, linear text) or 'grid' (2D spatial layout).
            max_width: Maximum line width in characters (40-200, default 100).
            max_height: Grid mode only: maximum height in lines (20-80, default 40).
        """
        pathway_id = validate_pathway_id(pathway_id)
        max_width = max(40, min(max_width, 200))
        max_height = max(20, min(max_height, 80))

        kegg = ctx.request_context.lifespan_context.kegg
        kgml_xml = await kegg.get(pathway_id, option="kgml")

        if not kgml_xml.strip():
            return ErrorResult(
                error=f"No KGML data available for pathway {pathway_id}",
                code="kgml_not_available",
                retryable=False,
                hint=(
                    "KGML is only available for organism-specific pathways "
                    "(e.g. 'hsa00010', not 'map00010'). Try prefixing with an "
                    "organism code like 'hsa', 'eco', or 'mmu'."
                ),
            )

        pathway = parse_kgml(kgml_xml)

        legend: list[dict[str, str]] = []

        if style == "grid":
            ascii_art = render_grid(pathway, width=max_width, height=max_height)
        else:
            ascii_art = render_chain(pathway, max_width=max_width)

        # Build legend from nodes
        for node in list(pathway.nodes.values())[:50]:
            if node.label and node.type != "map":
                legend.append({"label": node.label, "id": node.name, "type": node.type})

        return AsciiPathway(
            pathway_id=pathway_id,
            title=pathway.title,
            organism=pathway.org or None,
            style=style,
            ascii=ascii_art,
            legend=legend,
            node_count=len(pathway.nodes),
            reaction_count=len(pathway.reactions),
            relation_count=len(pathway.relations),
        )
