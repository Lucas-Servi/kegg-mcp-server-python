"""Tests for draw_pathway_map: id handling, KO/EC matching, the summary and the PNG."""

from __future__ import annotations

import asyncio
import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from PIL import Image

from kegg_mcp_server.drawing import MAX_GROUPS, PALETTE
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.pathway_map import PathwayMapSummary
from kegg_mcp_server.pathway_map import (
    PathwayMapError,
    build_pathway_map,
    normalize_map_id,
    split_ids,
)
from kegg_mcp_server.tools import pathway_map as pathway_map_tool

KGML = (Path(__file__).parent / "fixtures" / "kgml" / "ko00010_sample.xml").read_text()

NAMES = {
    "K00844": "HK; hexokinase [EC:2.7.1.1]",
    "K01810": "GPI, pgi; glucose-6-phosphate isomerase [EC:5.3.1.9]",
    "K01623": "ALDO; fructose-bisphosphate aldolase, class I [EC:4.1.2.13]",
    "C00267": "alpha-D-Glucose; alpha-D-Glucopyranose",
    "C00668": "alpha-D-Glucose 6-phosphate",
    "C05345": "beta-D-Fructose 6-phosphate",
    "C00354": "D-Fructose 1,6-bisphosphate; D-Fructose 1,6-diphosphate",
}
KO_EC = "ko:K00844\tec:2.7.1.1\nko:K12407\tec:2.7.1.2\nko:K01810\tec:5.3.1.9\n" \
        "ko:K01623\tec:4.1.2.13\nko:K01624\tec:4.1.2.13\n"


class FakeKEGG:
    def __init__(self, kgml: str = KGML) -> None:
        self.kgml = kgml
        self.calls: list[tuple[str, str]] = []

    async def get(self, entry: str, option: str | None = None) -> str:
        self.calls.append(("get", f"{entry}/{option}"))
        return self.kgml

    async def list(self, ids: str) -> str:
        self.calls.append(("list", ids))
        return "".join(f"{i}\t{NAMES[i]}\n" for i in ids.split("+") if i in NAMES)

    async def link(self, target: str, source: str) -> str:
        self.calls.append(("link", f"{target}/{source}"))
        return KO_EC


def _build(groups=None, kegg=None):
    return asyncio.run(build_pathway_map(kegg or FakeKEGG(), "map00010", groups))


@pytest.mark.parametrize(
    "given", ["map00010", "ko00010", "eco00010", "path:hsa00010", "00010", " KO00010 "]
)
def test_any_map_id_form_is_drawn_as_the_ko_reference_map(given: str) -> None:
    assert normalize_map_id(given) == "ko00010"


@pytest.mark.parametrize("given", ["map01100", "01200", "ko01230"])
def test_global_maps_are_refused(given: str) -> None:
    with pytest.raises(PathwayMapError) as exc:
        normalize_map_id(given)
    assert exc.value.code == "global_map"


@pytest.mark.parametrize("given", ["", "glycolysis", "map0001", "K00844"])
def test_bad_map_ids_are_validation_errors(given: str) -> None:
    with pytest.raises(PathwayMapError) as exc:
        normalize_map_id(given)
    assert exc.value.code == "validation_error"


def test_split_ids_accepts_ko_and_ec_spellings() -> None:
    kos, ec_sets, bad = split_ids(
        ["K00844", "ko:K01810", "KEGG:K01623", "EC:2.7.1.1", "ec:5.3.1.9", "4.1.2.13",
         "EC:1.1.1.-", "hexokinase", ""]
    )
    assert kos == {"K00844", "K01810", "K01623"}
    assert ec_sets == [{"2.7.1.1"}, {"5.3.1.9"}, {"4.1.2.13"}]
    assert bad == ["EC:1.1.1.-", "hexokinase"]


def test_one_item_is_one_gene_and_db_xref_strings_work_as_is() -> None:
    kos, ec_sets, bad = split_ids(
        ["COG:COG0205 EC:2.7.1.11 GO:0003872 KEGG:K00850", "K01810,EC:5.3.1.9"]
    )
    assert kos == {"K00850", "K01810"}
    assert ec_sets == [{"2.7.1.11"}, {"5.3.1.9"}]
    assert bad == []


def test_a_bifunctional_ko_needs_one_gene_with_all_its_ecs() -> None:
    kegg = FakeKEGG()
    # K01624 made bifunctional for this test: 4.1.2.13 + 2.2.1.2.
    kegg.link = _links(KO_EC + "ko:K01624\tec:2.2.1.2\n")
    split = _build({"G": ["EC:4.1.2.13", "EC:2.2.1.2"]}, kegg=kegg).summary.groups[0]
    assert split.matched_by_ec == ["K01623"]
    together = _build({"G": ["EC:4.1.2.13 EC:2.2.1.2"]}, kegg=kegg).summary.groups[0]
    assert together.matched_by_ec == ["K01623", "K01624"]
    assert together.ec_matches["K01624"] == ["2.2.1.2", "4.1.2.13"]


def _links(text: str):
    async def link(_target: str, _source: str) -> str:
        return text

    return link


