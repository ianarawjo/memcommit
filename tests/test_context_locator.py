"""Shared lexical Context-locator contract."""
from __future__ import annotations

import pytest

from memcommit.application.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)


@pytest.mark.parametrize(
    ("current", "locator", "expected"),
    [
        ("task2/advisor1", "../advisor2", "task2/advisor2"),
        (
            "organization/wiki",
            "./facilities",
            "organization/wiki/facilities",
        ),
        ("test/update/from", ".", "test/update/from"),
        ("test/update/from", "..", "test/update"),
        ("test/update/from", "../", "test/update"),
        ("test/update/from", "../../archive", "test/archive"),
        ("test/update/from", "./", "test/update/from"),
    ],
)
def test_resolves_explicit_relative_locator_lexically(
    current,
    locator,
    expected,
):
    assert resolve_context_locator(locator, current=current) == expected


def test_bare_name_remains_global_and_does_not_require_current():
    assert not is_relative_context_locator("child")
    assert (
        resolve_context_locator("child", current="organization/wiki")
        == "child"
    )
    assert resolve_context_locator("task2/advisor2", current=None) == (
        "task2/advisor2"
    )


@pytest.mark.parametrize("locator", [".", "..", "./child", "../sibling"])
def test_explicit_relative_locator_requires_current_context(locator):
    with pytest.raises(ValueError, match="requires a current Context"):
        resolve_context_locator(locator, current=None)


@pytest.mark.parametrize(
    ("current", "locator", "message"),
    [
        (
            "campus",
            "..",
            "resolves to the namespace root",
        ),
        (
            "test/update",
            "../../../outside",
            "escapes above the namespace root",
        ),
        (
            "test/update/from",
            "..//to",
            "contains an empty segment",
        ),
        (
            "test/update/from",
            "./child//leaf",
            "contains an empty segment",
        ),
    ],
)
def test_rejects_ambiguous_or_out_of_bounds_relative_locator(
    current,
    locator,
    message,
):
    with pytest.raises(ValueError, match=message):
        resolve_context_locator(locator, current=current)


@pytest.mark.parametrize(
    "locator",
    [
        "/task2/advisor2",
        "task2/../advisor2",
        r"task2\advisor2",
    ],
)
def test_non_relative_spelling_is_left_for_canonical_name_validation(locator):
    assert resolve_context_locator(
        locator,
        current="task2/advisor1",
    ) == locator
