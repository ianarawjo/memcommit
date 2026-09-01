"""Ownership and behavior contracts for line-oriented batch input."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import memcommit.adapters.console.coordination.batch_input_source as batch_input_source
from memcommit.adapters.console.commands.add.line_input_records import (
    parse_line_input_records,
)
from memcommit.adapters.console.commands.edit.input_records import (
    parse_input_records as parse_edit_input_records,
)


REPOSITORY_ROOT = Path(__file__).parents[1]


def test_batch_input_has_one_source_owner_and_command_local_grammars() -> None:
    source = REPOSITORY_ROOT / "src" / "memcommit"

    assert not (source / "adapters" / "interfaces" / "cli" / "batch_input.py").exists()
    assert not (source / "adapters" / "console" / "shared" / "batch_input.py").exists()
    assert not (
        source / "adapters" / "console" / "shared" / "batch_input_source.py"
    ).exists()
    assert (
        source / "adapters" / "console" / "coordination" / "batch_input_source.py"
    ).is_file()
    assert (
        source
        / "adapters"
        / "console"
        / "commands"
        / "add"
        / "line_input_records.py"
    ).is_file()
    assert (
        source
        / "adapters"
        / "console"
        / "commands"
        / "edit"
        / "input_records.py"
    ).is_file()


def test_batch_input_source_preserves_stdin_line_endings(monkeypatch) -> None:
    patched_sys = type("PatchedSys", (), {"stdin": io.StringIO("one\r\ntwo\n")})
    monkeypatch.setattr(batch_input_source, "sys", patched_sys)

    assert batch_input_source.read_batch_input_text("-") == "one\r\ntwo\n"


def test_batch_input_source_reads_utf8_file_without_newline_translation(tmp_path) -> None:
    path = tmp_path / "batch.txt"
    path.write_bytes("하나\r\ntwo\n".encode())

    assert batch_input_source.read_batch_input_text(str(path)) == "하나\r\ntwo\n"


def test_add_input_records_strip_lines_and_ignore_empty_lines() -> None:
    assert parse_line_input_records("  one  \r\n\r\n\ttwo\t\n") == ["one", "two"]


def test_add_input_records_reject_an_empty_batch() -> None:
    with pytest.raises(ValueError, match="no non-empty lines"):
        parse_line_input_records(" \r\n\t\n")


def test_edit_input_records_split_only_the_first_tab() -> None:
    assert parse_edit_input_records("  abc  \t replacement\tkept \r\n\r\ndef\t") == [
        ("abc", " replacement\tkept "),
        ("def", ""),
    ]


@pytest.mark.parametrize(
    "text,message",
    (
        ("abc replacement", "Line 1: expected UID<TAB>replacement content."),
        (" \tcontent", "Line 1: Memory UID is empty."),
        ("\r\n\t\n", "Input contains no edit records."),
    ),
)
def test_edit_input_records_keep_the_existing_validation_contract(
    text: str,
    message: str,
) -> None:
    with pytest.raises(ValueError) as raised:
        parse_edit_input_records(text)
    assert str(raised.value) == message


def test_add_and_edit_commands_import_their_exact_owners() -> None:
    command_root = (
        REPOSITORY_ROOT
        / "src"
        / "memcommit"
        / "adapters"
        / "console"
        / "commands"
    )
    add_source = (command_root / "add" / "command.py").read_text(encoding="utf-8")
    edit_source = (command_root / "edit" / "command.py").read_text(
        encoding="utf-8"
    )

    assert (
        "from memcommit.adapters.console.commands.add.line_input_records import ("
        in add_source
    )
    assert (
        "parse_line_input_records" in add_source
    )
    assert (
        "from memcommit.adapters.console.commands.edit.input_records import "
        "parse_input_records" in edit_source
    )
    for source in (add_source, edit_source):
        assert (
            "from memcommit.adapters.console.coordination.batch_input_source import"
            in source
        )
        assert "memcommit.adapters.interfaces.cli.batch_input" not in source
