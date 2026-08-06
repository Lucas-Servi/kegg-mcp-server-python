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

## KEGG REST gotchas

Hard-won behaviours of the live API (`rest.kegg.jp`). Each was confirmed by probing, not read
off the documentation — the docs disagree with the server in every case below.

**`/list/organism` is retired and returns HTTP 400.** `list_organisms` queries `/list/genome`
instead. The row shape is **two** columns, `T-number \t code; description`
(`T01001\thsa; Homo sapiens (human)`), so the `"; "` partition is mandatory: without it the result
dict is keyed by T-number and carries the organism code inside the description string. A tolerant
3-column branch is kept as a fallback, and it is the reason a naive endpoint swap can leave the
old test green while the tool returns garbage. `/list/genome` is ~9,000 lines — the shared output
cap applies.

**`/conv` converts within ONE kind only, KEGG side ↔ outside side.** Genes (an organism code like
`hsa`, or a T-number) ↔ `ncbi-geneid` / `ncbi-proteinid` / `uniprot`; chemistry
(`compound`/`drug`/`glycan`, or the short prefixes `cpd`/`dr`/`gl`) ↔ `pubchem` / `chebi`.
Cross-kind and same-side pairs are 400.

- **Validate the PAIR, not each side.** `pathway`, `compound`, `uniprot` and `chebi` are all
  legitimate conv names, yet `pathway/hsa`, `compound/uniprot`, `hsa/chebi` and `chebi/pubchem` are
  all 400. A per-side validator lets every one of them through. See `validate_conv_pair`.
- **`kegg` is not a conv database at all** — `/conv/kegg/…` is 400 in both directions.
- **`genes` is a TARGET only, and only with entry ids.** `/conv/genes/uniprot:P00533` is 200;
  `/conv/genes/ncbi-geneid` (whole-database form) and `/conv/uniprot/genes` are both 400.
- **Every entry id must carry its own database prefix.** `/conv/uniprot/1956` is 400;
  `/conv/uniprot/hsa:1956` is 200. Bare ids are auto-prefixed from `source_db`.
- **A 200 does not imply a meaningful pair.** `/conv/pathway/ncbi-geneid:1956` returns 200 with an
  **empty body** while `/conv/pathway/hsa` is 400 — so per-entry probing cannot discover the
  vocabulary, and the accepted/rejected sets in `tests/test_validators.py` (with the observed status
  recorded per case) are the reference.
- Ordering hazard in `_classify_conv_database`: `kegg`, `compound`, `drug` and `genes` are all 3–4
  lowercase letters and match `KEGG_DATABASE_IDENTIFIER`, so the named sets must be checked
  **before** the organism-code regex or they are misread as organism codes.

**BRITE entries are an indented hierarchy, not an ENTRY/NAME flat file.** `/get/br:ko00001` is 200,
but `parse_flat_entry` yields garbage keys from it (`'a09100 metab'`, `'b  09101 car'`, …) and
`summarize_flat_entry` returns `{}` — `EntrySummary.entry` is the only field without a default, so
this surfaced as a `ValidationError` on **every valid BRITE id**. Use `parse_brite_hierarchy`.

- **Key off the leading letter, NOT indent width.** `br:br08303` emits
  `AA ALIMENTARY TRACT AND METABOLISM` — level `A`, no space before the label — which is exactly
  what an indent-width parser gets wrong.
- **Cap the output.** `/get/br:ko00001` is **4.3 MB** / 65,338 lines. Before the parser was fixed
  the error accidentally protected the caller's context window; fixing it without a cap turns a
  confusing error into a context bomb.
- **`/get` requires the `br:` prefix, and NO other endpoint emits it.** `/get/br:br08303` is 200
  while `/get/br08303` and `/get/08303` are both **404** — but `/list/brite` emits `br08901` and
  `/find/brite/<query>` strips the family prefix entirely (`08303` for `br08303`, `00001` for
  `ko00001`). So every id `search_brite` handed the model came back `not_found` on a real entry:
  a broken search→get handoff that the URL being "fine" hides. `brite_get_candidates` normalizes
  all four shapes. A **bare** digit id is unambiguous but not locally decidable (which family?), so
  both are tried in order — `/list/brite` is 97 `br#####` + 59 `ko#####` and those 156 ids have
  156 distinct digit suffixes, and a 404 costs one cached empty response. `BRITE_ID` therefore
  makes the family segment optional; keep `validate_brite_id` rejecting non-BRITE junk.

**`pydantic.ValidationError` subclasses `ValueError`.** The shared tool decorator catches
`ValueError` and maps it to `code="validation_error"` with a hint blaming the caller's identifier —
so a server-side parse bug was reported as bad user input (that is how the BRITE defect above
presented). Catch `pydantic.ValidationError` **first** and map it to a distinct non-retryable code.
Input validators must keep raising plain `ValueError`.
