from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.enzyme import EnzymeInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> EnzymeInfo:
    return EnzymeInfo(
        entry=p.get("entry", ""), name=p.get("name", ""), cls=p.get("cls"),
        sysname=p.get("sysname"), reaction=p.get("reaction"),
        substrate=p.get("substrate"), product=p.get("product"), comment=p.get("comment"),
        pathway=p.get("pathway"), orthology=p.get("orthology"), genes=p.get("gene"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_enzymes(query: str, max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search KEGG enzymes by EC number or name.

        Args:
            query: EC number (e.g. '1.1.1.1') or enzyme name (e.g. 'kinase', 'oxidase').
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("enzyme", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database="enzyme", total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_enzyme_info(enzyme_id: str, ctx: Context = None) -> EnzymeInfo:
        """Get detailed information for a KEGG enzyme (EC number).

        Args:
            enzyme_id: EC number (e.g. '1.1.1.1') or prefixed ID (e.g. 'ec:1.1.1.1').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        entry_id = enzyme_id if enzyme_id.startswith("ec:") else f"ec:{enzyme_id}"
        return _build(parse_flat_entry(await kegg.get(entry_id)))
