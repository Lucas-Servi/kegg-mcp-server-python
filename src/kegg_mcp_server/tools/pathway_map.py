"""MCP tool drawing a KEGG pathway as a PNG with highlighted KO/EC groups.

Part of the KEGG MCP Server by Elytron Biotech.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Annotated

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, ImageContent, TextContent

from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.pathway_map import PathwayMapSummary
from kegg_mcp_server.pathway_map import PathwayMapError, build_pathway_map
from kegg_mcp_server.tools._common import READ_ONLY, kegg_tool

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def register(mcp: MCPServer) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def draw_pathway_map(
        pathway_id: str,
        highlight: dict[str, list[str]] | None = None,
        ctx: Context = None,
    ) -> Annotated[CallToolResult, PathwayMapSummary]:
        """Draw a KEGG pathway map as a PNG image, with gene boxes coloured by group.

        The map is redrawn from KEGG's KGML layout (gene boxes, compounds, reactions and
        links to other maps), not copied from KEGG's image. Each gene box is split into one
        stripe per highlight group: coloured when the group has one of the box's KOs, grey
        when it doesn't. Returns the PNG plus an exact summary of what the image shows
        (per group: map KOs found and boxes coloured; per box: KOs and the groups that
        have them), so check the summary rather than describing the picture from memory.

        Args:
            pathway_id: KEGG map number: 'map00010', 'ko00010', an organism map such as
                'eco00010' (drawn as the KO reference map), or '00010'. Global and overview
                maps (011xx, 012xx) are refused.
            highlight: Optional {label: ids}, at most 8 groups (e.g. one per genome). Ids
                are KO ids ('K00844', 'ko:K00844', 'KEGG:K00844') or complete EC numbers
                ('2.7.1.1', 'EC:2.7.1.1'). One item may hold one gene's ids separated by
                spaces ('K00845 EC:2.7.1.2', or a GenBank db_xref string). A KO with no
                KO match is coloured through EC numbers only when one item carries every EC
                KEGG links to it; those KOs are listed under matched_by_ec.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        try:
            result = await build_pathway_map(kegg, pathway_id, highlight)
        except PathwayMapError as exc:
            raise ToolError(
                ErrorResult(
                    error=str(exc), code=exc.code, retryable=False, hint=exc.hint or None
                ).model_dump_json()
            ) from exc
        summary = result.summary
        return CallToolResult(
            content=[
                TextContent(type="text", text=summary.model_dump_json()),
                ImageContent(
                    type="image",
                    data=base64.b64encode(result.png).decode("ascii"),
                    mime_type="image/png",
                ),
            ],
            structured_content=summary.model_dump(mode="json"),
        )
