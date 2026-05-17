"""Linear reaction-chain ASCII renderer for KEGG pathways.

Part of the KEGG MCP Server by Elytron Biotech.
Renders pathways as text chains: [Substrate] ──enzyme──▶ [Product]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kegg_mcp_server.ascii.kgml import KGMLPathway


def render_chain(pathway: KGMLPathway, *, max_width: int = 100) -> str:
    """Render a pathway as linear reaction chains in ASCII text."""
    lines: list[str] = []

    # Header
    title = pathway.title or pathway.name
    org_info = f" ({pathway.org})" if pathway.org else ""
    header = f"{title}{org_info}"
    lines.append(header)
    lines.append("=" * min(len(header), max_width))
    lines.append("")

    if pathway.reactions:
        _render_reactions(pathway, lines, max_width)
    elif pathway.relations:
        _render_relations(pathway, lines, max_width)
    else:
        lines.append("(No reactions or relations found in this pathway)")

    return "\n".join(lines)


def _get_label(pathway: KGMLPathway, node_id: int) -> str:
    """Get a short display label for a node."""
    node = pathway.nodes.get(node_id)
    if not node:
        return f"#{node_id}"
    label = node.label or node.name
    # Take first name if comma-separated
    if "," in label:
        label = label.split(",")[0].strip()
    # Remove prefix like "cpd:" or "hsa:"
    if ":" in label and len(label.split(":")[0]) <= 4:
        label = label.split(":", 1)[1]
    # Truncate long labels
    if len(label) > 16:
        label = label[:14] + ".."
    return label


def _get_reaction_label(rxn_name: str) -> str:
    """Extract short reaction ID from name like 'rn:R00756'."""
    if " " in rxn_name:
        rxn_name = rxn_name.split()[0]
    if ":" in rxn_name:
        rxn_name = rxn_name.split(":", 1)[1]
    return rxn_name


def _render_reactions(pathway: KGMLPathway, lines: list[str], max_width: int) -> None:
    """Render metabolic reactions as chains."""
    # Build directed graph: substrate_id -> [(reaction_label, product_id, reversible)]
    graph: dict[int, list[tuple[str, int, bool]]] = {}
    all_products: set[int] = set()
    all_substrates: set[int] = set()

    for rxn in pathway.reactions:
        rxn_label = _get_reaction_label(rxn.name)
        reversible = rxn.type == "reversible"
        for sub_id in rxn.substrate_ids:
            all_substrates.add(sub_id)
            for prod_id in rxn.product_ids:
                all_products.add(prod_id)
                graph.setdefault(sub_id, []).append((rxn_label, prod_id, reversible))
                if reversible:
                    graph.setdefault(prod_id, []).append((rxn_label, sub_id, True))

    # Find source nodes (substrates not appearing as products, or all if cyclic)
    sources = all_substrates - all_products
    if not sources:
        sources = all_substrates

    # Walk chains from each source using DFS
    visited_edges: set[tuple[int, int]] = set()
    chains: list[list[str]] = []

    for source in sorted(sources):
        chain_parts: list[str] = []
        current = source
        while current is not None:
            chain_parts.append(f"[{_get_label(pathway, current)}]")
            edges = graph.get(current, [])
            next_node = None
            for rxn_label, prod_id, reversible in edges:
                if (current, prod_id) not in visited_edges:
                    visited_edges.add((current, prod_id))
                    arrow = " <>" if reversible else " ──"
                    chain_parts.append(f"{arrow}{rxn_label}──▶ ")
                    next_node = prod_id
                    break
            current = next_node

        if chain_parts:
            chains.append(chain_parts)

    # Render chains with wrapping
    for i, chain_parts in enumerate(chains):
        if i > 0:
            lines.append("")
        full_chain = "".join(chain_parts)
        _wrap_chain(full_chain, lines, max_width)

    # Branches: edges not visited
    branch_lines: list[str] = []
    for node_id, edges in sorted(graph.items()):
        for rxn_label, prod_id, reversible in edges:
            if (node_id, prod_id) not in visited_edges:
                visited_edges.add((node_id, prod_id))
                src = _get_label(pathway, node_id)
                dst = _get_label(pathway, prod_id)
                arrow = "<=>" if reversible else "-->"
                branch_lines.append(f"  [{src}] {arrow} {rxn_label} {arrow} [{dst}]")

    if branch_lines:
        lines.append("")
        lines.append("Branches:")
        lines.extend(branch_lines)


def _render_relations(pathway: KGMLPathway, lines: list[str], max_width: int) -> None:
    """Render signaling/regulatory relations as chains."""
    # Build graph from relations
    graph: dict[int, list[tuple[str, int]]] = {}
    targets: set[int] = set()

    for rel in pathway.relations:
        subtype_str = ""
        if rel.subtypes:
            subtype_str = rel.subtypes[0][0]
        label = f"{rel.type}:{subtype_str}" if subtype_str else rel.type
        graph.setdefault(rel.entry1, []).append((label, rel.entry2))
        targets.add(rel.entry2)

    # Find source nodes
    sources = set(graph.keys()) - targets
    if not sources:
        sources = set(graph.keys())

    visited: set[tuple[int, int]] = set()

    for source in sorted(sources):
        chain_parts: list[str] = []
        current = source
        while current is not None:
            chain_parts.append(f"[{_get_label(pathway, current)}]")
            edges = graph.get(current, [])
            next_node = None
            for label, target in edges:
                if (current, target) not in visited:
                    visited.add((current, target))
                    chain_parts.append(f" ──{label}──▶ ")
                    next_node = target
                    break
            current = next_node

        if chain_parts:
            full_chain = "".join(chain_parts)
            _wrap_chain(full_chain, lines, max_width)
            lines.append("")


def _wrap_chain(text: str, lines: list[str], max_width: int) -> None:
    """Wrap a chain string at max_width, breaking at arrow boundaries."""
    if len(text) <= max_width:
        lines.append(text)
        return

    # Break at ──▶ boundaries
    segments: list[str] = []
    current = ""
    i = 0
    while i < len(text):
        current += text[i]
        if text[i] == "▶" and text[i - 1 : i + 1] == "─▶":
            if len(current) >= max_width * 0.6:
                segments.append(current)
                current = "  └─"
        i += 1
    if current and current != "  └─":
        segments.append(current)

    lines.extend(segments)
