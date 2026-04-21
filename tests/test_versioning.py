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


def test_manifest_version_matches_package_version() -> None:
    manifest = Path(__file__).resolve().parents[1] / "manifest.json"
    data = json.loads(manifest.read_text())

    assert data["version"] == __version__
