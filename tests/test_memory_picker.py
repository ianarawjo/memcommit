"""Interaction and presentation contracts for trace/rationale Memory selection."""
from __future__ import annotations

import io

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.memory_picker import (
    _render_memory_options,
    choose_memory,
)
from memcommit.provenance import TraceCandidate


def candidate(
    suffix: int,
    *,
    content: str | None = None,
    status: str = "CURRENT",
) -> TraceCandidate:
    return TraceCandidate(
        uid=f"00000000-0000-4000-8000-{suffix:012d}",
        content=content if content is not None else f"Memory {suffix}",
        position=suffix,
        status=status,  # type: ignore[arg-type]
    )


def test_picker_returns_the_exact_selected_uid():
    options = (candidate(1), candidate(2, status="HISTORICAL"))
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = choose_memory(
            options,
            context_name="notes",
            operation="trace",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == options[1].uid


def test_picker_navigation_clamps_and_supports_home_end():
    options = tuple(candidate(index) for index in range(1, 5))
    with create_pipe_input() as pipe_input:
        # End -> clamp below last -> Home -> second row -> accept.
        pipe_input.send_text("\x1b[F\x1b[B\x1b[H\x1b[B\r")
        selected = choose_memory(
            options,
            context_name="notes",
            operation="rationale",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == options[1].uid


@pytest.mark.parametrize("key", ["q", "\x1b", "\x03"])
def test_picker_cancel_keys_return_no_uid(key: str):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(key)
        selected = choose_memory(
            (candidate(1),),
            context_name="notes",
            operation="trace",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected is None


def test_picker_rows_escape_untrusted_content_and_mark_historical_state():
    options = (
        candidate(
            1,
            content="safe\nFAKE HEADING\u202e",
            status="HISTORICAL",
        ),
    )

    rendered = "".join(
        text
        for style, text in _render_memory_options(options, selected=0)
        if style != "[SetCursorPosition]"
    )

    assert "HISTORICAL" in rendered
    assert "safe\\nFAKE HEADING\\u202e" in rendered
    assert "\u202e" not in rendered


def test_picker_requires_a_tty_when_requested(monkeypatch):
    monkeypatch.setattr(
        "memcommit.commands.memory_picker.sys.stdin",
        io.StringIO(),
    )
    monkeypatch.setattr(
        "memcommit.commands.memory_picker.sys.stdout",
        io.StringIO(),
    )

    with pytest.raises(ValueError, match="requires a terminal"):
        choose_memory(
            (candidate(1),),
            context_name="notes",
            operation="trace",
        )


def test_picker_rejects_empty_duplicate_or_invalid_inputs():
    item = candidate(1)
    with pytest.raises(ValueError, match="No current or retained"):
        choose_memory(
            (),
            context_name="notes",
            operation="trace",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="duplicate"):
        choose_memory(
            (item, item),
            context_name="notes",
            operation="trace",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="Context name"):
        choose_memory(
            (item,),
            context_name="",
            operation="trace",
            require_tty=False,
        )
    with pytest.raises(ValueError, match="operation"):
        choose_memory(
            (item,),
            context_name="notes",
            operation="inspect",  # type: ignore[arg-type]
            require_tty=False,
        )
