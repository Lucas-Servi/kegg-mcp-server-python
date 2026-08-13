"""Entry point for the KEGG MCP server.

Built on ``MCPServer`` from ``mcp>=2`` (protocol 2026-07-28). An mcp 2.x server
also answers every earlier protocol revision from the same app, so clients still
on the 1.x SDK connect unchanged.
"""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from mcp.server.mcpserver import MCPServer

from kegg_mcp_server import __version__
from kegg_mcp_server.cache import TTLCache
from kegg_mcp_server.client import KEGGClient
from kegg_mcp_server.logging import setup_logging


@dataclass
class AppContext:
    kegg: KEGGClient


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    cache = TTLCache(maxsize=1024, default_ttl=300)
    async with httpx.AsyncClient(
        base_url="https://rest.kegg.jp",
        timeout=30.0,
        follow_redirects=False,
        headers={"User-Agent": f"kegg-mcp-server/{__version__}"},
    ) as http:
        yield AppContext(kegg=KEGGClient(http, cache))


mcp = MCPServer(
    "KEGG MCP Server",
    lifespan=lifespan,
    instructions=(
        "Bioinformatics server for querying the KEGG database. "
        "Provides tools for pathways, genes, compounds, reactions, enzymes, "
        "diseases, drugs, modules, orthology (KO), glycans, and BRITE hierarchies. "
        "Uses the unauthenticated KEGG REST API at https://rest.kegg.jp. "
        "KEGG limits API use to academic users; review its non-academic-use guidance."
    ),
)

# Register tools, resources, and prompts after mcp is created to avoid circular imports
from kegg_mcp_server.prompts import register_prompts  # noqa: E402
from kegg_mcp_server.resources import register_resources  # noqa: E402
from kegg_mcp_server.tools import register_all_tools  # noqa: E402

register_all_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KEGG MCP Server — expose KEGG bioinformatics data via MCP"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport to use (default: stdio for Claude Desktop / uvx)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for streamable-http transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for streamable-http transport (default: 8080)",
    )
    args = parser.parse_args()

    setup_logging()

    if args.transport == "streamable-http":
        # mcp 2.x moved transport settings off the constructor and off `Settings`:
        # `MCPServer(port=…)` is a TypeError and `mcp.settings.host` no longer exists.
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")
