"""2D box-and-arrow grid renderer for KEGG pathways.

Part of the KEGG MCP Server by Elytron Biotech.
Uses KGML x/y coordinates to place nodes on a character grid
and draws ASCII connections between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kegg_mcp_server.ascii.kgml import KGMLPathway


def render_grid(pathway: KGMLPathway, *, width: int = 100, height: int = 40) -> str:
    """Render a 2D spatial layout from KGML node coordinates."""
    nodes_with_pos = [
        n for n in pathway.nodes.values() if n.x > 0 or n.y > 0
    ]

    if not nodes_with_pos:
        from kegg_mcp_server.ascii.chain import render_chain

        return "(No spatial coordinates in KGML; falling back to chain mode)\n\n" + render_chain(
            pathway, max_width=width
        )

    # Compute bounding box
    min_x = min(n.x for n in nodes_with_pos)
    max_x = max(n.x for n in nodes_with_pos)
    min_y = min(n.y for n in nodes_with_pos)
    max_y = max(n.y for n in nodes_with_pos)

    range_x = max(max_x - min_x, 1)
    range_y = max(max_y - min_y, 1)

    # Reserve space for labels (max 10 chars per node box)
    usable_width = width - 2
    usable_height = height - 2

    # Initialize grid buffer
    grid: list[list[str]] = [[" " for _ in range(width)] for _ in range(height)]

    # Place nodes
    placed: dict[int, tuple[int, int]] = {}  # node_id -> (col, row)
    legend: list[dict[str, str]] = []

    for node in nodes_with_pos:
        # Skip map-link nodes (they're just references to other pathways)
        if node.type == "map":
            continue

        col = int((node.x - min_x) / range_x * (usable_width - 8)) + 1
        row = int((node.y - min_y) / range_y * (usable_height - 2)) + 1
        col = max(1, min(col, width - 10))
        row = max(0, min(row, height - 1))

        # Get short label
        label = _short_label(node.label or node.name)
        box = f"[{label}]"

        # Check for collision and shift if needed
        row, col = _find_free_spot(grid, row, col, len(box), width, height)

        # Place the box on the grid
        for i, ch in enumerate(box):
            if 0 <= col + i < width:
                grid[row][col + i] = ch

        placed[node.id] = (col + len(box) // 2, row)
        legend.append({"short": label, "full": node.label or node.name, "id": node.name})

    # Draw edges for reactions
    for rxn in pathway.reactions:
        for sub_id in rxn.substrate_ids:
            for prod_id in rxn.product_ids:
                if sub_id in placed and prod_id in placed:
                    _draw_edge(grid, placed[sub_id], placed[prod_id], width, height)

    # Draw edges for relations
    for rel in pathway.relations:
        if rel.entry1 in placed and rel.entry2 in placed:
            _draw_edge(grid, placed[rel.entry1], placed[rel.entry2], width, height)

    # Render grid to string
    rendered_lines = ["".join(row).rstrip() for row in grid]
    # Remove trailing empty lines
    while rendered_lines and not rendered_lines[-1].strip():
        rendered_lines.pop()

    # Header
    title = pathway.title or pathway.name
    org_info = f" ({pathway.org})" if pathway.org else ""
    header = f"{title}{org_info}"

    output_parts = [header, "=" * min(len(header), width), ""]
    output_parts.extend(rendered_lines)

    # Legend
    if legend:
        output_parts.append("")
        output_parts.append("Legend:")
        for item in legend[:30]:
            output_parts.append(f"  [{item['short']}] = {item['full']} ({item['id']})")
        if len(legend) > 30:
            output_parts.append(f"  ... and {len(legend) - 30} more nodes")

    return "\n".join(output_parts)


def _short_label(label: str, max_len: int = 8) -> str:
    """Truncate a label for grid display."""
    if "," in label:
        label = label.split(",")[0].strip()
    if ":" in label and len(label.split(":")[0]) <= 4:
        label = label.split(":", 1)[1]
    # Remove trailing ellipsis-causing whitespace
    label = label.strip()
    if len(label) > max_len:
        return label[: max_len - 1] + "~"
    return label


def _find_free_spot(
    grid: list[list[str]], row: int, col: int, box_len: int, width: int, height: int
) -> tuple[int, int]:
    """Find nearest free position for a box, shifting rows if collided."""
    for offset in range(0, height, 1):
        for r in [row + offset, row - offset]:
            if 0 <= r < height:
                if all(
                    grid[r][c] == " " for c in range(col, min(col + box_len, width))
                ):
                    return r, col
    return row, col


def _draw_edge(
    grid: list[list[str]],
    src: tuple[int, int],
    dst: tuple[int, int],
    width: int,
    height: int,
) -> None:
    """Draw a simple connection between two points using ASCII chars."""
    sx, sy = src
    dx, dy = dst

    # Simple horizontal/vertical routing
    if sy == dy:
        # Horizontal line
        start_x, end_x = min(sx, dx), max(sx, dx)
        for x in range(start_x + 1, end_x):
            if 0 <= x < width and grid[sy][x] == " ":
                grid[sy][x] = "─"
        if 0 <= end_x < width and grid[dy][end_x] == " ":
            grid[dy][end_x] = "▶" if dx > sx else "◀"
    elif sx == dx:
        # Vertical line
        start_y, end_y = min(sy, dy), max(sy, dy)
        for y in range(start_y + 1, end_y):
            if 0 <= y < height and grid[y][sx] == " ":
                grid[y][sx] = "│"
        if 0 <= end_y < height and 0 <= sx < width and grid[end_y][sx] == " ":
            grid[end_y][sx] = "▼" if dy > sy else "▲"
    else:
        # L-shaped routing: go horizontal first, then vertical
        mid_x = dx
        # Horizontal segment
        start_x, end_x = min(sx, mid_x), max(sx, mid_x)
        for x in range(start_x + 1, end_x):
            if 0 <= x < width and 0 <= sy < height and grid[sy][x] == " ":
                grid[sy][x] = "─"
        # Corner
        if 0 <= mid_x < width and 0 <= sy < height and grid[sy][mid_x] == " ":
            if dy > sy:
                grid[sy][mid_x] = "┐" if mid_x > sx else "┌"
            else:
                grid[sy][mid_x] = "┘" if mid_x > sx else "└"
        # Vertical segment
        start_y, end_y = min(sy, dy), max(sy, dy)
        for y in range(start_y + 1, end_y):
            if 0 <= y < height and 0 <= mid_x < width and grid[y][mid_x] == " ":
                grid[y][mid_x] = "│"
        # Arrow head
        if 0 <= dy < height and 0 <= mid_x < width and grid[dy][mid_x] == " ":
            grid[dy][mid_x] = "▼" if dy > sy else "▲"
