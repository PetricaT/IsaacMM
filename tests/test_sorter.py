"""Tests for source/sorter.py."""

from __future__ import annotations

import pytest

from source import sorter


class TestExtractWorkshopId:
    def test_converts_to_int(self) -> None:
        result = sorter._extract_workshop_id("mod_12345")
        assert result == 12345
        assert isinstance(result, int)

    def test_returns_none_when_no_id(self) -> None:
        assert sorter._extract_workshop_id("MyMod") is None


class TestBuildGroupIndex:
    def test_extracts_priorities(self) -> None:
        masterlist = {"groups": [{"name": "core", "priority": 1}, {"name": "gameplay", "priority": 2}]}
        result = sorter._build_group_index(masterlist)
        assert result == {"core": 1, "gameplay": 2}

    def test_empty_masterlist(self) -> None:
        assert sorter._build_group_index({}) == {}

    def test_missing_groups_key(self) -> None:
        assert sorter._build_group_index({"other": {}}) == {}


class TestBuildModLookup:
    def test_returns_three_tuples(self) -> None:
        masterlist = {
            "mods": [
                {
                    "id": "some_mod",
                    "name": "Some Mod",
                    "group": "gameplay",
                    "before": [],
                    "after": [],
                }
            ]
        }
        lookup, regex_entries, tag_entries = sorter._build_mod_lookup(masterlist)
        assert isinstance(lookup, dict)
        assert isinstance(regex_entries, list)
        assert isinstance(tag_entries, list)

    def test_empty_masterlist(self) -> None:
        lookup, regex_entries, tag_entries = sorter._build_mod_lookup({})
        assert lookup == {}
        assert regex_entries == []
        assert tag_entries == []


class TestMergeUserRules:
    def test_merges_into_existing_entry(self) -> None:
        mod_lookup = {"existing": {"before": ["a"], "after": []}}
        rules = [{"id": "existing", "before": [], "after": ["b"]}]
        sorter._merge_user_rules(mod_lookup, rules)
        assert "b" in mod_lookup["existing"]["after"]


class TestTopologicalSort:
    @staticmethod
    def _key(x: str) -> str:
        return x

    @staticmethod
    def _before(x: str) -> list[str]:
        return []

    @staticmethod
    def _after(x: str) -> list[str]:
        return []

    def test_preserves_order_when_no_constraints(self) -> None:
        items = ["a", "b", "c"]
        result = sorter._topological_sort(items, self._key, self._before, self._after)
        assert set(result) == set(items)

    def test_simple_ordering(self) -> None:
        items = ["a", "b", "c"]
        result = sorter._topological_sort(
            items,
            self._key,
            lambda x: [],
            lambda x: ["a"] if x == "b" else [],
        )
        assert result.index("b") > result.index("a")

    def test_complex_dag(self) -> None:
        items = ["a", "b", "c", "d"]
        result = sorter._topological_sort(
            items,
            self._key,
            lambda x: {"b": ["a"], "d": ["b", "c"]}.get(x, []),
            lambda x: [],
        )
        assert result.index("b") < result.index("a")
        assert result.index("d") < result.index("b")
        assert result.index("d") < result.index("c")

    def test_handles_empty_list(self) -> None:
        assert sorter._topological_sort([], self._key, self._before, self._after) == []

    def test_handles_cycles_gracefully(self) -> None:
        items = ["a", "b"]
        result = sorter._topological_sort(
            items,
            self._key,
            lambda x: {"a": ["b"], "b": ["a"]}.get(x, []),
            lambda x: [],
        )
        assert len(result) == 2


class TestShouldPreserveName:
    def test_preserve_name_uses_masterlist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sorter, "_extract_workshop_id", lambda x: None if x != "ws_123" else 123)
        monkeypatch.setattr(sorter, "get_masterlist", lambda: {"mods": [{"id": 123, "preserve_name": True}]})

        assert sorter.should_preserve_name("ws_123") is True
        assert sorter.should_preserve_name("unknown_mod") is False
