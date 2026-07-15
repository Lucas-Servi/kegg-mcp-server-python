from __future__ import annotations

import json
import tomllib
from pathlib import Path

from kegg_mcp_server import __version__


def test_pyproject_version_matches_package_version() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())

    assert data["project"]["dynamic"] == ["version"]
    assert data["tool"]["hatch"]["version"]["path"] == "src/kegg_mcp_server/__init__.py"


def test_release_metadata_versions_match_package_version() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "manifest.json").read_text())
    plugin = json.loads((root / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())

    assert manifest["version"] == __version__
    assert plugin["version"] == __version__
    assert marketplace["plugins"][0]["version"] == __version__


def test_mcpb_manifest_is_linux_cp312_only() -> None:
    manifest = Path(__file__).resolve().parents[1] / "manifest.json"
    compatibility = json.loads(manifest.read_text())["compatibility"]

    assert compatibility["platforms"] == ["linux"]
    assert compatibility["runtimes"]["python"] == ">=3.12,<3.13"
