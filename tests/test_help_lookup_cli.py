"""Natural-language Help CLI projection."""

from __future__ import annotations

import io

import pytest
from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.command_progress import CommandProgress
from memcommit.help_application import describe_operation
from memcommit.interfaces.tui.operations.help import inventory
from memcommit.query_provider import QueryProviderError


runner = CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def _ordinary_profile(monkeypatch):
    monkeypatch.setattr(inventory, "active_profile_is_study", lambda: False)


class _Provider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls = 0

    def complete(self, _prompt, *, operation, output_schema=None):
        assert operation == "help"
        assert output_schema is not None
        self.calls += 1
        return self.raw


def _invoke(*args: str):
    return runner.invoke(
        app,
        list(args),
        env={"MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1"},
    )


def test_help_request_renders_three_ranked_existing_description_when_rows(monkeypatch):
    provider = _Provider(
        '{"operations":["compare","search","query"]}'
    )
    monkeypatch.setattr(inventory, "connect_help_provider", lambda: provider)

    result = _invoke("help", "compare two Contexts and find related Memories")

    assert result.exit_code == 0
    assert result.stderr == ""
    assert provider.calls == 1
    assert "1 · mem compare ┬ Compare Memories in two Contexts" in result.stdout
    assert "└ WHEN · Comparing two Contexts as a whole" in result.stdout
    assert "2 · mem search ┬ Semantically rank Memories" in result.stdout
    assert "└ WHEN · Finding relevant Memories through meaning" in result.stdout
    assert "3 · mem query ┬ Generate an LLM-based answer" in result.stdout
    assert result.stdout.index("mem compare") < result.stdout.index("mem search")
    assert result.stdout.index("mem search") < result.stdout.index("mem query")
    assert "WHY" not in result.stdout
    assert "FLOW" not in result.stdout
    assert "EFFECT" not in result.stdout
    assert "Overview" not in result.stdout
    assert "Command line" not in result.stdout


def test_help_request_rejects_short_or_empty_provider_selections(monkeypatch):
    provider = _Provider('{"operations":["query"]}')
    monkeypatch.setattr(inventory, "connect_help_provider", lambda: provider)

    one = _invoke("help", "answer from my readable Context")

    assert one.exit_code == 1
    assert "invalid structured output" in one.stderr

    none_provider = _Provider('{"operations":[]}')
    monkeypatch.setattr(
        inventory,
        "connect_help_provider",
        lambda: none_provider,
    )
    none = _invoke("help", "🦆 ??? 123")

    assert none.exit_code == 1
    assert "invalid structured output" in none.stderr


def test_plain_help_does_not_connect_a_provider(monkeypatch):
    monkeypatch.setattr(
        inventory,
        "connect_help_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider connected")),
    )

    result = _invoke("help")

    assert result.exit_code == 0
    assert "mem command inventory" in result.stdout


def test_thinking_progress_is_tty_only_and_focused_lookup_only(monkeypatch):
    class _TTYBuffer(io.StringIO):
        def isatty(self) -> bool:
            return True

    stream = _TTYBuffer()

    def build_progress(operation, stage, *, total):
        return CommandProgress(
            operation,
            stage,
            total=total,
            stream=stream,
            interval=60,
        )

    provider = _Provider(
        '{"operations":["update","meld","merge"]}'
    )
    monkeypatch.setattr(inventory, "CommandProgress", build_progress)
    monkeypatch.setattr(inventory, "connect_help_provider", lambda: provider)

    focused = _invoke("help", "update a campus wiki from mine")

    assert focused.exit_code == 0
    assert "mem update" in focused.stdout
    assert "MEM HELP · 1/1 · THINKING . · 0s" in stream.getvalue()
    assert stream.getvalue().endswith("\r")

    stream.seek(0)
    stream.truncate()
    plain = _invoke("help")

    assert plain.exit_code == 0
    assert "mem command inventory" in plain.stdout
    assert stream.getvalue() == ""


def test_help_request_reports_provider_failure_without_partial_rows(monkeypatch):
    def fail():
        raise QueryProviderError("provider unavailable")

    monkeypatch.setattr(inventory, "connect_help_provider", fail)

    result = _invoke("help", "compare Contexts")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Help error: provider unavailable" in result.stderr


def test_study_help_rejects_copied_description_before_provider(monkeypatch):
    provider = _Provider(
        '{"operations":["query","search","elaborate"]}'
    )
    monkeypatch.setattr(inventory, "active_profile_is_study", lambda: True)
    monkeypatch.setattr(inventory, "connect_help_provider", lambda: provider)

    def fail_progress(*_args, **_kwargs):
        raise AssertionError("Study preflight must not start Help progress")

    monkeypatch.setattr(inventory, "CommandProgress", fail_progress)

    result = _invoke("help", describe_operation("query").summary)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert provider.calls == 0
    assert "Study lookup requires original task wording" in result.stderr
    assert "at least 50%" in result.stderr
    assert "query" not in result.stderr.casefold()


def test_same_description_is_allowed_outside_study(monkeypatch):
    provider = _Provider(
        '{"operations":["query","search","elaborate"]}'
    )
    monkeypatch.setattr(inventory, "connect_help_provider", lambda: provider)

    result = _invoke("help", describe_operation("query").summary)

    assert result.exit_code == 0
    assert provider.calls == 1
    assert "mem query" in result.stdout
