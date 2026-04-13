"""MCP prompts for guided bioinformatics workflows using KEGG tools."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:

    @mcp.prompt()
    def pathway_enrichment_analysis(
        gene_list: str,
        organism: str = "hsa",
    ) -> str:
        """Guided KEGG pathway enrichment analysis for a list of genes.

        Walk through mapping a gene list to KEGG IDs, aggregating pathway
        associations, and identifying over-represented pathways.

        Args:
            gene_list: Comma- or newline-separated gene symbols or IDs
                (e.g. 'EGFR, TP53, BRCA1' or Entrez IDs).
            organism: KEGG organism code (default 'hsa' for human).
        """
        return (
            f"I have a list of genes from a differential expression experiment "
            f"in organism '{organism}'. The genes are:\n\n{gene_list}\n\n"
            f"Please perform a KEGG pathway enrichment analysis:\n"
            f"1. Use `search_genes` to find each gene's KEGG ID in organism '{organism}'\n"
            f"2. For each gene found, use `get_gene_info` to retrieve its associated pathways\n"
            f"3. Tally pathway frequencies across all genes\n"
            f"4. Use `get_pathway_info` on the top 5 most frequent pathways to describe their "
            f"biological function\n"
            f"5. Summarize which pathways are enriched, how many genes from the list participate, "
            f"and what this means biologically"
        )

    @mcp.prompt()
    def drug_target_investigation(
        drug_name: str,
    ) -> str:
        """Comprehensive investigation of a drug's targets, pathways, and interactions.

        Guides the analysis from drug identification through target mapping,
        pathway involvement, and drug-drug interaction screening.

        Args:
            drug_name: Drug name or synonym (e.g. 'imatinib', 'aspirin', 'metformin').
        """
        return (
            f"Investigate the drug '{drug_name}' using KEGG:\n\n"
            f"1. Use `search_drugs` to find the KEGG drug entry for '{drug_name}'\n"
            f"2. Use `get_drug_info` on the drug ID to retrieve targets, formula, "
            f"and classification\n"
            f"3. For each gene target listed, use `get_gene_info` to understand the target "
            f"protein's function\n"
            f"4. Use `find_related_entries` to map the drug to associated pathways and diseases\n"
            f"5. Use `get_drug_interactions` on the drug ID to check for known drug-drug "
            f"interactions\n"
            f"6. Provide a comprehensive summary covering: mechanism of action, primary targets, "
            f"affected pathways, relevant diseases, and key interaction risks"
        )

    @mcp.prompt()
    def metabolic_pathway_comparison(
        pathway_id: str,
        organisms: str = "hsa,mmu,eco",
    ) -> str:
        """Cross-species comparison of a metabolic pathway.

        Compares gene content, reactions, and compounds across multiple organisms
        to reveal conserved and species-specific elements.

        Args:
            pathway_id: Reference KEGG pathway ID (e.g. 'map00010' for glycolysis,
                'map00020' for TCA cycle).
            organisms: Comma-separated KEGG organism codes to compare
                (default: 'hsa,mmu,eco' for human, mouse, E. coli).
        """
        org_list = [o.strip() for o in organisms.split(",")]
        org_str = ", ".join(org_list)
        numeric_id = re.sub(r"^[a-z]+", "", pathway_id)

        return (
            f"Compare the metabolic pathway {pathway_id} across these organisms: {org_str}\n\n"
            + "".join(
                f"{i + 1}. Use `get_pathway_info` for {org}{numeric_id} "
                f"to get genes and compounds in {org}\n"
                for i, org in enumerate(org_list)
            )
            + f"{len(org_list) + 1}. Use `get_pathway_genes` and `get_pathway_compounds` "
            f"for each organism-specific pathway\n"
            f"{len(org_list) + 2}. Identify genes/compounds conserved across all organisms "
            f"vs. those unique to specific species\n"
            f"{len(org_list) + 3}. For conserved enzymes, use `get_ko_info` on shared KO entries "
            f"to confirm functional equivalence\n"
            f"{len(org_list) + 4}. Summarize evolutionary conservation, species-specific "
            f"adaptations, and functional implications of differences"
        )
