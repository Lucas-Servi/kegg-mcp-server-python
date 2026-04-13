from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.gene import GeneInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_link_response, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> GeneInfo:
    return GeneInfo(
        entry=p.get("entry", ""), name=p.get("name", ""), definition=p.get("definition"),
        orthology=p.get("orthology"), organism=p.get("organism"), pathway=p.get("pathway"),
        module=p.get("module"), brite=p.get("brite"), disease=p.get("disease"),
        network=p.get("network"), position=p.get("position"), motif=p.get("motif"),
        dblinks=p.get("dblinks"), aaseq=p.get("aaseq"), ntseq=p.get("ntseq"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_genes(query: str, organism_code: str = "hsa", max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search for genes in a KEGG organism database.

        Args:
            query: Search term (gene name, symbol, or description).
            organism_code: KEGG organism code (e.g. 'hsa' human, 'mmu' mouse, 'eco' E. coli).
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find(organism_code, query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database=organism_code, total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_gene_info(gene_id: str, include_sequence: bool = False, ctx: Context = None) -> GeneInfo:
        """Get detailed information for a KEGG gene entry.

        Args:
            gene_id: KEGG gene ID in format 'organism:gene' (e.g. 'hsa:1956' for EGFR).
            include_sequence: If True, fetches amino acid and nucleotide sequences.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        info = _build(parse_flat_entry(await kegg.get(gene_id)))
        if include_sequence and info.aaseq is None:
            try:
                aa_raw = await kegg.get(gene_id, option="aaseq")
                nt_raw = await kegg.get(gene_id, option="ntseq")
                info.aaseq = "".join(aa_raw.splitlines()[1:])
                info.ntseq = "".join(nt_raw.splitlines()[1:])
            except Exception:
                pass
        return info

    @mcp.tool()
    async def get_gene_orthologs(gene_id: str, ctx: Context = None) -> dict:
        """Get KO (KEGG Orthology) entries and cross-organism orthologs for a gene.

        Args:
            gene_id: KEGG gene ID (e.g. 'hsa:1956').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        ko_pairs = parse_link_response(await kegg.link("ko", gene_id))
        ko_ids = [b for _, b in ko_pairs]
        orthologs: dict = {}
        for ko_id in ko_ids:
            try:
                orth_pairs = parse_link_response(await kegg.link("genes", ko_id))
                orthologs[ko_id] = [{"source": a, "target": b} for a, b in orth_pairs]
            except Exception:
                orthologs[ko_id] = []
        return {
            "gene_id": gene_id,
            "ko_entries": ko_ids,
            "ortholog_genes": orthologs,
            "total_orthologs": sum(len(v) for v in orthologs.values()),
        }
