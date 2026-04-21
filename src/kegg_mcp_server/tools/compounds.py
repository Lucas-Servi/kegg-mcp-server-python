from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.compound import CompoundInfo
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import (
    parse_flat_entry,
    parse_link_response,
    parse_tab_list,
    summarize_flat_entry,
)
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> CompoundInfo:
    return CompoundInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        formula=p.get("formula"),
        exact_mass=p.get("exact_mass"),
        mol_weight=p.get("mol_weight"),
        remark=p.get("remark"),
        comment=p.get("comment"),
        reaction=p.get("reaction"),
        pathway=p.get("pathway"),
        module=p.get("module"),
        enzyme=p.get("enzyme"),
        network=p.get("network"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_compounds(
        query: str, search_type: str = "name", max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG compounds by name or chemical property.

        Args:
            query: Search term (compound name, formula, or mass).
            search_type: 'name' (default), 'formula', 'exact_mass', 'mol_weight', or 'nop'.
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        option = None if search_type == "name" else search_type
        results = parse_tab_list(await kegg.find("compound", query, option=option))
        return build_search_result(query, "compound", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_compound_info(
        compound_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> CompoundInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG compound entry.

        Args:
            compound_id: KEGG compound ID (e.g. 'C00002' for ATP, 'C00031' for D-Glucose).
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(compound_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_compound_reactions(
        compound_id: str, ctx: Context = None
    ) -> dict | ErrorResult:
        """Get all reactions involving a KEGG compound.

        Args:
            compound_id: KEGG compound ID (e.g. 'C00002').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("reaction", compound_id))
        return {
            "compound_id": compound_id,
            "reactions": [{"compound": a, "reaction": b} for a, b in pairs],
            "count": len(pairs),
        }
