---
name: kegg-analysis
description: Use when the user asks to analyze genes, pathways, compounds, drugs, or metabolic networks using KEGG. Triggers on requests like "find pathways for these genes", "what does this enzyme do", "compare metabolism across species", "drug targets", "pathway enrichment", or any bioinformatics question involving KEGG identifiers (hsa:1234, map00010, C00001, K00001, ec:1.1.1.1).
---

# KEGG Bioinformatics Analysis

Guide the user through structured KEGG database queries using the kegg MCP server tools.

## Available Tools

You have access to 34 KEGG tools via the `kegg` MCP server. Key categories:

| Category | Tools | Use for |
|----------|-------|---------|
| Pathways | `search_pathways`, `get_pathway_info`, `get_pathway_genes`, `get_pathway_compounds`, `get_pathway_reactions` | Finding and exploring metabolic/signaling pathways |
| Genes | `search_genes`, `get_gene_info`, `get_gene_orthologs` | Gene function, cross-species orthologs |
| Compounds | `search_compounds`, `get_compound_info`, `get_compound_reactions` | Metabolites, substrates, products |
| Reactions | `search_reactions`, `get_reaction_info` | Biochemical transformations |
| Enzymes | `search_enzymes`, `get_enzyme_info` | EC numbers, catalytic activity |
| Diseases | `search_diseases`, `get_disease_info` | Disease-gene-drug associations |
| Drugs | `search_drugs`, `get_drug_info`, `get_drug_interactions` | Pharmacology, DDI |
| Orthology | `search_ko_entries`, `get_ko_info` | Functional orthologs (KO) |
| Cross-DB | `batch_entry_lookup`, `convert_identifiers`, `find_related_entries` | Bulk queries, ID mapping (UniProt, NCBI, ChEBI) |
| Visualization | `render_pathway_ascii` | ASCII pathway diagrams |

## Workflow Patterns

### Pattern 1: Gene List → Pathway Enrichment

When the user provides a gene list:

1. Identify the organism code (e.g., `hsa` for human, `eco` for E. coli, `sce` for yeast)
2. For each gene, use `search_genes` with the organism to get KEGG gene IDs
3. For each gene ID, use `get_gene_info` with `detail_level="full"` to get pathway associations
4. Tally pathway frequencies across the gene list
5. For enriched pathways (appearing 2+ times), use `get_pathway_info` to describe their function
6. Summarize: which pathways are over-represented, what biological processes they reflect

### Pattern 2: Pathway Deep Dive

When the user asks about a specific pathway:

1. Use `search_pathways` to find the pathway ID if not provided
2. Use `get_pathway_info` with `detail_level="full"` for overview
3. Use `get_pathway_genes`, `get_pathway_compounds`, `get_pathway_reactions` for components
4. Use `render_pathway_ascii` to visualize topology
5. Highlight key enzymes, rate-limiting steps, and regulatory points

### Pattern 3: Cross-Species Comparison

When comparing metabolism across organisms:

1. Get the reference pathway (e.g., `map00010` for glycolysis)
2. For each organism code, use `get_pathway_info` with the organism-specific ID (e.g., `hsa00010`, `eco00010`)
3. Use `get_pathway_genes` for each organism to list genes
4. Compare: which genes are conserved vs. species-specific
5. Use `get_gene_orthologs` for genes of interest to find KO assignments

### Pattern 4: Compound/Drug Investigation

When investigating a compound or drug:

1. Use `search_compounds` or `search_drugs` to find the entry
2. Use `get_compound_info` or `get_drug_info` with `detail_level="full"`
3. Use `get_compound_reactions` to find biochemical context
4. Use `find_related_entries` to cross-link to pathways, enzymes, diseases
5. For drugs: use `get_drug_interactions` to screen DDI

### Pattern 5: ID Mapping

When the user has identifiers from other databases:

1. Use `convert_identifiers` to map between KEGG and external DBs (UniProt, NCBI GeneID, ChEBI, PubChem)
2. Use `batch_entry_lookup` for bulk retrieval (up to 50 entries)
3. Use `find_related_entries` to traverse links between KEGG databases

## KEGG Identifier Formats

| Database | Format | Example |
|----------|--------|---------|
| Pathway | `map{5digits}` or `{org}{5digits}` | `map00010`, `hsa00010` |
| Gene | `{org}:{id}` | `hsa:1956`, `eco:b0002` |
| Compound | `C{5digits}` | `C00001` (water), `C00002` (ATP) |
| Reaction | `R{5digits}` | `R00756` |
| Enzyme | `ec:{EC number}` | `ec:1.1.1.1` |
| KO | `K{5digits}` | `K00001` |
| Drug | `D{5digits}` | `D00001` |
| Disease | `H{5digits}` | `H00004` |
| Module | `M{5digits}` | `M00001` |
| Glycan | `G{5digits}` | `G00001` |

## Common Organism Codes

| Code | Organism |
|------|----------|
| `hsa` | Homo sapiens (human) |
| `mmu` | Mus musculus (mouse) |
| `eco` | Escherichia coli K-12 |
| `sce` | Saccharomyces cerevisiae (yeast) |
| `ath` | Arabidopsis thaliana |
| `dme` | Drosophila melanogaster |

Use `list_organisms` to find any organism code.

## Tips

- Start with `detail_level="summary"` (default) to keep responses concise; switch to `"full"` when the user needs complete details
- Use `batch_entry_lookup` instead of individual calls when fetching 3+ entries
- `render_pathway_ascii` in `grid` mode shows spatial relationships; `chain` mode shows linear flow
- KEGG cross-references are bidirectional — use `find_related_entries` to traverse in either direction
- When the user provides gene symbols (e.g., EGFR, TP53), search with the organism code to resolve to KEGG IDs first
