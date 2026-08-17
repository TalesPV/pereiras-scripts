"""Testes para pereiras_scripts.utils."""

import pytest

from pereiras_scripts.utils import chunk, flatten, safe_get, slugify, unique


class TestFlatten:
    def test_flat_list(self):
        assert flatten([1, 2, 3]) == [1, 2, 3]

    def test_one_level(self):
        assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]

    def test_default_depth_one(self):
        assert flatten([[1, [2, 3]], [4]]) == [1, [2, 3], 4]

    def test_depth_two(self):
        assert flatten([[1, [2, [3]]], [4]], depth=2) == [1, 2, [3], 4]

    def test_strings_not_expanded(self):
        assert flatten(["ab", "cd"]) == ["ab", "cd"]

    def test_empty(self):
        assert flatten([]) == []

    def test_mixed_types(self):
        assert flatten([[1, "a"], [True, None]]) == [1, "a", True, None]


class TestChunk:
    def test_even_split(self):
        assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_last_chunk_smaller(self):
        assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_size_larger_than_list(self):
        assert chunk([1, 2], 10) == [[1, 2]]

    def test_empty(self):
        assert chunk([], 3) == []

    def test_size_one(self):
        assert chunk([1, 2, 3], 1) == [[1], [2], [3]]

    def test_invalid_size(self):
        with pytest.raises(ValueError):
            chunk([1, 2], 0)

    def test_negative_size(self):
        with pytest.raises(ValueError):
            chunk([1, 2], -1)


class TestUnique:
    def test_removes_duplicates(self):
        assert unique([3, 1, 2, 1, 3]) == [3, 1, 2]

    def test_preserves_order(self):
        assert unique([4, 5, 4, 6, 5]) == [4, 5, 6]

    def test_no_duplicates(self):
        assert unique([1, 2, 3]) == [1, 2, 3]

    def test_empty(self):
        assert unique([]) == []

    def test_all_same(self):
        assert unique([7, 7, 7]) == [7]

    def test_string_elements(self):
        assert unique(["a", "b", "a"]) == ["a", "b"]


class TestSafeGet:
    def test_dict_single_key(self):
        assert safe_get({"a": 1}, "a") == 1

    def test_dict_nested(self):
        assert safe_get({"a": {"b": 2}}, "a", "b") == 2

    def test_missing_key_returns_default(self):
        assert safe_get({"a": 1}, "b") is None

    def test_custom_default(self):
        assert safe_get({"a": 1}, "b", default=0) == 0

    def test_list_index(self):
        assert safe_get([10, 20, 30], 1) == 20

    def test_nested_list(self):
        assert safe_get([[1, 2], [3, 4]], 1, 0) == 3

    def test_index_out_of_range(self):
        assert safe_get([1, 2], 5, default=-1) == -1

    def test_none_object(self):
        assert safe_get(None, "key", default="x") == "x"

    def test_no_keys(self):
        assert safe_get({"a": 1}) == {"a": 1}


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_accents(self):
        assert slugify("Olá Mundo") == "ola-mundo"

    def test_special_chars(self):
        assert slugify("Olá, Mundo!") == "ola-mundo"

    def test_multiple_spaces(self):
        assert slugify("Python  Scripts") == "python-scripts"

    def test_portuguese(self):
        assert slugify("Python é incrível") == "python-e-incrivel"

    def test_numbers(self):
        assert slugify("item 42 ok") == "item-42-ok"

    def test_already_slug(self):
        assert slugify("already-a-slug") == "already-a-slug"

    def test_empty(self):
        assert slugify("") == ""

    def test_spaces_only(self):
        assert slugify("   ") == ""

    def test_special_chars_only(self):
        assert slugify("!!!") == ""
