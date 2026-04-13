from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.module import ModuleInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> ModuleInfo:
    return ModuleInfo(
        entry=p.get("entry", ""), name=p.get("name", ""), definition=p.get("definition"),
        cls=p.get("cls"), pathway=p.get("pathway"), reaction=p.get("reaction"),
        compound=p.get("compound"), enzyme=p.get("enzyme"), orthology=p.get("orthology"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_modules(query: str, max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search KEGG modules by keyword.

        Args:
            query: Module name or pathway block (e.g. 'glycolysis', 'TCA cycle').
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("module", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database="module", total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_module_info(module_id: str, ctx: Context = None) -> ModuleInfo:
        """Get detailed information for a KEGG module.

        Args:
            module_id: KEGG module ID (e.g. 'M00001' for glycolysis core module).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(module_id)))
