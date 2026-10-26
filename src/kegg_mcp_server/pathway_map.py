"""Build a drawn pathway map with highlight groups: the library API behind ``draw_pathway_map``.

Part of the KEGG MCP Server by Elytron Biotech.

A caller passes a KEGG map id and, optionally, groups of KO or EC ids (one group per
genome, say). The map is drawn from the KO reference KGML, every gene box striped by
which groups have one of its KOs, and the result comes with an exact summary of what the
image shows, so an agent can check it without looking at the pixels.

EC ids reach a box through KEGG's KO→EC links for the map's own KOs (a bounded number
of requests per map, cached), never through a lookup per caller-supplied EC. One item of
a group may hold one gene's ids together (``"K00845 EC:2.7.1.2"``, a GenBank db_xref
string as is): a KO matches through EC numbers only when ONE item carries every EC
KEGG links to that KO, so a bifunctional KO (K13810, EC 2.2.1.2 + 5.3.1.9) is not lit by
a transaldolase and a separate glucose-6-phosphate isomerase.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kegg_mcp_server.ascii.kgml import parse_kgml
from kegg_mcp_server.drawing import MAX_GROUPS, PALETTE, draw_pathway
from kegg_mcp_server.models.pathway_map import MapBox, MapGroup, MapStep, PathwayMapSummary
from kegg_mcp_server.parsers import parse_link_response, parse_tab_list

if TYPE_CHECKING:
    from kegg_mcp_server.client import KEGGClient

_MAP_ID = re.compile(r"^(?:path:)?(?:[a-z]{2,4}|map)?(\d{5})$")
# Global and overview maps (01100 metabolic pathways, 012xx overviews) are drawn by
# KEGG with thousands of line segments, not boxes: nothing readable comes out of them.
_GLOBAL = re.compile(r"^01[12]\d\d$")
_KO = re.compile(r"^(?:ko:|kegg:)?(K\d{5})$", re.I)
_EC = re.compile(r"^(?:ec:)?(\d+\.\d+\.\d+\.\d+)$", re.I)
_CHUNK = 100
MAX_LABEL = 40
MAX_IDS_PER_GROUP = 20_000
MAX_BOXES_LISTED = 200
MAX_STEPS_LISTED = 150
ATTRIBUTION = (
    "Pathway layout and data: KEGG (Kanehisa Laboratories), www.kegg.jp. Redrawn from KGML."
)


class PathwayMapError(ValueError):
    """The request can't produce a map: ``code`` says why (stable, machine-readable)."""

    def __init__(self, message: str, code: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


@dataclass
class PathwayMap:
    png: bytes
    summary: PathwayMapSummary


def normalize_map_id(pathway_id: str) -> str:
    """``map00010``, ``ko00010``, ``eco00010``, ``path:hsa00010`` or ``00010`` → ``ko00010``."""
    match = _MAP_ID.match((pathway_id or "").strip().lower())
    if not match:
        raise PathwayMapError(
            f"Invalid pathway ID: {pathway_id!r}",
            "validation_error",
            "Pass a KEGG map number such as 'map00010', 'ko00010' or '00010'.",
        )
    number = match.group(1)
    if _GLOBAL.match(number):
        raise PathwayMapError(
            f"Map {number} is a global/overview map and can't be drawn readably",
            "global_map",
            "Choose a specific pathway, e.g. 'map00010' (glycolysis); search_pathways finds one.",
        )
    return f"ko{number}"


def split_ids(ids: Sequence[str]) -> tuple[set[str], list[frozenset[str]], list[str]]:
    """KO ids, each item's EC numbers (one set per item, i.e. per gene) and the tokens that
    are neither (``EC:1.1.1.-`` included). An item may hold several ids separated by
    spaces or commas; other cross-references in it (``GO:…``) are ignored, not reported."""
    kos: set[str] = set()
    ec_sets: list[frozenset[str]] = []
    unrecognized: list[str] = []
    for raw in ids:
        tokens = [t for t in re.split(r"[\s,]+", str(raw)) if t]
        item_ecs: set[str] = set()
        for token in tokens:
            if ko := _KO.match(token):
                kos.add(ko.group(1).upper())
            elif ec := _EC.match(token):
                item_ecs.add(ec.group(1))
            elif len(tokens) == 1:
                unrecognized.append(token)
        if item_ecs:
            ec_sets.append(frozenset(item_ecs))
    return kos, ec_sets, unrecognized


def _box_kos(name: str) -> list[str]:
    return [part[3:] for part in name.split() if part.startswith("ko:")]


def _first_name(description: str) -> str:
    """``'HK; hexokinase [EC:2.7.1.1]'`` → ``'HK'``; ``'E2.7.1.1, glk; …'`` → ``'E2.7.1.1'``."""
    return description.split(";", 1)[0].split(",", 1)[0].strip()


async def _list_names(kegg: KEGGClient, ids: list[str]) -> dict[str, str]:
    chunks = [ids[i : i + _CHUNK] for i in range(0, len(ids), _CHUNK)]
    texts = await asyncio.gather(*(kegg.list("+".join(chunk)) for chunk in chunks))
    names: dict[str, str] = {}
    for text in texts:
        for key, description in parse_tab_list(text).items():
            names[key.split(":", 1)[-1]] = description
    return names


async def _ko_ecs(kegg: KEGGClient, kos: list[str]) -> dict[str, set[str]]:
    chunks = [kos[i : i + _CHUNK] for i in range(0, len(kos), _CHUNK)]
    texts = await asyncio.gather(*(kegg.link("ec", "+".join(chunk)) for chunk in chunks))
    links: dict[str, set[str]] = {}
    for text in texts:
        for source, target in parse_link_response(text):
            links.setdefault(source.split(":", 1)[-1], set()).add(target.split(":", 1)[-1])
    return links


async def build_pathway_map(
    kegg: KEGGClient,
    pathway_id: str,
    groups: Mapping[str, Sequence[str]] | None = None,
) -> PathwayMap:
    """Draw ``pathway_id`` with ``groups`` ({label: KO/EC ids}) highlighted; see the module doc."""
    map_id = normalize_map_id(pathway_id)
    groups = dict(groups or {})
    if len(groups) > MAX_GROUPS:
        raise PathwayMapError(
            f"{len(groups)} highlight groups; at most {MAX_GROUPS} fit on one map",
            "validation_error",
            "Split the groups over several maps.",
        )
    labels: list[str] = []
    parsed: list[tuple[set[str], list[frozenset[str]]]] = []
    unrecognized: list[str] = []
    for label, ids in groups.items():
        label = str(label).strip()[:MAX_LABEL]
        if not label or label in labels:
            raise PathwayMapError(
                f"Highlight group labels must be non-empty and distinct: {label!r}",
                "validation_error",
            )
        ids = list(ids or [])
        if len(ids) > MAX_IDS_PER_GROUP:
            raise PathwayMapError(
                f"Group {label!r} has {len(ids)} ids; the limit is {MAX_IDS_PER_GROUP}",
                "validation_error",
            )
        kos, ec_sets, bad = split_ids(ids)
        labels.append(label)
        parsed.append((kos, ec_sets))
        unrecognized.extend(bad)

    kgml = await kegg.get(map_id, option="kgml")
    if not kgml or kgml.isspace():
        raise PathwayMapError(
            f"KEGG has no KGML layout for {map_id}",
            "kgml_not_available",
            "Check the map number with search_pathways; a few maps have no layout file.",
        )
    pathway = parse_kgml(kgml)

    boxes = [n for n in pathway.nodes.values() if n.type == "ortholog" and _box_kos(n.name)]
    map_kos = sorted({ko for node in boxes for ko in _box_kos(node.name)})
    first_kos = sorted({_box_kos(node.name)[0] for node in boxes})
    compounds = sorted({n.label for n in pathway.nodes.values()
                        if n.type == "compound" and n.label})

    any_ec = any(ec_sets for _, ec_sets in parsed)
    ko_names, compound_names, ko_ecs = await asyncio.gather(
        _list_names(kegg, first_kos) if first_kos else _none(),
        _list_names(kegg, compounds) if compounds else _none(),
        _ko_ecs(kegg, map_kos) if any_ec and map_kos else _none(),
    )
    # Only `;` separates compound synonyms: commas belong to names (1,6-bisphosphate).
    compound_names = {key: value.split(";", 1)[0].strip() for key, value in compound_names.items()}

    map_ko_set = set(map_kos)
    group_kos: list[set[str]] = []
    group_rows: list[MapGroup] = []
    for index, (label, (kos, ec_sets)) in enumerate(zip(labels, parsed)):
        direct = kos & map_ko_set
        via_ec = {
            ko for ko in map_kos
            if ko not in direct and ko_ecs.get(ko)
            and any(ko_ecs[ko] <= item for item in ec_sets)
        }
        group_kos.append(direct | via_ec)
        group_rows.append(MapGroup(
            label=label,
            color=PALETTE[index],
            ids_given=len(kos) + len(set().union(*ec_sets)),
            kos_on_map=sorted(direct | via_ec),
            matched_by_ec=sorted(via_ec),
            ec_matches={ko: sorted(ko_ecs[ko]) for ko in sorted(via_ec)},
        ))

    box_labels: dict[int, str] = {}
    box_groups: dict[int, list[int]] = {}
    box_rows: list[MapBox] = []
    for node in sorted(boxes, key=lambda n: (n.y, n.x)):
        kos = _box_kos(node.name)
        box_labels[node.id] = _first_name(ko_names.get(kos[0], "")) or kos[0]
        have = [i for i, found in enumerate(group_kos) if found & set(kos)]
        box_groups[node.id] = have
        for i in have:
            group_rows[i].boxes_colored += 1
        box_rows.append(MapBox(
            entry_id=node.id,
            label=box_labels[node.id],
            kos=kos,
            present_in=[labels[i] for i in have],
        ))

    # Steps: KGML reactions keyed by their enzyme box's entry id. A reference map draws
    # every organism's alternative enzyme for one conversion as its own box (HK, GCK,
    # ppgK, ADPGK all make glucose 6-phosphate), so coverage is per step, not per box.
    steps: dict[frozenset, dict] = {}
    for reaction in pathway.reactions:
        node = pathway.nodes.get(reaction.id)
        if node is None or node.id not in box_labels:
            continue

        def names(ids: list[int]) -> list[str]:
            found = (pathway.nodes.get(i) for i in ids)
            return sorted({compound_names.get(n.label) or n.label for n in found if n})

        subs, prods = names(reaction.substrate_ids), names(reaction.product_ids)
        if not subs or not prods:
            continue
        key = frozenset({tuple(subs), tuple(prods)})
        arrow = " ⇌ " if reaction.type == "reversible" else " → "
        step = steps.setdefault(key, {"step": " + ".join(subs) + arrow + " + ".join(prods),
                                      "reactions": [], "boxes": [], "have": set()})
        for name in reaction.name.split():
            if name.startswith("rn:") and name[3:] not in step["reactions"]:
                step["reactions"].append(name[3:])
        if box_labels[node.id] not in step["boxes"]:
            step["boxes"].append(box_labels[node.id])
        step["have"].update(box_groups.get(node.id, []))
    step_rows = [
        MapStep(step=s["step"], reactions=s["reactions"], boxes=s["boxes"],
                present_in=[labels[i] for i in sorted(s["have"])])
        for s in steps.values()
    ]
    for s in steps.values():
        for i in s["have"]:
            group_rows[i].steps_covered += 1

    title = f"{pathway.title} ({map_id})" if pathway.title else map_id
    drawing = await asyncio.to_thread(
        draw_pathway,
        pathway,
        title=title,
        box_labels=box_labels,
        box_groups=box_groups,
        groups=[(row.label, row.color) for row in group_rows],
        compound_names=compound_names,
        footer=ATTRIBUTION,
    )

    notes: list[str] = []
    if groups and not any(row.kos_on_map for row in group_rows):
        notes.append("No group has any of this map's KOs; every box is drawn as absent.")
    if any(not (kos or ec_sets) for kos, ec_sets in parsed):
        notes.append("A group with no KO or EC ids can't be matched and is drawn absent.")
    if any(row.matched_by_ec for row in group_rows):
        notes.append(
            "matched_by_ec KOs share an EC number with the group's ids; an EC can cover "
            "several KOs, so treat these as less specific than a KO match."
        )
    return PathwayMap(
        png=drawing.png,
        summary=PathwayMapSummary(
            pathway_id=map_id,
            title=pathway.title or map_id,
            url=f"https://www.kegg.jp/pathway/{map_id}",
            image_width=drawing.width,
            image_height=drawing.height,
            groups=group_rows,
            box_count=len(box_rows),
            boxes_with_any_group=sum(1 for row in box_rows if row.present_in),
            boxes=box_rows[:MAX_BOXES_LISTED],
            boxes_truncated=len(box_rows) > MAX_BOXES_LISTED,
            step_count=len(step_rows),
            steps_with_any_group=sum(1 for row in step_rows if row.present_in),
            steps=step_rows[:MAX_STEPS_LISTED],
            steps_truncated=len(step_rows) > MAX_STEPS_LISTED,
            map_ko_count=len(map_kos),
            unrecognized_ids=sorted(set(unrecognized))[:50],
            notes=notes,
        ),
    )


async def _none() -> dict:
    return {}
