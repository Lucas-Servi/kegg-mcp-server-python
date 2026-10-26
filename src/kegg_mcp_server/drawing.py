"""Draw a KEGG pathway from its KGML layout as a PNG.

Part of the KEGG MCP Server by Elytron Biotech.

This is our own drawing of the KGML coordinates (boxes, compounds, reaction lines and
links to other maps), not KEGG's map bitmap, which is not redistributed. Pure function:
everything it needs (names, colours, which groups have which box) is passed in.
"""

from __future__ import annotations

import functools
import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from kegg_mcp_server.ascii.kgml import KGMLPathway

# Okabe–Ito, distinguishable with the common colour-vision deficiencies.
PALETTE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000")
MAX_GROUPS = len(PALETTE)

_SCALE = 2
_MARGIN = 24
_BOX_FILL = "#FFFFFF"
_ABSENT = "#E3E3E3"
_INK = "#1F1F1F"
_LINE = "#8C8C8C"
_MAP_FILL = "#F4F1E8"
_MAX_SIDE = 4000  # px, before scaling down


@dataclass
class Drawing:
    png: bytes
    width: int
    height: int


@functools.lru_cache(maxsize=32)
def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: float) -> str:
    """The text, cut with an ellipsis to fit ``width`` pixels."""
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…" if text else ""


