"""MCP resource templates for direct KEGG entity access by URI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_resources(mcp: FastMCP) -> None:

    @mcp.resource("kegg://pathway/{pathway_id}")
    async def pathway_resource(pathway_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG pathway entry as structured JSON.

        Args:
            pathway_id: KEGG pathway ID (e.g. hsa00010, map00020).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(pathway_id)
        parsed = parse_flat_entry(raw)
        return json.dumps(parsed, indent=2)

    @mcp.resource("kegg://gene/{gene_id}")
    async def gene_resource(gene_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG gene entry as structured JSON.

        Args:
            gene_id: KEGG gene ID (e.g. hsa:1956 for EGFR).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(gene_id)
        parsed = parse_flat_entry(raw)
        return json.dumps(parsed, indent=2)

    @mcp.resource("kegg://compound/{compound_id}")
    async def compound_resource(compound_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG compound entry as structured JSON.

        Args:
            compound_id: KEGG compound ID (e.g. C00002 for ATP).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(compound_id)
        parsed = parse_flat_entry(raw)
        return json.dumps(parsed, indent=2)

    @mcp.resource("kegg://reaction/{reaction_id}")
    async def reaction_resource(reaction_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG reaction entry as structured JSON.

        Args:
            reaction_id: KEGG reaction ID (e.g. R00756).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(reaction_id)
        parsed = parse_flat_entry(raw)
        return json.dumps(parsed, indent=2)

    @mcp.resource("kegg://disease/{disease_id}")
    async def disease_resource(disease_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG disease entry as structured JSON.

        Args:
            disease_id: KEGG disease ID (e.g. H00004).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(disease_id)
        parsed = parse_flat_entry(raw)
        return json.dumps(parsed, indent=2)

    @mcp.resource("kegg://drug/{drug_id}")
    async def drug_resource(drug_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG drug entry as structured JSON.

        Args:
            drug_id: KEGG drug ID (e.g. D00001 for aspirin).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(drug_id)
        parsed = parse_flat_entry(raw)
        return json.dumps(parsed, indent=2)

    @mcp.resource("kegg://organism/{org_code}")
    async def organism_resource(org_code: str, ctx: Context = None) -> str:
        """List all pathways available for a KEGG organism.

        Args:
            org_code: KEGG organism code (e.g. hsa, mmu, eco).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.list(f"pathway/{org_code}")
        items = parse_tab_list(raw)
        return json.dumps({"organism": org_code, "pathways": items, "count": len(items)}, indent=2)

    @mcp.resource("kegg://search/{database}/{query}")
    async def search_resource(database: str, query: str, ctx: Context = None) -> str:
        """Search any KEGG database and return results as JSON.

        Args:
            database: KEGG database name (e.g. pathway, compound, drug, disease, ko).
            query: Search keyword.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find(database, query)
        results = parse_tab_list(raw)
        return json.dumps(
            {"database": database, "query": query, "results": results, "count": len(results)},
            indent=2,
        )
