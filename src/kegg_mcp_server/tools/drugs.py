from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.drug import DrugInfo, DrugInteraction, DrugInteractionResult
from kegg_mcp_server.parsers import parse_ddi_response, parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> DrugInfo:
    return DrugInfo(
        entry=p.get("entry", ""), name=p.get("name", ""), formula=p.get("formula"),
        exact_mass=p.get("exact_mass"), mol_weight=p.get("mol_weight"),
        remark=p.get("remark"), comment=p.get("comment"), cls=p.get("cls"),
        pathway=p.get("pathway"), target=p.get("target"), network=p.get("network"),
        interaction=p.get("interaction"), dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_drugs(query: str, search_type: str = "name", max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search KEGG drugs by name, formula, or molecular weight.

        Args:
            query: Drug name, formula, or mass value.
            search_type: 'name' (default), 'formula', 'exact_mass', or 'mol_weight'.
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        option = None if search_type == "name" else search_type
        raw = await kegg.find("drug", query, option=option)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database="drug", total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_drug_info(drug_id: str, ctx: Context = None) -> DrugInfo:
        """Get detailed information for a KEGG drug entry.

        Args:
            drug_id: KEGG drug ID (e.g. 'D00001' for aspirin, 'D00564' for ibuprofen).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(drug_id)))

    @mcp.tool()
    async def get_drug_interactions(drug_ids: str, ctx: Context = None) -> DrugInteractionResult:
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
        return DrugInteractionResult(drug_ids=drug_ids.split("+"), interactions=interactions, count=len(interactions))
