from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.glycan import GlycanInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> GlycanInfo:
    return GlycanInfo(
        entry=p.get("entry", ""), name=p.get("name", ""),
        composition=p.get("composition"), mass=p.get("exact_mass") or p.get("mol_weight"),
        remark=p.get("remark"), reaction=p.get("reaction"), pathway=p.get("pathway"),
        enzyme=p.get("enzyme"), orthology=p.get("orthology"), dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_glycans(query: str, max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search KEGG glycan database by keyword or composition.

        Args:
            query: Glycan name or composition (e.g. 'GlcNAc', 'Man5', 'sialic acid').
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("glycan", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database="glycan", total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_glycan_info(glycan_id: str, ctx: Context = None) -> GlycanInfo:
        """Get detailed information for a KEGG glycan entry.

        Args:
            glycan_id: KEGG glycan ID (e.g. 'G00001').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(glycan_id)))
