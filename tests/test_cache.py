"""Tests for per-op TTL behavior in the cache."""

from __future__ import annotations

import time

import pytest

from kegg_mcp_server.cache import _TTL_BY_OP, TTLCache, _op_from_path


def test_op_extraction_from_kegg_paths() -> None:
    assert _op_from_path("/info/kegg") == "info"
    assert _op_from_path("/list/organism") == "list"
    assert _op_from_path("/get/hsa00010") == "get"
    assert _op_from_path("/find/pathway/glycolysis") == "find"
    assert _op_from_path("info/kegg") == "info"  # tolerates missing leading slash
    assert _op_from_path("") == ""


def test_get_set_roundtrip() -> None:
    cache = TTLCache()
    cache.set("/info/kegg", "release")
    assert cache.get("/info/kegg") == "release"


def test_miss_returns_none() -> None:
    cache = TTLCache()
    assert cache.get("/get/nothing") is None


def test_per_op_ttl_config_covers_all_kegg_ops() -> None:
    for op in ("info", "list", "get", "find", "conv", "link", "ddi"):
        assert op in _TTL_BY_OP


def test_get_entry_expires_by_default_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    # Freeze a custom clock so we can advance time deterministically.
    current = [1000.0]

    def fake_monotonic() -> float:
        return current[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    cache = TTLCache()
    cache.set("/get/X", "v")
    assert cache.get("/get/X") == "v"
    current[0] += _TTL_BY_OP["get"] + 1
    assert cache.get("/get/X") is None


def test_info_outlives_get(monkeypatch: pytest.MonkeyPatch) -> None:
    current = [1000.0]

    def fake_monotonic() -> float:
        return current[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    cache = TTLCache()
    cache.set("/info/kegg", "release")
    cache.set("/get/hsa00010", "entry")
    # Advance past the `get` TTL but within the `info` TTL
    current[0] += _TTL_BY_OP["get"] + 1
    assert cache.get("/get/hsa00010") is None
    assert cache.get("/info/kegg") == "release"


def test_len_reports_size() -> None:
    cache = TTLCache()
    assert len(cache) == 0
    cache.set("/info/kegg", "x")
    cache.set("/list/pathway", "y")
    assert len(cache) == 2


def test_clear_empties_cache() -> None:
    cache = TTLCache()
    cache.set("/info/kegg", "x")
    cache.clear()
    assert len(cache) == 0
    assert cache.get("/info/kegg") is None


def test_bounded_by_bytes_not_entry_count() -> None:
    cache = TTLCache(maxsize=10)
    cache.set("/get/a", "01234567890")  # 11 bytes, already over budget alone
    assert cache.get("/get/a") is None
    cache.set("/get/b", "12345")
    cache.set("/get/c", "67890")
    assert cache.get("/get/b") == "12345"
    assert cache.get("/get/c") == "67890"


def test_oversize_value_is_skipped_not_raised() -> None:
    cache = TTLCache(maxsize=10)
    cache.set("/get/huge", "x" * 100)  # must not raise
    assert cache.get("/get/huge") is None


def test_entry_ops_get_six_hour_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    current = [1000.0]

    def fake_monotonic() -> float:
        return current[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    cache = TTLCache()
    for op, path in (
        ("get", "/get/hsa00010"),
        ("find", "/find/pathway/x"),
        ("conv", "/conv/uniprot/hsa"),
        ("link", "/link/pathway/hsa"),
        ("ddi", "/ddi/D00001"),
    ):
        cache.set(path, "v")
        current[0] += _TTL_BY_OP[op] - 1
        assert cache.get(path) == "v", op
        current[0] += 2
        assert cache.get(path) is None, op
        current[0] = 1000.0
