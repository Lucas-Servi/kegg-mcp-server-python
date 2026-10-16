"""MCP resource templates for direct KEGG entity access by URI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list
from kegg_mcp_server.tools._common import cap_list, cap_mapping
from kegg_mcp_server.validators import (
    validate_compound_id,
    validate_disease_id,
    validate_drug_id,
    validate_gene_id,
    validate_organism_code,
    validate_pathway_id,
    validate_query,
    validate_reaction_id,
)

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def _cap_parsed(parsed: dict[str, Any]) -> dict[str, Any]:
    """Bound every dict/list field of a parsed flat entry before it goes out as JSON."""
    capped: dict[str, Any] = {}
    for key, value in parsed.items():
        if isinstance(value, dict):
            limited, _, truncated = cap_mapping(value)
            capped[key] = limited
        elif isinstance(value, list):
            limited, _, truncated = cap_list(value)
            capped[key] = limited
        else:
            capped[key] = value
            truncated = False
        if truncated:
            capped[f"{key}_truncated"] = True
    return capped


def _dumps(data: Any) -> str:
    """Compact JSON — resources were dumping `indent=2`, doubling output size for nothing."""
    return json.dumps(data, separators=(",", ":"))


def register_resources(mcp: MCPServer) -> None:

    @mcp.resource("kegg://pathway/{pathway_id}")
    async def pathway_resource(pathway_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG pathway entry as structured JSON.

        Args:
            pathway_id: KEGG pathway ID (e.g. hsa00010, map00020).
        """
        pathway_id = validate_pathway_id(pathway_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(pathway_id)
        if not raw or raw.isspace():
            raise ResourceNotFoundError(f"KEGG pathway not found: {pathway_id}")
        return _dumps(_cap_parsed(parse_flat_entry(raw)))

    @mcp.resource("kegg://gene/{gene_id}")
    async def gene_resource(gene_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG gene entry as structured JSON.

        Args:
            gene_id: KEGG gene ID (e.g. hsa:1956 for EGFR).
        """
        gene_id = validate_gene_id(gene_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(gene_id)
        if not raw or raw.isspace():
            raise ResourceNotFoundError(f"KEGG gene not found: {gene_id}")
        return _dumps(_cap_parsed(parse_flat_entry(raw)))

    @mcp.resource("kegg://compound/{compound_id}")
    async def compound_resource(compound_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG compound entry as structured JSON.

        Args:
            compound_id: KEGG compound ID (e.g. C00002 for ATP).
        """
        compound_id = validate_compound_id(compound_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(compound_id)
        if not raw or raw.isspace():
            raise ResourceNotFoundError(f"KEGG compound not found: {compound_id}")
        return _dumps(_cap_parsed(parse_flat_entry(raw)))

    @mcp.resource("kegg://reaction/{reaction_id}")
    async def reaction_resource(reaction_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG reaction entry as structured JSON.

        Args:
            reaction_id: KEGG reaction ID (e.g. R00756).
        """
        reaction_id = validate_reaction_id(reaction_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(reaction_id)
        if not raw or raw.isspace():
            raise ResourceNotFoundError(f"KEGG reaction not found: {reaction_id}")
        return _dumps(_cap_parsed(parse_flat_entry(raw)))

    @mcp.resource("kegg://disease/{disease_id}")
    async def disease_resource(disease_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG disease entry as structured JSON.

        Args:
            disease_id: KEGG disease ID (e.g. H00004).
        """
        disease_id = validate_disease_id(disease_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(disease_id)
        if not raw or raw.isspace():
            raise ResourceNotFoundError(f"KEGG disease not found: {disease_id}")
        return _dumps(_cap_parsed(parse_flat_entry(raw)))

    @mcp.resource("kegg://drug/{drug_id}")
    async def drug_resource(drug_id: str, ctx: Context = None) -> str:
        """Retrieve a KEGG drug entry as structured JSON.

        Args:
            drug_id: KEGG drug ID (e.g. D00001 for aspirin).
        """
        drug_id = validate_drug_id(drug_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(drug_id)
        if not raw or raw.isspace():
            raise ResourceNotFoundError(f"KEGG drug not found: {drug_id}")
        return _dumps(_cap_parsed(parse_flat_entry(raw)))

    @mcp.resource("kegg://organism/{org_code}")
    async def organism_resource(org_code: str, ctx: Context = None) -> str:
        """List all pathways available for a KEGG organism.

        Args:
            org_code: KEGG organism code (e.g. hsa, mmu, eco).
        """
        org_code = validate_organism_code(org_code)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.list(f"pathway/{org_code}")
        items, total, truncated = cap_mapping(parse_tab_list(raw))
        return _dumps(
            {"organism": org_code, "pathways": items, "count": total, "truncated": truncated}
        )

    @mcp.resource("kegg://pathway/{pathway_id}/ascii")
    async def pathway_ascii_resource(pathway_id: str, ctx: Context = None) -> str:
        """Render a KEGG pathway as ASCII text (chain mode).

        Args:
            pathway_id: KEGG pathway ID (e.g. hsa00010).
        """
        from kegg_mcp_server.ascii import parse_kgml, render_chain

        pathway_id = validate_pathway_id(pathway_id)
        kegg = ctx.request_context.lifespan_context.kegg
        kgml_xml = await kegg.get(pathway_id, option="kgml")
        if not kgml_xml or kgml_xml.isspace():
            raise ResourceNotFoundError(f"No KGML data available for pathway {pathway_id}")
        pathway = parse_kgml(kgml_xml)
        return render_chain(pathway)

    @mcp.resource("kegg://search/{database}/{query}")
    async def search_resource(database: str, query: str, ctx: Context = None) -> str:
        """Search any KEGG database and return results as JSON.

        Args:
            database: KEGG database name (e.g. pathway, compound, drug, disease, ko).
            query: Search keyword.
        """
        database = validate_query(database, max_len=50)
        query = validate_query(query)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find(database, query)
        results, total, truncated = cap_mapping(parse_tab_list(raw))
        return _dumps(
            {
                "database": database,
                "query": query,
                "results": results,
                "count": total,
                "truncated": truncated,
            }
        )
