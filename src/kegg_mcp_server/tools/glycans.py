from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.glycan import GlycanInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list, summarize_flat_entry
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> GlycanInfo:
    return GlycanInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        composition=p.get("composition"),
        mass=p.get("exact_mass") or p.get("mol_weight"),
        remark=p.get("remark"),
        reaction=p.get("reaction"),
        pathway=p.get("pathway"),
        enzyme=p.get("enzyme"),
        orthology=p.get("orthology"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_glycans(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG glycan database by keyword or composition.

        Args:
            query: Glycan name or composition (e.g. 'GlcNAc', 'Man5', 'sialic acid').
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("glycan", query))
        return build_search_result(query, "glycan", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_glycan_info(
        glycan_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> GlycanInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG glycan entry.

        Args:
            glycan_id: KEGG glycan ID (e.g. 'G00001').
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(glycan_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))
