"""Typed projection and shared-workbench contracts for Distill."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.context import Context, Memory
from memcommit.context_targeting.tui.picker import ContextMemoryRow
from memcommit.distill import DistillAnalysis, DistilledRule
from memcommit.distill_goal_fit import DistillGoalFit
from memcommit.application.operations.distill.application import (
    DistillRequest,
    DistillResult,
)
from memcommit.interfaces.tui.operations.distill import (
    DistillTuiSetup,
    project_distill_clipboard,
    project_distill_result,
    run_distill_tui,
)
from memcommit.summarize import collect_summary_scope
from memcommit.application.operations.summarize.application import FrozenSummarySource


def _result(*, descendants: bool = False) -> DistillResult:
    context = Context(
        uid="00000000-0000-4000-8000-000000000001",
        name="distill/cases",
    )
    context.add(
        Memory(
            uid="00000000-0000-4000-8000-000000000011",
            content="A quiet setting supported a long conversation.",
        )
    )
    frame = collect_summary_scope(
        (context,),
        root_context_uid=context.uid,
        root_context_name=context.name,
        include_descendants=descendants,
        follow_embeds=descendants,
    )
    analysis = DistillAnalysis(
        uid="00000000-0000-4000-8000-000000000021",
        source=frame,
        goal="Focus on settings suitable for conversation.",
        overview="The example supports one bounded preference.",
        rules=(
            DistilledRule(
                uid="00000000-0000-4000-8000-000000000031",
                content="Prefer a quiet setting when conversation is the purpose.",
                rationale="The supplied Case proposition supports this condition.",
                support_memory_uids=(
                    "00000000-0000-4000-8000-000000000011",
                ),
                boundary_memory_uids=(),
            ),
        ),
        outside_memory_uids=(),
        goal_fit=DistillGoalFit(
            verdict="FIT",
            reason="The proposed Rule is relevant to and compatible with the Goal.",
            considered_rule_uids=(
                "00000000-0000-4000-8000-000000000031",
            ),
            material_rule_uids=(),
        ),
    )
    return DistillResult(
        analysis=analysis,
        frozen_source=FrozenSummarySource(frame=frame, token="test"),
    )


def _setup(*, range_mode: str = "EXACT") -> DistillTuiSetup:
    return DistillTuiSetup(
        names=("distill/cases",),
        selected_context="distill/cases",
        initial_range_mode=range_mode,
        current_context="distill/cases",
    )


def test_distill_projects_operation_meaning_over_shared_viewer() -> None:
    document = project_distill_result(_result())

    assert [section.uid for section in document.sections] == [
        "DISTILL:TITLE",
        "DISTILL:STATUS",
        "DISTILL:GOAL",
        "DISTILL:OVERVIEW",
        "DISTILL:RULE:0",
        "DISTILL:OUTSIDE",
    ]
    rendered = "".join(
        text for _style, text in document.render(focused_uid="DISTILL:TITLE")
    )
    assert "GOAL · RELEVANCE FOCUS ONLY" in rendered
    assert "SOURCE OVERVIEW" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "Prefer a quiet setting" in rendered
    assert "STATUS · PROPOSAL" in rendered


def test_distill_clipboard_keeps_focused_rule_and_whole_proposal_distinct() -> None:
    result = _result()

    focused = project_distill_clipboard(
        result,
        focused_uid="DISTILL:RULE:0",
        whole_document=False,
    )
    complete = project_distill_clipboard(result, whole_document=True)

    assert focused.label == "Distill Rule 1"
    assert focused.text.startswith("RULE 1 · Prefer a quiet setting")
    assert "WHAT MEM UNDERSTOOD" not in focused.text
    assert complete.label == "complete Distill proposal"
    assert "SOURCE OVERVIEW" in complete.text


def test_distill_tui_executes_only_after_explicit_run() -> None:
    requests: list[DistillRequest] = []

    def execute(request: DistillRequest) -> DistillResult:
        requests.append(request)
        return _result(descendants=request.include_descendants)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("sq")
        returned = run_distill_tui(
            DistillRequest(
                context_locator="distill/cases",
                goal="Focus on settings suitable for conversation.",
            ),
            setup=_setup(),
            execute=execute,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result()
    assert requests == [
        DistillRequest(
            context_locator="distill/cases",
            goal="Focus on settings suitable for conversation.",
        )
    ]


def test_distill_tui_cancels_before_provider_execution() -> None:
    requests: list[DistillRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_distill_tui(
            DistillRequest(context_locator="distill/cases"),
            setup=_setup(),
            execute=lambda request: requests.append(request) or _result(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert requests == []


def test_distill_tui_lowercase_m_loads_only_the_focused_context() -> None:
    loaded: list[str] = []

    def load(name: str) -> tuple[ContextMemoryRow, ...]:
        loaded.append(name)
        return (ContextMemoryRow(name, f"Memory from {name}"),)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("mq")
        returned = run_distill_tui(
            DistillRequest(context_locator="distill/cases"),
            setup=DistillTuiSetup(
                names=("distill/cases", "distill/other"),
                selected_context="distill/cases",
                current_context="distill/cases",
                memory_loader=load,
            ),
            execute=lambda _request: (_ for _ in ()).throw(
                AssertionError("preview must not execute Distill")
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert loaded == ["distill/cases"]


def test_distill_tui_uppercase_m_loads_every_visible_context() -> None:
    loaded: list[str] = []

    def load(name: str) -> tuple[ContextMemoryRow, ...]:
        loaded.append(name)
        return (ContextMemoryRow(name, f"Memory from {name}"),)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Mq")
        returned = run_distill_tui(
            DistillRequest(context_locator="distill/cases"),
            setup=DistillTuiSetup(
                names=("distill/cases", "distill/other"),
                selected_context="distill/cases",
                current_context="distill/cases",
                memory_loader=load,
            ),
            execute=lambda _request: (_ for _ in ()).throw(
                AssertionError("preview must not execute Distill")
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert loaded == ["distill/cases", "distill/other"]


def test_distill_tui_has_no_ambiguous_both_range() -> None:
    requests: list[DistillRequest] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Z\x1b[Csq")
        returned = run_distill_tui(
            DistillRequest(context_locator="distill/cases"),
            setup=_setup(),
            execute=lambda request: requests.append(request)
            or _result(descendants=request.include_descendants),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result(descendants=True)
    assert requests == [
        DistillRequest(
            context_locator="distill/cases",
            include_descendants=True,
            follow_embeds=True,
        )
    ]


def test_distill_tui_keeps_caller_frozen_source_out_of_targeting_controls() -> None:
    requests: list[DistillRequest] = []
    exact = DistillRequest(
        context_locator="distill/cases",
        goal="Use the exact Ground Goal.",
    )
    with create_pipe_input() as pipe_input:
        # Shift-Tab and Right would change focus/reach in an editable setup.
        # A locked Ground setup keeps Summary focused and submits the exact input.
        pipe_input.send_text("\x1b[Z\x1b[Csq")
        returned = run_distill_tui(
            exact,
            setup=DistillTuiSetup(
                names=("distill/cases",),
                selected_context="distill/cases",
                current_context="distill/cases",
                source_locked=True,
            ),
            execute=lambda request: requests.append(request) or _result(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result()
    assert requests == [exact]


def test_distill_tui_y_and_uppercase_y_copy_rule_then_all() -> None:
    copied: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("s" + "\x1b[B" * 4 + "yYq")
        returned = run_distill_tui(
            DistillRequest(context_locator="distill/cases"),
            setup=_setup(),
            execute=lambda _request: _result(),
            clipboard_writer=copied.append,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == _result()
    assert copied[0].startswith("RULE 1 · Prefer a quiet setting")
    assert "WHAT MEM UNDERSTOOD" not in copied[0]
    assert "SOURCE OVERVIEW" in copied[1]
