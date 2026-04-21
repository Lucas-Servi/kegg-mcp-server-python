# kegg-mcp-server-python

[![PyPI](https://img.shields.io/pypi/v/kegg-mcp-server)](https://pypi.org/project/kegg-mcp-server/)
[![Python 3.11–3.14](https://img.shields.io/badge/python-3.11--3.14-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Lucas-Servi/kegg-mcp-server-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Lucas-Servi/kegg-mcp-server-python/actions)

An unofficial Python [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for the [KEGG](https://www.kegg.jp) bioinformatics database. It exposes **33 tools**, **8 resource templates**, and **3 guided prompts** to any MCP-compatible client (Claude Desktop, Claude Code, Cursor, etc.).

Built with [FastMCP](https://github.com/jlowin/fastmcp), returns **structured Pydantic JSON** (not raw text), and includes per-operation TTL caching, request retry with exponential backoff, KEGG-friendly concurrency limits, structured JSON stderr logging, and batch helpers out of the box. No API key required -- uses the free KEGG REST API.

Responses are token-aware by default: `get_*_info` tools return a compact `EntrySummary` (entry id, name, class, description, counts of linked entities) unless you pass `detail_level="full"`. Errors are returned as a typed `ErrorResult` the model can reason about, not raised as exceptions.

> **Note:** This is a community non-official project and is not affiliated with or endorsed by KEGG or Kanehisa Laboratories.

---

## Quick start

### With `uvx` (no install)

```bash
uvx kegg-mcp-server
```

### With pip

```bash
pip install kegg-mcp-server
kegg-mcp-server
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kegg": {
      "command": "uvx",
      "args": ["kegg-mcp-server"]
    }
  }
}
```

<details>
<summary>Config file locations</summary>

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

</details>

### Claude Code

```bash
claude mcp add kegg-mcp-server -- uvx kegg-mcp-server
```

### MCPB bundle (Claude Desktop, no Python required)

Download the latest `.mcpb` from the [releases page](https://github.com/Lucas-Servi/kegg-mcp-server-python/releases) and drag it onto Claude Desktop. The bundle vendors all Python dependencies and runs with Claude Desktop's embedded Python.

---

## What's included

### 33 Tools

| Category | Tools | Examples |
|----------|-------|---------|
| **Database** | `get_database_info`, `list_organisms` | Get KEGG release stats, list all ~26k organisms |
| **Pathways** | `search_pathways`, `get_pathway_info`, `get_pathway_genes`, `get_pathway_compounds`, `get_pathway_reactions` | Search by keyword, get full pathway details |
| **Genes** | `search_genes`, `get_gene_info`, `get_gene_orthologs` | Find genes in any organism, cross-species orthologs |
| **Compounds** | `search_compounds`, `get_compound_info`, `get_compound_reactions` | Search by name/formula/mass, find reactions |
| **Reactions** | `search_reactions`, `get_reaction_info` | Equation, enzymes, pathways for any reaction |
| **Enzymes** | `search_enzymes`, `get_enzyme_info` | EC number lookup, substrates, genes |
| **Diseases** | `search_diseases`, `get_disease_info` | Disease genes, drugs, pathways |
| **Drugs** | `search_drugs`, `get_drug_info`, `get_drug_interactions` | Drug targets, DDI screening |
| **Modules** | `search_modules`, `get_module_info` | Functional module definitions |
| **Orthology** | `search_ko_entries`, `get_ko_info` | KEGG Orthology entries |
| **Glycans** | `search_glycans`, `get_glycan_info` | Glycan composition, reactions |
| **BRITE** | `search_brite`, `get_brite_info` | Functional hierarchies |
| **Cross-database** | `batch_entry_lookup`, `convert_identifiers`, `find_related_entries` | Bulk fetch (up to 50), ID mapping (UniProt, NCBI, ChEBI, PubChem) |

### 8 Resource Templates

Direct URI-based access to KEGG entities:

```
kegg://pathway/{pathway_id}      e.g. kegg://pathway/hsa00010
kegg://gene/{gene_id}            e.g. kegg://gene/hsa:1956
kegg://compound/{compound_id}    e.g. kegg://compound/C00002
kegg://reaction/{reaction_id}    e.g. kegg://reaction/R00756
kegg://disease/{disease_id}      e.g. kegg://disease/H00004
kegg://drug/{drug_id}            e.g. kegg://drug/D00001
kegg://organism/{org_code}       e.g. kegg://organism/hsa
kegg://search/{database}/{query} e.g. kegg://search/compound/glucose
```

### 3 Guided Prompts

| Prompt | Arguments | What it does |
|--------|-----------|--------------|
| `pathway_enrichment_analysis` | `gene_list`, `organism` | Maps a gene list to KEGG IDs, aggregates pathway associations, identifies enriched pathways |
| `drug_target_investigation` | `drug_name` | Drug lookup, target identification, pathway mapping, DDI screening |
| `metabolic_pathway_comparison` | `pathway_id`, `organisms` | Compares gene/compound content of a pathway across species |

---

## Transport options

```bash
# stdio (default -- for Claude Desktop, Claude Code, uvx)
kegg-mcp-server

# Streamable HTTP (for web/API deployment)
kegg-mcp-server --transport streamable-http --host 0.0.0.0 --port 8080

# python -m also works
python -m kegg_mcp_server
```

---

## Development

```bash
git clone https://github.com/Lucas-Servi/kegg-mcp-server-python
cd kegg-mcp-server-python
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Debug with MCP Inspector
mcp dev kegg-mcp-server
```

### Project structure

```
src/kegg_mcp_server/
  server.py       FastMCP instance, lifespan (httpx client + TTL cache), CLI
  client.py       KEGGClient: async KEGG REST with retry/backoff + KEGG-politeness semaphore
  cache.py        Per-op TTL cache (info 24h, list 1h, entry ops 5min)
  parsers.py      KEGG flat-file and tab-delimited response parsers + summarize_flat_entry
  errors.py       KEGGAPIError exception type
  logging.py      JSON stderr logger (stdout is reserved for MCP stdio framing)
  resources.py    8 MCP resource templates
  prompts.py      3 bioinformatics workflow prompts
  models/         Pydantic models for all KEGG entity types + EntrySummary + ErrorResult
  tools/          13 tool modules, each with a register(mcp) function; _common.py has the
                  @kegg_tool error-boundary decorator and shared READ_ONLY annotations
```

---

## Author

Developed by **Lucas Servi** (lucasservi@gmail.com) at [Elytron Biotech](https://elytron.bio) using [Claude Code](https://claude.ai/code).

## Acknowledgments

- Based on [Augmented-Nature/KEGG-MCP-Server](https://github.com/Augmented-Nature/KEGG-MCP-Server) -- the original TypeScript implementation that served as the foundation for this Python rewrite
- [KEGG](https://www.kegg.jp) -- Kyoto Encyclopedia of Genes and Genomes (Kanehisa Laboratories)
- [Model Context Protocol](https://modelcontextprotocol.io) -- Anthropic's open protocol for LLM tool use

## License

MIT -- see [LICENSE](LICENSE).
