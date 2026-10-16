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


def test_mcp_json_pins_exact_launcher_version() -> None:
    # The Claude plugin directory blocks an unpinned `uvx` launcher, so the pin
    # must be exact and must track the published version.
    root = Path(__file__).resolve().parents[1]
    mcp_config = json.loads((root / ".mcp.json").read_text())

    assert mcp_config["mcpServers"]["kegg"] == {
        "command": "uvx",
        "args": [f"kegg-mcp-server=={__version__}"],
    }


def test_marketplace_entry_has_no_duplicate_mcp_servers() -> None:
    # mcpServers lives in .mcp.json only; Claude Code loads that from the
    # plugin root regardless, so a release bumps one pin, not two.
    root = Path(__file__).resolve().parents[1]
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())

    assert "mcpServers" not in marketplace["plugins"][0]


def test_mcpb_manifest_is_linux_cp312_only() -> None:
    manifest = Path(__file__).resolve().parents[1] / "manifest.json"
    compatibility = json.loads(manifest.read_text())["compatibility"]

    assert compatibility["platforms"] == ["linux"]
    assert compatibility["runtimes"]["python"] == ">=3.12,<3.13"
