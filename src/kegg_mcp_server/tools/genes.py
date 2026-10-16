from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import httpx
from mcp.server.mcpserver import Context

from kegg_mcp_server.errors import KEGGAPIError
from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.gene import GeneInfo
from kegg_mcp_server.parsers import (
    parse_flat_entry,
    parse_link_response,
    parse_tab_list,
    summarize_flat_entry,
)
from kegg_mcp_server.tools._common import (
    MAX_ENTRIES_CAP,
    READ_ONLY,
    build_search_result,
    cap_list,
    kegg_tool,
    not_found_result,
)
from kegg_mcp_server.validators import validate_gene_id, validate_organism_code, validate_query

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

#: KEGG accepts "K1+K2+..." in one /link call; chunk KO ids to this size.
_ORTHOLOG_CHUNK = 10


def _build(p: dict) -> GeneInfo:
    return GeneInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        symbol=p.get("symbol"),
        definition=p.get("definition"),
        orthology=p.get("orthology"),
        organism=p.get("organism"),
        pathway=p.get("pathway"),
        module=p.get("module"),
        brite=p.get("brite"),
        disease=p.get("disease"),
        network=p.get("network"),
        position=p.get("position"),
        motif=p.get("motif"),
        dblinks=p.get("dblinks"),
        aaseq=p.get("aaseq"),
        ntseq=p.get("ntseq"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: MCPServer) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_genes(
        query: str, organism_code: str = "hsa", max_results: int = 25, ctx: Context = None
    ) -> SearchResult:
        """Search for genes in a KEGG organism database.

        Args:
            query: Search term (gene name, symbol, or description).
            organism_code: KEGG organism code (e.g. 'hsa' human, 'mmu' mouse, 'eco' E. coli).
            max_results: Maximum number of results to return (capped at 100).
        """
        query = validate_query(query)
        organism_code = validate_organism_code(organism_code)
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find(organism_code, query))
        return build_search_result(query, organism_code, results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_gene_info(
        gene_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        include_sequence: bool = False,
        ctx: Context = None,
    ) -> GeneInfo | EntrySummary:
        """Get detailed information for a KEGG gene entry.

        Args:
            gene_id: KEGG gene ID in format 'organism:gene' (e.g. 'hsa:1956' for EGFR).
            detail_level: 'summary' (default, compact) or 'full' (complete parse with
                linked orthologs, pathways, xrefs, and references).
            include_sequence: If True and detail_level='full', fetches amino acid and
                nucleotide sequences.
        """
        gene_id = validate_gene_id(gene_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(gene_id)
        if not raw or raw.isspace():
            not_found_result("gene", gene_id)
        parsed = parse_flat_entry(raw)
        if detail_level != "full":
            return EntrySummary(**summarize_flat_entry(parsed))

        info = _build(parsed)
        if not include_sequence:
            info.aaseq = None
            info.ntseq = None
            return info
        if info.aaseq is None:
            try:
                aa_raw = await kegg.get(gene_id, option="aaseq")
                if aa_raw and not aa_raw.isspace():
                    info.aaseq = "".join(aa_raw.splitlines()[1:])
            except (httpx.HTTPError, KEGGAPIError):
                pass
        if info.ntseq is None:
            try:
                nt_raw = await kegg.get(gene_id, option="ntseq")
                if nt_raw and not nt_raw.isspace():
                    info.ntseq = "".join(nt_raw.splitlines()[1:])
            except (httpx.HTTPError, KEGGAPIError):
                pass
        return info

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_gene_orthologs(gene_id: str, ctx: Context = None) -> dict:
        """Get KO (KEGG Orthology) entries and cross-organism orthologs for a gene.

        Args:
            gene_id: KEGG gene ID (e.g. 'hsa:1956').
        """
        gene_id = validate_gene_id(gene_id)
        kegg = ctx.request_context.lifespan_context.kegg
        ko_pairs = parse_link_response(await kegg.link("ko", gene_id))
        ko_ids = [b for _, b in ko_pairs]
        orthologs: dict = {}
        # KEGG accepts "K1+K2+..." in one /link call (verified: 9,394 rows for
        # 10 KOs in one request) — batch instead of one round trip per KO. A
        # failure here (429/5xx) must propagate: silently recording [] made an
        # outage look like "this gene has no orthologs".
        total_orthologs = 0
        truncated = False
        for i in range(0, len(ko_ids), _ORTHOLOG_CHUNK):
            chunk = ko_ids[i : i + _ORTHOLOG_CHUNK]
            orth_pairs = parse_link_response(await kegg.link("genes", "+".join(chunk)))
            by_ko: dict[str, list[tuple[str, str]]] = {ko_id: [] for ko_id in chunk}
            for source, target in orth_pairs:
                by_ko.setdefault(source, []).append((source, target))
            for ko_id, pairs in by_ko.items():
                total_orthologs += len(pairs)
                limited, _, cut = cap_list(pairs, MAX_ENTRIES_CAP)
                truncated = truncated or cut
                orthologs[ko_id] = [{"source": a, "target": b} for a, b in limited]
        return {
            "gene_id": gene_id,
            "ko_entries": ko_ids,
            "ortholog_genes": orthologs,
            "total_orthologs": total_orthologs,
            "truncated": truncated,
        }
