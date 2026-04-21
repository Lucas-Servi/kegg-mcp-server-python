from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.pathway import PathwayInfo, PathwayLinks
from kegg_mcp_server.parsers import (
    parse_flat_entry,
    parse_link_response,
    parse_tab_list,
    summarize_flat_entry,
)
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _filter_pathways_by_query(pathways: dict[str, str], query: str) -> dict[str, str]:
    """Filter pathways by query tokens (case-insensitive) across ID + description."""
    terms = [t.lower() for t in re.split(r"\s+", query.strip()) if t]
    if not terms:
        return pathways
    filtered: dict[str, str] = {}
    for pathway_id, description in pathways.items():
        haystack = f"{pathway_id} {description}".lower()
        if all(term in haystack for term in terms):
            filtered[pathway_id] = description
    return filtered


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

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_pathways(
        query: str, organism_code: str = "map", max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG pathways by keyword.

        Args:
            query: Search term (e.g. 'glycolysis', 'TCA', 'insulin signaling').
            organism_code: 3-4 letter organism code (e.g. 'hsa' for human, 'mmu' for mouse).
                Use 'map' for reference pathways.
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        normalized_organism = organism_code.strip().lower()

        if normalized_organism == "map":
            db = "pathway"
            results = parse_tab_list(await kegg.find(db, query))
        else:
            db = f"pathway/{normalized_organism}"
            results = _filter_pathways_by_query(parse_tab_list(await kegg.list(db)), query)

        return build_search_result(query, db, results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_info(
        pathway_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> PathwayInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010', 'map00010').
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse
                with all linked genes, compounds, reactions, references, and xrefs).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(pathway_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_genes(
        pathway_id: str, ctx: Context = None
    ) -> PathwayLinks | ErrorResult:
        """Get all genes associated with a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("genes", pathway_id))
        return PathwayLinks(pathway_id=pathway_id, linked_db="genes", pairs=pairs, count=len(pairs))

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_compounds(
        pathway_id: str, ctx: Context = None
    ) -> PathwayLinks | ErrorResult:
        """Get all compounds (metabolites) associated with a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'map00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("compound", pathway_id))
        return PathwayLinks(
            pathway_id=pathway_id, linked_db="compound", pairs=pairs, count=len(pairs)
        )

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_reactions(
        pathway_id: str, ctx: Context = None
    ) -> PathwayLinks | ErrorResult:
        """Get all reactions in a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("reaction", pathway_id))
        return PathwayLinks(
            pathway_id=pathway_id, linked_db="reaction", pairs=pairs, count=len(pairs)
        )
