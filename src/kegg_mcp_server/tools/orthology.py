from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.orthology import KOInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> KOInfo:
    return KOInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        definition=p.get("definition"),
        pathway=p.get("pathway"),
        module=p.get("module"),
        disease=p.get("disease"),
        network=p.get("network"),
        brite=p.get("brite"),
        genes=p.get("gene"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_ko_entries(
        query: str, max_results: int = 50, ctx: Context = None
    ) -> SearchResult:
        """Search KEGG Orthology (KO) entries by keyword.

        Args:
            query: Gene function (e.g. 'hexokinase', 'ribosomal protein', 'cytochrome').
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("ko", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(
            query=query,
            database="ko",
            total_found=len(results),
            returned_count=len(limited),
            results=limited,
        )

    @mcp.tool()
    async def get_ko_info(ko_id: str, ctx: Context = None) -> KOInfo:
        """Get detailed information for a KEGG Orthology (KO) entry.

        Args:
            ko_id: KEGG KO identifier (e.g. 'K00844' for hexokinase).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(ko_id)))
