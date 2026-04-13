from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.common import BatchLookupResult, ConversionResult, LinkResult
from kegg_mcp_server.parsers import parse_conv_response, parse_link_response, parse_multi_flat

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_MAX_BATCH = 50


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def batch_entry_lookup(entry_ids: list[str], ctx: Context = None) -> BatchLookupResult:
        """Fetch multiple KEGG entries in bulk (max 50 IDs).

        Automatically chunks requests into groups of 10 to respect KEGG's API limit.

        Args:
            entry_ids: List of KEGG entry IDs (e.g. ['C00002', 'C00031', 'C00033']).
                Can mix databases. Max 50 entries.
        """
        if len(entry_ids) > _MAX_BATCH:
            raise ValueError(f"Maximum {_MAX_BATCH} entries per batch request")
        kegg = ctx.request_context.lifespan_context.kegg
        raw_chunks = await kegg.get_batch(entry_ids)
        all_parsed = []
        for chunk in raw_chunks:
            all_parsed.extend(parse_multi_flat(chunk))
        return BatchLookupResult(requested=entry_ids, found=len(all_parsed), entries=all_parsed)

    @mcp.tool()
    async def convert_identifiers(source_db: str, target_db: str, entry_ids: list[str] | None = None, ctx: Context = None) -> ConversionResult:
        """Convert KEGG IDs to/from external database identifiers.

        Args:
            source_db: Source database (e.g. 'hsa', 'ncbi-geneid', 'uniprot', 'chebi', 'pubchem').
            target_db: Target database (e.g. 'kegg', 'ncbi-geneid', 'uniprot').
            entry_ids: Optional list of specific IDs to convert (max 10). If None,
                converts the full source database.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        source = "+".join(entry_ids[:10]) if entry_ids else source_db
        mappings = parse_conv_response(await kegg.conv(target_db, source))
        return ConversionResult(source_db=source_db, target_db=target_db, mappings=mappings, count=len(mappings))

    @mcp.tool()
    async def find_related_entries(entry_id: str, target_db: str, ctx: Context = None) -> LinkResult:
        """Find related entries in another KEGG database for a given entry.

        Args:
            entry_id: Source KEGG entry ID (e.g. 'hsa:1956', 'C00002', 'K00844').
            target_db: Target database (e.g. 'pathway', 'disease', 'drug', 'ko',
                'compound', 'reaction', 'module', 'genes').
        """
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link(target_db, entry_id))
        return LinkResult(source=entry_id, target_db=target_db, pairs=pairs, count=len(pairs))
