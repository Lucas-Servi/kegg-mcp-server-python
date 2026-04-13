"""Pydantic models for KEGG database entities."""

from kegg_mcp_server.models.brite import BriteInfo
from kegg_mcp_server.models.common import (
    BatchLookupResult,
    ConversionResult,
    LinkResult,
    ListResult,
    Reference,
    SearchResult,
)
from kegg_mcp_server.models.compound import CompoundInfo
from kegg_mcp_server.models.disease import DiseaseInfo
from kegg_mcp_server.models.drug import DrugInfo, DrugInteraction, DrugInteractionResult
from kegg_mcp_server.models.enzyme import EnzymeInfo
from kegg_mcp_server.models.gene import GeneInfo
from kegg_mcp_server.models.glycan import GlycanInfo
from kegg_mcp_server.models.module import ModuleInfo
from kegg_mcp_server.models.organism import DatabaseInfo, OrganismInfo
from kegg_mcp_server.models.orthology import KOInfo
from kegg_mcp_server.models.pathway import PathwayInfo, PathwayLinks
from kegg_mcp_server.models.reaction import ReactionInfo

__all__ = [
    "BatchLookupResult",
    "BriteInfo",
    "CompoundInfo",
    "ConversionResult",
    "DatabaseInfo",
    "DiseaseInfo",
    "DrugInfo",
    "DrugInteraction",
    "DrugInteractionResult",
    "EnzymeInfo",
    "GeneInfo",
    "GlycanInfo",
    "KOInfo",
    "LinkResult",
    "ListResult",
    "ModuleInfo",
    "OrganismInfo",
    "PathwayInfo",
    "PathwayLinks",
    "ReactionInfo",
    "Reference",
    "SearchResult",
]
