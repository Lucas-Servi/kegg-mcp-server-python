from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.pathway import PathwayInfo, PathwayLinks
from kegg_mcp_server.parsers import (
    parse_flat_entry,
    parse_link_response,
    parse_tab_list,
    summarize_flat_entry,
)
from kegg_mcp_server.tools._common import (
    READ_ONLY,
    build_search_result,
    cap_list,
    kegg_tool,
    not_found_result,
)
from kegg_mcp_server.validators import validate_organism_code, validate_pathway_id, validate_query

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def _ensure_path_prefix(pathway_id: str) -> str:
    """Ensure pathway ID has the 'path:' prefix required by KEGG link/get APIs."""
    if not pathway_id.startswith("path:"):
        return f"path:{pathway_id}"
    return pathway_id


def _pathway_genes_target(pathway_id: str) -> str:
    """Return the correct target_db for a genes link call against this pathway.

    KEGG rejects /link/genes/path:<id> with 400 for all pathway types.
    The only working form is /link/<org_code>/path:<org_code><num>.
    For reference pathways (map*) we fall back to 'genes' and let the API
    return an empty result or KEGGAPIError that the kegg_tool decorator handles.
    """
    bare = pathway_id.removeprefix("path:")
    m = re.match(r"^([a-zA-Z]+)\d+$", bare)
    if not m:
        return "genes"
    org = m.group(1).lower()
    return "genes" if org == "map" else org


def _filter_pathways_by_query(pathways: dict[str, str], query: str) -> dict[str, str]:
    """Filter pathways by query tokens (case-insensitive) across ID + description."""
    terms = [t.lower() for t in re.split(r"\s+", query.strip()) if t]
    if not terms:
        return pathways
    filtered: dict[str, str] = {}
    for pathway_id, description in pathways.items():
        haystack = f"{pathway_id} {description}".lower()
        if all(term in haystack for term in terms):
            filtered[pathway_id] = description
    return filtered


def _build(p: dict) -> PathwayInfo:
    return PathwayInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        cls=p.get("cls"),
        description=p.get("description"),
        organism=p.get("organism"),
        gene=p.get("gene"),
        compound=p.get("compound"),
        reaction=p.get("reaction"),
        module=p.get("module"),
        disease=p.get("disease"),
        drug=p.get("drug"),
        network=p.get("network"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: MCPServer) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_pathways(
        query: str, organism_code: str = "map", max_results: int = 25, ctx: Context = None
    ) -> SearchResult:
        """Search KEGG pathways by keyword.

        Args:
            query: Search term (e.g. 'glycolysis', 'TCA', 'insulin signaling').
            organism_code: 3-4 letter organism code (e.g. 'hsa' for human, 'mmu' for mouse).
                Use 'map' for reference pathways.
            max_results: Maximum number of results to return (capped at 100).
        """
        query = validate_query(query)
        organism_code = validate_organism_code(organism_code)
        kegg = ctx.request_context.lifespan_context.kegg
        normalized_organism = organism_code

        if normalized_organism == "map":
            db = "pathway"
            results = parse_tab_list(await kegg.find(db, query))
        else:
            db = f"pathway/{normalized_organism}"
            results = _filter_pathways_by_query(parse_tab_list(await kegg.list(db)), query)

        return build_search_result(query, db, results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_info(
        pathway_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> PathwayInfo | EntrySummary:
        """Get detailed information for a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010', 'map00010').
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse
                with all linked genes, compounds, reactions, references, and xrefs).
        """
        pathway_id = validate_pathway_id(pathway_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(pathway_id)
        if not raw or raw.isspace():
            not_found_result("pathway", pathway_id)
        parsed = parse_flat_entry(raw)
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_genes(
        pathway_id: str, max_results: int = 100, ctx: Context = None
    ) -> PathwayLinks:
        """Get all genes associated with a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010'). Use organism-specific
                IDs (e.g. 'pae00350' for P. aeruginosa) — reference pathways
                ('map*') are not supported by the KEGG gene link API.
            max_results: Maximum number of pairs to return (capped at 100).
        """
        pathway_id = validate_pathway_id(pathway_id)
        bare = pathway_id.removeprefix("path:")
        if re.match(r"^map\d+$", bare):
            raise ToolError(
                ErrorResult(
                    error=(
                        f"Gene link queries are not supported for reference pathways ('{bare}'). "
                        "Use an organism-specific pathway ID instead "
                        "(e.g. 'pae00350' for P. aeruginosa, 'eco00350' for E. coli). "
                        "Use search_pathways(organism_code='pae') to find organism-specific IDs."
                    ),
                    code="unsupported_pathway_type",
                    retryable=False,
                    hint="Replace 'map' prefix with the organism code (e.g. pae, eco, hsa).",
                ).model_dump_json()
            )
        kegg = ctx.request_context.lifespan_context.kegg
        source = _ensure_path_prefix(pathway_id)
        target = _pathway_genes_target(pathway_id)
        pairs = parse_link_response(await kegg.link(target, source))
        limited, total, truncated = cap_list(pairs, max_results)
        return PathwayLinks(
            pathway_id=pathway_id, linked_db=target, pairs=limited, count=total, truncated=truncated
        )

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_compounds(
        pathway_id: str, max_results: int = 100, ctx: Context = None
    ) -> PathwayLinks:
        """Get all compounds (metabolites) associated with a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'map00010').
            max_results: Maximum number of pairs to return (capped at 100).
        """
        pathway_id = validate_pathway_id(pathway_id)
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("compound", _ensure_path_prefix(pathway_id)))
        limited, total, truncated = cap_list(pairs, max_results)
        return PathwayLinks(
            pathway_id=pathway_id, linked_db="compound", pairs=limited, count=total,
            truncated=truncated,
        )

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_pathway_reactions(
        pathway_id: str, max_results: int = 100, ctx: Context = None
    ) -> PathwayLinks:
        """Get all reactions in a KEGG pathway.

        Args:
            pathway_id: KEGG pathway ID (e.g. 'hsa00010').
            max_results: Maximum number of pairs to return (capped at 100).
        """
        pathway_id = validate_pathway_id(pathway_id)
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link("reaction", _ensure_path_prefix(pathway_id)))
        limited, total, truncated = cap_list(pairs, max_results)
        return PathwayLinks(
            pathway_id=pathway_id, linked_db="reaction", pairs=limited, count=total,
            truncated=truncated,
        )
