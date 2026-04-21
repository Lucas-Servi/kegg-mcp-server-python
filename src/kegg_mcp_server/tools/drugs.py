from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.drug import DrugInfo, DrugInteraction, DrugInteractionResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import (
    parse_ddi_response,
    parse_flat_entry,
    parse_tab_list,
    summarize_flat_entry,
)
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> DrugInfo:
    return DrugInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        formula=p.get("formula"),
        exact_mass=p.get("exact_mass"),
        mol_weight=p.get("mol_weight"),
        remark=p.get("remark"),
        comment=p.get("comment"),
        cls=p.get("cls"),
        pathway=p.get("pathway"),
        target=p.get("target"),
        network=p.get("network"),
        interaction=p.get("interaction"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_drugs(
        query: str, search_type: str = "name", max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG drugs by name, formula, or molecular weight.

        Args:
            query: Drug name, formula, or mass value.
            search_type: 'name' (default), 'formula', 'exact_mass', or 'mol_weight'.
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        option = None if search_type == "name" else search_type
        results = parse_tab_list(await kegg.find("drug", query, option=option))
        return build_search_result(query, "drug", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_drug_info(
        drug_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> DrugInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG drug entry.

        Args:
            drug_id: KEGG drug ID (e.g. 'D00001' for aspirin, 'D00564' for ibuprofen).
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(drug_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_drug_interactions(
        drug_ids: str, ctx: Context = None
    ) -> DrugInteractionResult | ErrorResult:
        """Get drug-drug interactions for one or more KEGG drugs.

        Args:
            drug_ids: Single drug ID (e.g. 'D00001') or multiple IDs joined with '+'
                (e.g. 'D00001+D00564'). Max 10 entries.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.ddi(drug_ids)
        interactions = [
            DrugInteraction(drug1=d["drug1"], drug2=d["drug2"], interaction=d["interaction"])
            for d in parse_ddi_response(raw)
        ]
        return DrugInteractionResult(
            drug_ids=drug_ids.split("+"), interactions=interactions, count=len(interactions)
        )
