from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.module import ModuleInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list, summarize_flat_entry
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> ModuleInfo:
    return ModuleInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        definition=p.get("definition"),
        cls=p.get("cls"),
        pathway=p.get("pathway"),
        reaction=p.get("reaction"),
        compound=p.get("compound"),
        enzyme=p.get("enzyme"),
        orthology=p.get("orthology"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_modules(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG modules by keyword.

        Args:
            query: Module name or pathway block (e.g. 'glycolysis', 'TCA cycle').
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("module", query))
        return build_search_result(query, "module", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_module_info(
        module_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> ModuleInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG module.

        Args:
            module_id: KEGG module ID (e.g. 'M00001' for glycolysis core module).
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(module_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))
