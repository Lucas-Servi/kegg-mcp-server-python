"""KGML (KEGG Markup Language) XML parser.

Part of the KEGG MCP Server by Elytron Biotech.
Parses KGML XML into lightweight dataclasses for rendering.
Uses defusedxml to prevent XXE and billion-laughs attacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import defusedxml.ElementTree as ET


@dataclass
class KGMLNode:
    """A node (gene, compound, map, group, or ortholog) in the pathway."""

    id: int
    name: str
    type: str
    label: str = ""
    x: int = 0
    y: int = 0
    width: int = 46
    height: int = 17


@dataclass
class KGMLReaction:
    """A metabolic reaction edge connecting substrates to products."""

    id: int
    name: str
    type: str
    substrate_ids: list[int] = field(default_factory=list)
    product_ids: list[int] = field(default_factory=list)


@dataclass
class KGMLRelation:
    """A signaling/regulatory edge between two entries."""

    entry1: int
    entry2: int
    type: str
    subtypes: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class KGMLPathway:
    """Parsed KGML pathway document."""

    name: str
    org: str
    number: str
    title: str
    nodes: dict[int, KGMLNode] = field(default_factory=dict)
    reactions: list[KGMLReaction] = field(default_factory=list)
    relations: list[KGMLRelation] = field(default_factory=list)


def parse_kgml(xml_text: str) -> KGMLPathway:
    """Parse KGML XML into a KGMLPathway dataclass."""
    root = ET.fromstring(xml_text)

    pathway = KGMLPathway(
        name=root.get("name", ""),
        org=root.get("org", ""),
        number=root.get("number", ""),
        title=root.get("title", ""),
    )

    # Build a map from entry name to entry id for reaction substrate/product resolution
    name_to_ids: dict[str, list[int]] = {}

    for entry_el in root.findall("entry"):
        entry_id = int(entry_el.get("id", "0"))
        entry_name = entry_el.get("name", "")
        entry_type = entry_el.get("type", "")

        graphics = entry_el.find("graphics")
        label = ""
        x = y = 0
        width, height = 46, 17
        if graphics is not None:
            label = graphics.get("name", "")
            x = int(graphics.get("x", "0"))
            y = int(graphics.get("y", "0"))
            width = int(graphics.get("width", "46"))
            height = int(graphics.get("height", "17"))

        node = KGMLNode(
            id=entry_id,
            name=entry_name,
            type=entry_type,
            label=label,
            x=x,
            y=y,
            width=width,
            height=height,
        )
        pathway.nodes[entry_id] = node

        for single_name in entry_name.split():
            name_to_ids.setdefault(single_name, []).append(entry_id)

    for rxn_el in root.findall("reaction"):
        rxn_id = int(rxn_el.get("id", "0"))
        rxn_name = rxn_el.get("name", "")
        rxn_type = rxn_el.get("type", "irreversible")

        substrate_ids: list[int] = []
        for sub in rxn_el.findall("substrate"):
            sub_id = sub.get("id")
            if sub_id is not None:
                substrate_ids.append(int(sub_id))
            else:
                sub_name = sub.get("name", "")
                substrate_ids.extend(name_to_ids.get(sub_name, []))

        product_ids: list[int] = []
        for prod in rxn_el.findall("product"):
            prod_id = prod.get("id")
            if prod_id is not None:
                product_ids.append(int(prod_id))
            else:
                prod_name = prod.get("name", "")
                product_ids.extend(name_to_ids.get(prod_name, []))

        pathway.reactions.append(
            KGMLReaction(
                id=rxn_id,
                name=rxn_name,
                type=rxn_type,
                substrate_ids=substrate_ids,
                product_ids=product_ids,
            )
        )

    for rel_el in root.findall("relation"):
        subtypes = [
            (s.get("name", ""), s.get("value", "")) for s in rel_el.findall("subtype")
        ]
        pathway.relations.append(
            KGMLRelation(
                entry1=int(rel_el.get("entry1", "0")),
                entry2=int(rel_el.get("entry2", "0")),
                type=rel_el.get("type", ""),
                subtypes=subtypes,
            )
        )

    return pathway
