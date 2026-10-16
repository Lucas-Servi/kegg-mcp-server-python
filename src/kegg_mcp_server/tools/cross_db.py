from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from mcp.server.mcpserver import Context

from kegg_mcp_server.models.common import BatchLookupResult, ConversionResult, LinkResult
from kegg_mcp_server.parsers import (
    parse_conv_response,
    parse_link_response,
    parse_multi_flat,
    summarize_flat_entry,
)
from kegg_mcp_server.tools._common import READ_ONLY, cap_list, kegg_tool
from kegg_mcp_server.validators import validate_conv_pair, validate_link_database, validate_query

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

_MAX_BATCH = 50
_CONV_CHUNK = 10


def register(mcp: MCPServer) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def batch_entry_lookup(
        entry_ids: list[str],
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> BatchLookupResult:
        """Fetch multiple KEGG entries in bulk (max 50 IDs).

        Automatically chunks requests into groups of 10 to respect KEGG's API limit.

        Args:
            entry_ids: List of KEGG entry IDs (e.g. ['C00002', 'C00031', 'C00033']).
                Can mix databases. Max 50 entries.
            detail_level: 'summary' (default, compact per-entry projection) or
                'full' (complete flat-file parse — sequences and GENES lists make
                this large for 50 entries at once).
        """
        if len(entry_ids) > _MAX_BATCH:
            raise ValueError(f"Maximum {_MAX_BATCH} entries per batch request")
        entry_ids = [validate_query(eid, max_len=50) for eid in entry_ids]
        kegg = ctx.request_context.lifespan_context.kegg
        raw_chunks = await kegg.get_batch(entry_ids)
        all_parsed = []
        for chunk in raw_chunks:
            all_parsed.extend(parse_multi_flat(chunk))
        entries = (
            all_parsed if detail_level == "full" else [summarize_flat_entry(p) for p in all_parsed]
        )
        return BatchLookupResult(requested=entry_ids, found=len(entries), entries=entries)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def convert_identifiers(
        source_db: str, target_db: str, entry_ids: list[str] | None = None, ctx: Context = None
    ) -> ConversionResult:
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
                KEGG accepts at most 10 per request; longer lists are chunked and
                fetched concurrently rather than silently dropped.
                If None, converts the full source database (large: hsa <->
                ncbi-geneid is ~700 KB).
        """
        if entry_ids is not None and len(entry_ids) == 0:
            # KEGG treats an empty entry_ids the same as None — the WHOLE
            # database (~700 KB, ~20k mappings) would land in the model's
            # context, which is never what an explicit `[]` means.
            raise ValueError("entry_ids must not be empty; omit it to convert the whole database")
        source_db, target_db = validate_conv_pair(
            source_db, target_db, has_entry_ids=bool(entry_ids)
        )
        kegg = ctx.request_context.lifespan_context.kegg
        if entry_ids:
            # KEGG needs each id namespaced by its own database — a bare '1956'
            # is a 400. Discarding source_db here (the original bug) made every
            # entry_ids call fail while looking like a valid request.
            namespaced = [eid if ":" in eid else f"{source_db}:{eid}" for eid in entry_ids]
            chunks = [
                "+".join(namespaced[i : i + _CONV_CHUNK])
                for i in range(0, len(namespaced), _CONV_CHUNK)
            ]
            responses = await asyncio.gather(*(kegg.conv(target_db, c) for c in chunks))
        else:
            responses = [await kegg.conv(target_db, source_db)]
        mappings: dict[str, list[str]] = {}
        for response in responses:
            for source, targets in parse_conv_response(response).items():
                mappings.setdefault(source, []).extend(targets)
        return ConversionResult(
            source_db=source_db,
            target_db=target_db,
            mappings=mappings,
            count=sum(len(v) for v in mappings.values()),
        )

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def find_related_entries(
        entry_id: str, target_db: str, max_results: int = 100, ctx: Context = None
    ) -> LinkResult:
        """Find related entries in another KEGG database for a given entry.

        Args:
            entry_id: Source KEGG entry ID (e.g. 'hsa:1956', 'C00002', 'K00844').
            target_db: Target database (e.g. 'pathway', 'disease', 'drug', 'ko',
                'compound', 'reaction', 'module', 'genes').
            max_results: Maximum number of pairs to return (capped at 100).
        """
        entry_id = validate_query(entry_id, max_len=50)
        target_db = validate_link_database(target_db)
        kegg = ctx.request_context.lifespan_context.kegg
        pairs = parse_link_response(await kegg.link(target_db, entry_id))
        limited, total, truncated = cap_list(pairs, max_results)
        return LinkResult(
            source=entry_id,
            target_db=target_db,
            pairs=limited,
            count=total,
            truncated=truncated,
        )
