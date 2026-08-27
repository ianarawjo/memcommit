from __future__ import annotations

import click
from click.testing import CliRunner

from memcommit.adapters.interfaces.cli.show import render_show
from memcommit.adapters.interfaces.console.theme import memory_object_color_rgb
from memcommit.application.operations.show.application import (
    ShowContextSnapshot,
    ShowMemory,
    ShowMemoryReference,
    ShowResult,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceState,
)


def _render(result: ShowResult, *, color: bool) -> str:
    @click.command()
    def command() -> None:
        render_show(result)

    rendered = CliRunner().invoke(command, color=color)
    assert rendered.exit_code == 0
    return rendered.output


def _memory() -> ShowMemory:
    return ShowMemory(
        uid="11111111-memory",
        content="Direct Memory body",
        source=SourceDisplayFacts(form=SourceForm.MEMORY),
    )


def test_show_exact_memory_uses_the_shared_memory_foreground() -> None:
    result = ShowResult(
        requested_context_name="notes",
        resolved_context_name="notes",
        selector="11111111",
        value=_memory(),
    )

    colored = _render(result, color=True)

    assert click.unstyle(colored) == (
        "[Memory notes:11111111-memory] Direct Memory body\n"
    )
    assert click.style(
        "Direct Memory body",
        fg=memory_object_color_rgb(),
    ) in colored
    assert click.unstyle(colored) == _render(result, color=False)


def test_show_context_uses_the_shared_foreground_for_direct_and_referenced_memory() -> None:
    referenced = ShowMemoryReference(
        uid="22222222-reference",
        target_context_uid="source-context",
        target_context_name="source",
        target_memory_uid="33333333-memory",
        content="Referenced Memory body",
        source=SourceDisplayFacts(
            form=SourceForm.MEMORY_REFERENCE,
            states=(SourceState.READ_ONLY,),
        ),
    )
    context = ShowContextSnapshot(
        uid="notes-context",
        name="notes",
        items=(_memory(), referenced),
        source=SourceDisplayFacts(),
    )
    result = ShowResult(
        requested_context_name="notes",
        resolved_context_name="notes",
        selector=None,
        value=context,
    )

    colored = _render(result, color=True)

    for content in ("Direct Memory body", "           Referenced Memory body"):
        assert click.style(content, fg=memory_object_color_rgb()) in colored
    assert "\x1b[2m" not in colored
    assert click.unstyle(colored) == _render(result, color=False)
