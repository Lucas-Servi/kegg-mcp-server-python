# kegg-mcp-server

A Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for the [KEGG](https://www.kegg.jp) bioinformatics database. Exposes 33 tools, 8 resource templates, and 3 guided bioinformatics prompts to any MCP-compatible LLM client (Claude, etc.).

[![PyPI](https://img.shields.io/pypi/v/kegg-mcp-server)](https://pypi.org/project/kegg-mcp-server/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/elytron-biotech/kegg-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/elytron-biotech/kegg-mcp-server/actions)

---

## Quick Start

### With uvx (no install needed)

```bash
uvx kegg-mcp-server
```

### With pip

```bash
pip install kegg-mcp-server
kegg-mcp-server
```

---

## Claude Desktop Setup

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

Config file locations:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

---

## Features

- **33 MCP tools** across 13 KEGG database categories
- **8 resource templates** for direct URI-based entity access
- **3 guided prompts** for common bioinformatics workflows
- **Structured Pydantic output** — tools return typed JSON, not raw text
- **Batch support** — fetch up to 50 entries at once (auto-chunked to respect KEGG's 10-entry limit)
- **TTL caching** — repeated queries served from memory (5-minute default TTL)
- **No API key required** — uses the free KEGG REST API at `https://rest.kegg.jp`

---

## Tool Reference

### Database
| Tool | Description |
|------|-------------|
| `get_database_info` | Release info and statistics for any KEGG database |
| `list_organisms` | All organisms available in KEGG (~26,000+) |

### Pathways
| Tool | Description |
|------|-------------|
| `search_pathways` | Search pathways by keyword and organism |
| `get_pathway_info` | Full pathway details including genes, compounds, reactions |
| `get_pathway_genes` | All genes in a pathway |
| `get_pathway_compounds` | All metabolites in a pathway |
| `get_pathway_reactions` | All reactions in a pathway |

### Genes
| Tool | Description |
|------|-------------|
| `search_genes` | Search genes in any organism |
| `get_gene_info` | Gene details, orthologs, sequences |
| `get_gene_orthologs` | Cross-species orthologs via KO entries |

### Compounds
| Tool | Description |
|------|-------------|
| `search_compounds` | Search by name, formula, or mass |
| `get_compound_info` | Compound details, reactions, pathways |
| `get_compound_reactions` | All reactions involving a compound |

### Reactions
| Tool | Description |
|------|-------------|
| `search_reactions` | Search reactions by keyword |
| `get_reaction_info` | Reaction equation, enzymes, pathways |

### Enzymes
| Tool | Description |
|------|-------------|
| `search_enzymes` | Search by EC number or name |
| `get_enzyme_info` | Enzyme details, substrates, genes |

### Diseases
| Tool | Description |
|------|-------------|
| `search_diseases` | Search KEGG disease database |
| `get_disease_info` | Disease genes, drugs, pathways |

### Drugs
| Tool | Description |
|------|-------------|
| `search_drugs` | Search drugs by name, formula, or mass |
| `get_drug_info` | Drug targets, classification, interactions |
| `get_drug_interactions` | Drug-drug interaction screening |

### Modules
| Tool | Description |
|------|-------------|
| `search_modules` | Search KEGG functional modules |
| `get_module_info` | Module definition, reactions, orthology |

### Orthology (KO)
| Tool | Description |
|------|-------------|
| `search_ko_entries` | Search KEGG Orthology entries |
| `get_ko_info` | KO entry details, genes, pathways |

### Glycans
| Tool | Description |
|------|-------------|
| `search_glycans` | Search glycan database |
| `get_glycan_info` | Glycan composition and reactions |

### BRITE Hierarchies
| Tool | Description |
|------|-------------|
| `search_brite` | Search BRITE functional hierarchies |
| `get_brite_info` | Hierarchy content and structure |

### Cross-Database
| Tool | Description |
|------|-------------|
| `batch_entry_lookup` | Fetch up to 50 entries in bulk |
| `convert_identifiers` | Map between KEGG and external IDs (UniProt, NCBI, ChEBI, PubChem) |
| `find_related_entries` | Find cross-database relationships for any entry |

---

## Resource Templates

Direct URI access to KEGG entities:

| URI | Description |
|-----|-------------|
| `kegg://pathway/{pathway_id}` | Pathway entry (e.g. `kegg://pathway/hsa00010`) |
| `kegg://gene/{gene_id}` | Gene entry (e.g. `kegg://gene/hsa:1956`) |
| `kegg://compound/{compound_id}` | Compound entry (e.g. `kegg://compound/C00002`) |
| `kegg://reaction/{reaction_id}` | Reaction entry (e.g. `kegg://reaction/R00756`) |
| `kegg://disease/{disease_id}` | Disease entry (e.g. `kegg://disease/H00004`) |
| `kegg://drug/{drug_id}` | Drug entry (e.g. `kegg://drug/D00001`) |
| `kegg://organism/{org_code}` | Pathway list for an organism (e.g. `kegg://organism/hsa`) |
| `kegg://search/{database}/{query}` | Search any database (e.g. `kegg://search/compound/glucose`) |

---

## Prompts

Three guided workflows for common bioinformatics analyses:

| Prompt | Arguments | Description |
|--------|-----------|-------------|
| `pathway_enrichment_analysis` | `gene_list`, `organism` | Map gene list → KEGG IDs → pathways → enrichment summary |
| `drug_target_investigation` | `drug_name` | Drug → targets → pathways → interaction screening |
| `metabolic_pathway_comparison` | `pathway_id`, `organisms` | Compare pathway gene/compound content across species |

---

## Configuration

### Transport

```bash
# stdio (default, for Claude Desktop / uvx)
kegg-mcp-server

# Streamable HTTP (for web/API deployment)
kegg-mcp-server --transport streamable-http --host 0.0.0.0 --port 8080

# python -m also works
python -m kegg_mcp_server --transport stdio
```

---

## Development

```bash
git clone https://github.com/elytron-biotech/kegg-mcp-server
cd kegg-mcp-server
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Debug with MCP Inspector
mcp dev kegg-mcp-server
```

### Architecture

```
src/kegg_mcp_server/
├── server.py          # FastMCP instance, lifespan (httpx client + TTL cache), CLI
├── client.py          # KEGGClient: async wrapper for all 7 KEGG REST operations
├── cache.py           # TTLCache backed by cachetools
├── parsers.py         # KEGG flat-file and tab-delimited response parsers
├── resources.py       # 8 MCP resource templates
├── prompts.py         # 3 bioinformatics workflow prompts
├── models/            # Pydantic models for all KEGG entity types
└── tools/             # 13 tool modules, each with a register(mcp) function
```

---

## Acknowledgments

- [KEGG](https://www.kegg.jp) — Kyoto Encyclopedia of Genes and Genomes
- [Model Context Protocol](https://modelcontextprotocol.io) — Anthropic's open protocol for LLM tool use
- [FastMCP](https://github.com/jlowin/fastmcp) — Python MCP SDK

---

## License

MIT — see [LICENSE](LICENSE).
