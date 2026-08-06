from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.brite import BriteHierarchy
from kegg_mcp_server.models.common import SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import parse_brite_hierarchy, parse_tab_list
from kegg_mcp_server.tools._common import (
    READ_ONLY,
    build_search_result,
    kegg_tool,
    not_found_result,
)
from kegg_mcp_server.validators import (
    brite_get_candidates,
    validate_brite_id,
    validate_query,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

#: Cap on ``detail_level="full"`` raw text, ~4 chars/token → ~15K tokens. Sized
#: to stay well inside a single tool response without needing the caller to trim.
_RAW_CONTENT_MAX_CHARS = 60_000

_RAW_TRUNCATION_NOTICE = (
    "\n\n[... BRITE hierarchy truncated. Use the level_counts/labels summary to "
    "navigate, then query the specific entries (e.g. get_ko_info, get_drug_info) "
    "you need. ...]"
)


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_brite(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG BRITE functional hierarchy databases.

        Args:
            query: Hierarchy name (e.g. 'KEGG pathway', 'transporter', 'ribosome').
            max_results: Maximum number of results to return (capped at 100).
        """
        query = validate_query(query)
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("brite", query))
        return build_search_result(query, "brite", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_brite_info(
        brite_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> BriteHierarchy | ErrorResult:
        """Get the structure of a KEGG BRITE functional hierarchy.

        BRITE entries are large A/B/C/D trees, not flat-file entries, so the
        result is a bounded summary: the level line counts, the leaf column
        names, and the labels of the top two levels.

        Args:
            brite_id: KEGG BRITE hierarchy ID. Any form KEGG hands out works —
                'br:ko00001' (canonical), 'ko00001' / 'br08303' (as listed by
                list_databases), or the bare '00001' / '08303' returned by
                search_brite.
            detail_level: 'summary' (default) or 'full' (adds raw_content, the
                raw hierarchy text — TRUNCATED, since the largest hierarchies are
                several megabytes).
        """
        brite_id = validate_brite_id(brite_id)
        kegg = ctx.request_context.lifespan_context.kegg

        # `/get` needs the `br:` prefix, which neither `/list/brite` nor
        # `/find/brite` puts on the ids they hand the caller. A bare digit id is
        # unambiguous but not locally decidable, so try each family in turn.
        candidates = brite_get_candidates(brite_id)
        raw, resolved = "", candidates[0]
        for candidate in candidates:
            raw = await kegg.get(candidate)
            if raw.strip():
                resolved = candidate
                break
        if not raw.strip():
            return not_found_result(
                "BRITE entry", brite_id, path_identifier=candidates[0]
            )

        parsed = parse_brite_hierarchy(raw)
        hierarchy = BriteHierarchy(entry=resolved, detail_level=detail_level, **parsed)
        if detail_level != "full":
            return hierarchy

        # The cap is NOT optional. /get/br:ko00001 is 4.3 MB and
        # /get/br:hsa00001 is 6.8 MB; before this tool was fixed it errored out,
        # which accidentally protected the caller's context window. Returning the
        # raw text now would trade a confusing error for a context bomb.
        if len(raw) > _RAW_CONTENT_MAX_CHARS:
            hierarchy.raw_content = raw[:_RAW_CONTENT_MAX_CHARS] + _RAW_TRUNCATION_NOTICE
            hierarchy.raw_truncated = True
        else:
            hierarchy.raw_content = raw
        return hierarchy
