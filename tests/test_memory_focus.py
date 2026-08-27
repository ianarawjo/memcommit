from __future__ import annotations

from dataclasses import dataclass

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.context_targeting.memory_focus import (
    MemoryFocusError,
    is_memory_uid_prefix,
    is_memory_uid_selector,
    resolve_memory_focus,
)


@dataclass(frozen=True)
class Candidate:
    uid: str


runner = CliRunner()


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("deadbeef", True),
        ("DEADBEEF", True),
        ("deadbeef-1234", True),
        ("deadbee", False),
        ("deadbeef0", False),
        ("release-1", False),
        ("12345678-1234-4234-8234-123456789abc", True),
    ),
)
def test_public_memory_uid_selector_shape(value: str, expected: bool) -> None:
    assert is_memory_uid_selector(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("0", True),
        ("08df", True),
        ("DEADBEEF", True),
        ("deadbeef-", True),
        ("deadbeef0", False),
        ("", False),
        ("memory", False),
    ),
)
def test_canonical_memory_uid_prefix_shape(value: str, expected: bool) -> None:
    assert is_memory_uid_prefix(value) is expected


def test_no_selector_preserves_the_complete_actionable_frame() -> None:
    first = Candidate("11111111-1111-4111-8111-111111111111")
    second = Candidate("22222222-2222-4222-8222-222222222222")

    focus = resolve_memory_focus((first, second), None)

    assert focus.selected_uid is None
    assert focus.actionable == (first, second)
    assert focus.context_only == ()


def test_selector_separates_one_actionable_memory_from_context_only_neighbors() -> None:
    first = Candidate("11111111-1111-4111-8111-111111111111")
    second = Candidate("22222222-2222-4222-8222-222222222222")

    focus = resolve_memory_focus((first, second), "22222222")

    assert focus.selected_uid == second.uid
    assert focus.actionable == (second,)
    assert focus.context_only == (first,)


def test_selector_rejects_missing_and_ambiguous_prefixes() -> None:
    candidates = (
        Candidate("11111111-1111-4111-8111-111111111111"),
        Candidate("11111112-1111-4111-8111-111111111111"),
    )

    with pytest.raises(MemoryFocusError, match="No Source Memory"):
        resolve_memory_focus(candidates, "9", label="Source Memory")
    with pytest.raises(MemoryFocusError, match="Ambiguous prefix"):
        resolve_memory_focus(candidates, "1111111", label="Source Memory")


@pytest.mark.parametrize("command", ["forget", "sever"])
def test_selective_curation_commands_do_not_offer_memory_focus(command: str) -> None:
    result = runner.invoke(app, [command, "--memory", "deadbeef"])

    assert result.exit_code == 2
    assert "No such option: --memory" in result.output


@pytest.mark.parametrize(
    ("command", "flags"),
    [
        ("atomize", ("--memory",)),
        ("compare", ("--reference-memory", "--compared-memory")),
        ("update", ("--source-memory", "--target-memory")),
        ("meld", ("--incoming-memory", "--baseline-memory")),
    ],
)
def test_supported_commands_publish_explicit_memory_focus_flags(
    command: str,
    flags: tuple[str, ...],
) -> None:
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    for flag in flags:
        assert flag in result.output
