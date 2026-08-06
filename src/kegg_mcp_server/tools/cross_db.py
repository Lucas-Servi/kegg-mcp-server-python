from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import BatchLookupResult, ConversionResult, LinkResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import parse_conv_response, parse_link_response, parse_multi_flat
from kegg_mcp_server.tools._common import READ_ONLY, kegg_tool
from kegg_mcp_server.validators import validate_conv_pair, validate_link_database

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_MAX_BATCH = 50


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def batch_entry_lookup(
        entry_ids: list[str], ctx: Context = None
    ) -> BatchLookupResult | ErrorResult:
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

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def convert_identifiers(
        source_db: str, target_db: str, entry_ids: list[str] | None = None, ctx: Context = None
    ) -> ConversionResult | ErrorResult:
        """Convert KEGG IDs to/from external database identifiers.

        Converts within one kind only, KEGG side <-> outside side:
        genes (organism code 'hsa' or T-number 'T01001') <-> ncbi-geneid /
        ncbi-proteinid / uniprot; chemistry (compound / drug / glycan) <->
        pubchem / chebi. Cross-kind pairs such as compound<->uniprot are
        rejected by KEGG, and 'kegg' is not a database conv accepts.

        Args:
            source_db: Source database — 'hsa', 'T01001', 'ncbi-geneid',
                'ncbi-proteinid', 'uniprot', 'compound', 'drug', 'glycan',
                'pubchem' or 'chebi'.
            target_db: Target database, from the same list and the opposite side
                of the pair (e.g. source_db='hsa' + target_db='uniprot', or
                source_db='chebi' + target_db='compound').
            entry_ids: Optional list of specific IDs to convert. Bare ids are
                prefixed with source_db automatically ('1956' -> 'hsa:1956').
                KEGG accepts at most 10 per request; only the first 10 are sent.
                If None, converts the full source database (large: hsa <->
                ncbi-geneid is ~700 KB).
        """
        source_db, target_db = validate_conv_pair(
            source_db, target_db, has_entry_ids=bool(entry_ids)
        )
        kegg = ctx.request_context.lifespan_context.kegg
        if entry_ids:
            # KEGG needs each id namespaced by its own database — a bare '1956'
            # is a 400. Discarding source_db here (the original bug) made every
            # entry_ids call fail while looking like a valid request.
            source = "+".join(
                eid if ":" in eid else f"{source_db}:{eid}" for eid in entry_ids[:10]
            )
        else:
            source = source_db
        mappings = parse_conv_response(await kegg.conv(target_db, source))
        return ConversionResult(
            source_db=source_db, target_db=target_db, mappings=mappings, count=len(mappings)
        )

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def find_related_entries(
        entry_id: str, target_db: str, ctx: Context = None
    ) -> LinkResult | ErrorResult:
        """Find related entries in another KEGG database for a given entry.

        Args:
            entry_id: Source KEGG entry ID (e.g. 'hsa:1956', 'C00002', 'K00844').
            target_db: Target database (e.g. 'pathway', 'disease', 'drug', 'ko',
                'compound', 'reaction', 'module', 'genes').
        """
        target_db = validate_link_database(target_db)
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link(target_db, entry_id))
        return LinkResult(source=entry_id, target_db=target_db, pairs=pairs, count=len(pairs))