def test_plain_map_has_no_groups_and_skips_the_ec_lookup() -> None:
    kegg = FakeKEGG()
    result = _build(kegg=kegg)
    summary = result.summary
    assert summary.pathway_id == "ko00010"
    assert summary.title == "Glycolysis / Gluconeogenesis"
    assert summary.url == "https://www.kegg.jp/pathway/ko00010"
    assert summary.groups == []
    assert summary.box_count == 3
    assert summary.map_ko_count == 5
    assert summary.boxes_with_any_group == 0
    assert [box.label for box in summary.boxes] == ["HK", "GPI", "ALDO"]
    assert not any(kind == "link" for kind, _ in kegg.calls)
    assert ("get", "ko00010/kgml") in kegg.calls


def test_groups_colour_boxes_by_ko_and_by_ec() -> None:
    result = _build({"Strain A": ["K00844", "EC:4.1.2.13"], "Strain B": ["K01810", "K99999"]})
    summary = result.summary
    a, b = summary.groups
    assert (a.label, a.color, b.color) == ("Strain A", PALETTE[0], PALETTE[1])
    assert a.kos_on_map == ["K00844", "K01623", "K01624"]
    assert a.matched_by_ec == ["K01623", "K01624"]
    assert a.ec_matches == {"K01623": ["4.1.2.13"], "K01624": ["4.1.2.13"]}
    assert a.boxes_colored == 2
    assert b.kos_on_map == ["K01810"] and b.matched_by_ec == [] and b.boxes_colored == 1
    assert b.ids_given == 2  # K99999 is a valid KO, just not on this map
    present = {box.label: box.present_in for box in summary.boxes}
    assert present == {"HK": ["Strain A"], "GPI": ["Strain B"], "ALDO": ["Strain A"]}
    assert summary.boxes_with_any_group == 3
    steps = {step.step: step for step in summary.steps}
    assert steps["alpha-D-Glucose → alpha-D-Glucose 6-phosphate"].boxes == ["HK"]
    assert steps["alpha-D-Glucose → alpha-D-Glucose 6-phosphate"].present_in == ["Strain A"]
    isomerase = steps["alpha-D-Glucose 6-phosphate ⇌ beta-D-Fructose 6-phosphate"]
    assert (isomerase.reactions, isomerase.present_in) == (["R02740"], ["Strain B"])
    assert (summary.step_count, summary.steps_with_any_group) == (2, 2)
    assert (a.steps_covered, b.steps_covered) == (1, 1)
    assert any("matched_by_ec" in note for note in summary.notes)


def test_a_group_with_no_match_is_reported_not_silently_blank() -> None:
    summary = _build({"Empty": ["K99999"]}).summary
    assert summary.groups[0].kos_on_map == []
    assert summary.boxes_with_any_group == 0
    assert any("every box is drawn as absent" in note for note in summary.notes)


def test_compound_names_keep_their_commas() -> None:
    kegg = FakeKEGG(kgml=KGML.replace("C05345", "C00354"))
    steps = [step.step for step in _build(kegg=kegg).summary.steps]
    assert "alpha-D-Glucose 6-phosphate ⇌ D-Fructose 1,6-bisphosphate" in steps


def test_unrecognized_ids_are_listed() -> None:
    summary = _build({"G": ["K00844", "not-an-id"]}).summary
    assert summary.unrecognized_ids == ["not-an-id"]


def test_png_is_valid_and_matches_the_summary_size() -> None:
    result = _build({"Strain A": ["K00844"]})
    image = Image.open(io.BytesIO(result.png))
    assert image.format == "PNG"
    assert image.size == (result.summary.image_width, result.summary.image_height)
    assert len(result.png) < 2_000_000


def test_group_limits() -> None:
    too_many = {f"G{i}": ["K00844"] for i in range(MAX_GROUPS + 1)}
    with pytest.raises(PathwayMapError):
        _build(too_many)
    with pytest.raises(PathwayMapError):
        _build({" ": ["K00844"]})


def test_missing_kgml_is_a_clear_error() -> None:
    with pytest.raises(PathwayMapError) as exc:
        _build(kegg=FakeKEGG(kgml=""))
    assert exc.value.code == "kgml_not_available"


def _tool():
    registry: dict[str, object] = {}

    class FakeMCP:
        def tool(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            def decorator(func):  # noqa: ANN001, ANN202
                registry[func.__name__] = func
                return func

            return decorator

    pathway_map_tool.register(FakeMCP())
    return registry["draw_pathway_map"]


def _ctx(kegg: FakeKEGG):
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(kegg=kegg))
    )


def test_tool_returns_summary_text_structured_content_and_a_png_block() -> None:
    result = asyncio.run(
        _tool()(pathway_id="00010", highlight={"G": ["K01810"]}, ctx=_ctx(FakeKEGG()))
    )
    assert isinstance(result, CallToolResult)
    text, image = result.content
    assert text.type == "text" and image.type == "image"
    assert image.mime_type == "image/png"
    assert base64.b64decode(image.data).startswith(b"\x89PNG")
    summary = PathwayMapSummary.model_validate(result.structured_content)
    assert summary.groups[0].kos_on_map == ["K01810"]
    assert json.loads(text.text) == result.structured_content


def test_tool_raises_global_map_as_tool_error() -> None:
    with pytest.raises(ToolError) as exc:
        asyncio.run(_tool()(pathway_id="map01100", ctx=_ctx(FakeKEGG())))
    error = ErrorResult.model_validate_json(str(exc.value))
    assert error.code == "global_map"
    assert error.hint
