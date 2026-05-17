# Contributing to KEGG MCP Server

Developed by **Elytron Biotech**.

## Development Setup

```bash
git clone https://github.com/Lucas-Servi/kegg-mcp-server-python.git
cd kegg-mcp-server-python
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
ruff check src/ tests/
```

## Branch Protection

This repository expects:

- All changes via pull requests (no direct pushes to `main`)
- CI must pass (ruff lint, pytest with 80% coverage, bandit SAST, pip-audit)
- At least one review approval before merge

## Security

- `bandit -r src/ -ll` runs in CI for SAST scanning
- `pip-audit --strict` checks dependencies for known CVEs
- GitHub Actions are pinned to commit SHAs to prevent tag-moving supply-chain attacks
- OIDC Trusted Publishing is used for PyPI releases (no stored tokens)

## Adding a New Tool

1. Create `src/kegg_mcp_server/tools/<your_tool>.py` with a `register(mcp: FastMCP)` function
2. Add input validation calls from `kegg_mcp_server.validators`
3. Register in `src/kegg_mcp_server/tools/__init__.py`
4. Add entry to `manifest.json`
5. Write tests in `tests/test_<your_tool>.py`
6. Maintain 80%+ coverage
