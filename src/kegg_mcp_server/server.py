"""FastMCP server entry point for the KEGG MCP server."""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from mcp.server.fastmcp import FastMCP

from kegg_mcp_server.cache import TTLCache
from kegg_mcp_server.client import KEGGClient
from kegg_mcp_server.logging import setup_logging


@dataclass
class AppContext:
    kegg: KEGGClient


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    cache = TTLCache(maxsize=1024, default_ttl=300)
    async with httpx.AsyncClient(
        base_url="https://rest.kegg.jp",
        timeout=30.0,
        headers={"User-Agent": "kegg-mcp-server/0.1.0"},
    ) as http:
        yield AppContext(kegg=KEGGClient(http, cache))


mcp = FastMCP(
    "KEGG MCP Server",
    lifespan=lifespan,
    instructions=(
        "Bioinformatics server for querying the KEGG database. "
        "Provides tools for pathways, genes, compounds, reactions, enzymes, "
        "diseases, drugs, modules, orthology (KO), glycans, and BRITE hierarchies. "
        "Uses the free KEGG REST API at https://rest.kegg.jp — no API key required."
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
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
