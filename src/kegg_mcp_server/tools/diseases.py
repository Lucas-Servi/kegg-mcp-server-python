from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.disease import DiseaseInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> DiseaseInfo:
    return DiseaseInfo(
        entry=p.get("entry", ""), name=p.get("name", ""), description=p.get("description"),
        category=p.get("category"), gene=p.get("gene"), pathway=p.get("pathway"),
        module=p.get("module"), network=p.get("network"), drug=p.get("drug"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_diseases(query: str, max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search KEGG diseases by name or keyword.

        Args:
            query: Disease name (e.g. 'diabetes', 'cancer', 'Alzheimer').
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("disease", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database="disease", total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_disease_info(disease_id: str, ctx: Context = None) -> DiseaseInfo:
        """Get detailed information for a KEGG disease entry.

        Args:
            disease_id: KEGG disease ID (e.g. 'H00004' for colorectal cancer).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(disease_id)))