def draw_pathway(
    pathway: KGMLPathway,
    *,
    title: str,
    box_labels: dict[int, str],
    box_groups: dict[int, list[int]],
    groups: list[tuple[str, str]],
    compound_names: dict[str, str],
    footer: str,
) -> Drawing:
    """Render the map.

    ``box_groups`` maps an ortholog entry id to the indexes (into ``groups``, a list of
    ``(label, colour)``) that have it. With no groups, boxes are drawn plain.
    """
    shown = [n for n in pathway.nodes.values() if n.type in ("ortholog", "compound", "map")
             and (n.x or n.y) and n.name != pathway.name]
    if shown:
        min_x = min(n.x - n.width / 2 for n in shown)
        min_y = min(n.y - n.height / 2 for n in shown)
        max_x = max(n.x + n.width / 2 for n in shown)
        max_y = max(n.y + n.height / 2 for n in shown)
    else:
        min_x = min_y = 0
        max_x, max_y = 400, 200

    scale = _SCALE
    span = max(max_x - min_x, max_y - min_y, 1)
    if span * scale > _MAX_SIDE:
        scale = _MAX_SIDE / span

    title_h = 44
    legend_rows = (len(groups) + 1 + 3) // 4 if groups else 0
    legend_h = 28 + 26 * legend_rows if groups else 0
    footer_h = 30
    width = int((max_x - min_x) * scale + 2 * _MARGIN)
    width = max(width, 640)
    height = int((max_y - min_y) * scale + 2 * _MARGIN + title_h + legend_h + footer_h)

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    top = _MARGIN + title_h

    def at(x: float, y: float) -> tuple[float, float]:
        return ((x - min_x) * scale + _MARGIN, (y - min_y) * scale + top)

    # Sized for the image shown at about half its width in a chat answer.
    small = _font(max(9, int(8.5 * scale)))
    tiny = _font(max(8, int(8 * scale)))
    box_sizes = [max(9, int(size * scale)) for size in (11.5, 10.5, 9.5, 8.5)]

    # Reactions: substrate → product lines under the boxes.
    for reaction in pathway.reactions:
        for sub_id in reaction.substrate_ids:
            for prod_id in reaction.product_ids:
                sub = pathway.nodes.get(sub_id)
                prod = pathway.nodes.get(prod_id)
                if not sub or not prod:
                    continue
                start, end = at(sub.x, sub.y), at(prod.x, prod.y)
                draw.line([start, end], fill=_LINE, width=max(1, int(scale)))
                if reaction.type == "irreversible":
                    _arrowhead(draw, start, end, 4 * scale)

    # Links to other maps.
    for node in pathway.nodes.values():
        # The map's own title box (``TITLE:…``) repeats the image title.
        if node.type != "map" or not (node.x or node.y) or node.name == pathway.name:
            continue
        x0, y0 = at(node.x - node.width / 2, node.y - node.height / 2)
        x1, y1 = at(node.x + node.width / 2, node.y + node.height / 2)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=6 * scale, fill=_MAP_FILL, outline=_LINE)
        _wrapped(draw, node.label, (x0, y0, x1, y1), small)

    # Gene boxes, one stripe per group.
    for node in pathway.nodes.values():
        if node.type != "ortholog" or not (node.x or node.y):
            continue
        x0, y0 = at(node.x - node.width / 2, node.y - node.height / 2)
        x1, y1 = at(node.x + node.width / 2, node.y + node.height / 2)
        if groups:
            have = set(box_groups.get(node.id, []))
            stripe = (x1 - x0) / len(groups)
            for i, (_, colour) in enumerate(groups):
                draw.rectangle(
                    [x0 + i * stripe, y0, x0 + (i + 1) * stripe, y1],
                    fill=colour if i in have else _ABSENT,
                )
        else:
            draw.rectangle([x0, y0, x1, y1], fill=_BOX_FILL)
        draw.rectangle([x0, y0, x1, y1], outline=_INK, width=1)
        text = box_labels.get(node.id, "")
        # The largest size that fits the box, else the smallest one with an ellipsis.
        fitting = (size for size in box_sizes
                   if draw.textlength(text, font=_font(size)) <= x1 - x0 - 4)
        font = _font(next(fitting, box_sizes[-1]))
        label = _fit(draw, text, font, x1 - x0 - 4)
        draw.text(
            ((x0 + x1) / 2, (y0 + y1) / 2), label, fill=_INK, font=font, anchor="mm",
            stroke_width=max(1, int(scale)), stroke_fill="white",
        )

    # Compounds.
    for node in pathway.nodes.values():
        if node.type != "compound" or not (node.x or node.y):
            continue
        cx, cy = at(node.x, node.y)
        r = max(3, node.width / 2 * scale)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white", outline=_INK)
        name = compound_names.get(node.label) or node.label
        draw.text((cx, cy + r + 2), _fit(draw, name, tiny, 70 * scale), fill=_INK, font=tiny,
                  anchor="ma", stroke_width=max(1, int(scale)), stroke_fill="white")

    # Title, legend, footer.
    draw.text((_MARGIN, _MARGIN), _fit(draw, title, _font(22), width - 2 * _MARGIN),
              fill=_INK, font=_font(22))
    y = height - footer_h - legend_h + 10
    if groups:
        entries = [*groups, ("absent", _ABSENT)]
        col = (width - 2 * _MARGIN) / 4
        label_font = _font(14)
        for i, (label, colour) in enumerate(entries):
            ex = _MARGIN + (i % 4) * col
            ey = y + (i // 4) * 26
            draw.rectangle([ex, ey, ex + 18, ey + 14], fill=colour, outline=_INK)
            draw.text((ex + 26, ey + 7), _fit(draw, label, label_font, col - 34), fill=_INK,
                      font=label_font, anchor="lm")
    draw.text((_MARGIN, height - footer_h + 6), footer, fill="#555555", font=_font(12))

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return Drawing(png=out.getvalue(), width=width, height=height)


def _arrowhead(draw: ImageDraw.ImageDraw, start, end, size: float) -> None:
    (x0, y0), (x1, y1) = start, end
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length < size * 2:
        return
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    # Stop short of the compound circle the line ends on.
    tip = (x1 - ux * size, y1 - uy * size)
    left = (tip[0] - ux * size - uy * size * 0.6, tip[1] - uy * size + ux * size * 0.6)
    right = (tip[0] - ux * size + uy * size * 0.6, tip[1] - uy * size - ux * size * 0.6)
    draw.polygon([tip, left, right], fill=_LINE)


def _wrapped(draw: ImageDraw.ImageDraw, text: str, box, font) -> None:
    """Centre ``text`` in ``box``, wrapped by words to its width."""
    x0, y0, x1, y1 = box
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= x1 - x0 - 6 or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    step = (font.size if hasattr(font, "size") else 10) + 2
    max_lines = max(1, int((y1 - y0 - 4) // step))
    lines = [_fit(draw, item, font, x1 - x0 - 6) for item in lines[:max_lines]]
    y = (y0 + y1) / 2 - step * (len(lines) - 1) / 2
    for item in lines:
        draw.text(((x0 + x1) / 2, y), item, fill=_INK, font=font, anchor="mm")
        y += step
