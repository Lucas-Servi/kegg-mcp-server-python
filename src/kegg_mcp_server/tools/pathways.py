from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.pathway import PathwayInfo, PathwayLinks
from kegg_mcp_server.parsers import parse_flat_entry, parse_link_response, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> PathwayInfo:
    return PathwayInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        cls=p.get("cls"),
        description=p.get("description"),
        organism=p.get("organism"),
        gene=p.get("gene"),
        compound=p.get("compound"),
        reaction=p.get("reaction"),
        module=p.get("module"),
        disease=p.get("disease"),
        drug=p.get("drug"),
        network=p.get("network"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_pathways(
        query: str, organism_code: str = "map", max_results: int = 50, ctx: Context = None
    ) -> SearchResult:
        """Search KEGG pathways by keyword.

        Args:
            query: Search term (e.g. 'glycolysis', 'TCA', 'insulin signaling').
            organism_code: 3-4 letter organism code (e.g. 'hsa' for human, 'mmu' for mouse).
                Use 'map' for reference pathways.
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        db = f"pathway/{organism_code}" if organism_code != "map" else "pathway"
        raw = await kegg.find(db, query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(
            query=query,
            database=db,
            total_found=len(results),
            returned_count=len(limited),
            results=limited,
        )

    @mcp.tool()
    async def get_pathway_info(pathway_id: str, ctx: Context = None) -> PathwayInfo:
        """Get detailed information for a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010', 'map00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(pathway_id)))

    @mcp.tool()
    async def get_pathway_genes(pathway_id: str, ctx: Context = None) -> PathwayLinks:
        """Get all genes associated with a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("genes", pathway_id))
        return PathwayLinks(pathway_id=pathway_id, linked_db="genes", pairs=pairs, count=len(pairs))

    @mcp.tool()
    async def get_pathway_compounds(pathway_id: str, ctx: Context = None) -> PathwayLinks:
        """Get all compounds (metabolites) associated with a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'map00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("compound", pathway_id))
        return PathwayLinks(
            pathway_id=pathway_id, linked_db="compound", pairs=pairs, count=len(pairs)
        )

    @mcp.tool()
    async def get_pathway_reactions(pathway_id: str, ctx: Context = None) -> PathwayLinks:
        """Get all reactions in a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("reaction", pathway_id))
        return PathwayLinks(
            pathway_id=pathway_id, linked_db="reaction", pairs=pairs, count=len(pairs)
        )
