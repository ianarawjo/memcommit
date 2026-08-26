"""Frozen-plan review and exact Apply for deterministic Merge."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
    render_exact_command_review,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerController,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.operations.merge.application import (
    FrozenMergePlan,
    MergeError,
    MergeReach,
    MergeResult,
)
from memcommit.operations.merge.runtime import merge_summary
from memcommit.reviewing.session_navigation import SessionWorkbenchNavigation


def merge_exact_command_review(
    source_name: str,
    target_name: str,
    *,
    recursive: bool,
) -> ExactCommandReview:
    """Describe one exact deterministic union and its complete reach boundary."""

    scope = (
        "matching lexical descendants by relative path"
        if recursive
        else "the two selected Context roots only"
    )
    target_effect = (
        f"Target subtree '{target_name}' may update existing matching Contexts "
        "and create Source-only relative paths."
        if recursive
        else f"Only direct items in Target Context '{target_name}' may change."
    )
    return ExactCommandReview(
        argv=(
            "mem",
            "merge",
            source_name,
            target_name,
            "--recursive" if recursive else "--direct",
        ),
        effects=(
            f"Merge {scope} into selected Target '{target_name}'.",
            target_effect,
            "Classify every Source item as NEW, UNCHANGED, or required CONFLICT.",
            "Resolve conflicts only by keeping Target or taking Source.",
            "No semantic reconciliation and no deletion propagation.",
        ),
    )


def merge_plan_exact_command_review(plan: FrozenMergePlan) -> ExactCommandReview:
    """Bind the exact command to the already frozen Context plan."""

    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Merge plan review requires a FrozenMergePlan.")
    base = merge_exact_command_review(
        plan.source_name,
        plan.target_name,
        recursive=plan.request.reach is MergeReach.DESCENDANTS,
    )
    created = sum(context.target_created for context in plan.contexts)
    return ExactCommandReview(
        argv=base.argv,
        effects=(
            f"Apply this {plan.request.reach.value} plan to "
            f"{len(plan.contexts)} Context mapping(s).",
            f"Create {created} Source-only Target path(s).",
            f"Add {merge_summary(plan.additions)}; retain "
            f"{len(plan.unchanged)} unchanged item(s); resolve "
            f"{len(plan.conflicts)} conflict(s); record "
            f"{len(plan.contexts)} checkpoint(s).",
            "Apply only if the selected Contexts are unchanged.",
            "Save all changes together, or save none.",
        ),
    )


def project_merge_plan(plan: FrozenMergePlan) -> SemanticViewerDocument:
    """Project every frozen Source/Target mapping without parsing CLI text."""

    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Merge plan projection requires a FrozenMergePlan.")
    created = sum(context.target_created for context in plan.contexts)
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            uid="MERGE:PLAN:SUMMARY",
            kind="SUMMARY",
            block=SemanticViewerBlock(
                (
                    (
                        "class:title",
                        f"MERGE PLAN · {safe_terminal_text(plan.source_name)} → {safe_terminal_text(plan.target_name)}\n",
                    ),
                    ("class:report-label", "STATUS · READY FOR REVIEW\n"),
                    (
                        "class:viewer-body",
                        f"RANGE · {plan.request.reach.value}\n"
                        f"CONTEXTS · {len(plan.contexts)} · CREATE {created}\n"
                        f"ADDITIONS · {safe_terminal_text(merge_summary(plan.additions))}\n"
                        f"UNCHANGED · {len(plan.unchanged)}\n"
                        f"REQUIRED CONFLICTS · {len(plan.conflicts)}\n"
                        f"CHECKPOINTS · {len(plan.contexts)}\n\n",
                    ),
                )
            ),
        )
    ]
    for index, context in enumerate(plan.contexts, start=1):
        target_state = "WILL CREATE" if context.target_created else "EXISTING"
        fragments: list[tuple[str, str]] = [
            (
                "class:section",
                f"MAPPING {index}/{len(plan.contexts)} · "
                f"{safe_terminal_text(context.source_name)} → "
                f"{safe_terminal_text(context.target_name)}\n",
            ),
            (
                "class:viewer-body",
                f"TARGET · {target_state}\n"
                f"NEW · {safe_terminal_text(merge_summary(context.additions))}\n"
                f"UNCHANGED · {len(context.unchanged)}\n"
                f"CONFLICT · {len(context.conflicts)}\n",
            ),
        ]
        if context.additions:
            fragments.append(("class:report-label", "ITEMS\n"))
            for addition in context.additions:
                style = (
                    "class:memory-object"
                    if addition.kind.value == "MEMORY"
                    else "class:viewer-body"
                )
                fragments.append(
                    (
                        style,
                        f"  {addition.kind.value} · "
                        f"[{safe_terminal_text(addition.uid[:8])}]\n",
                    )
                )
        fragments.append(("", "\n"))
        sections.append(
            SemanticViewerSection(
                uid=f"MERGE:PLAN:CONTEXT:{index}",
                kind="CONTEXT_PLAN",
                row_index=index - 1,
                block=SemanticViewerBlock(tuple(fragments), anchor="both"),
            )
        )
    return SemanticViewerDocument(tuple(sections))


def run_merge_plan_review(
    plan: FrozenMergePlan,
    *,
    apply_plan: Callable[[FrozenMergePlan], MergeResult],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MergeResult | None:
    """Review one complete frozen plan and apply only that exact plan."""

    if not isinstance(plan, FrozenMergePlan):
        raise TypeError("Interactive Merge review requires a FrozenMergePlan.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Merge plan review",
            snapshot_hint="Pass SOURCE with --direct or --recursive outside a terminal.",
        )

    document = project_merge_plan(plan)
    controller = SemanticViewerController(SessionWorkbenchNavigation())
    bindings = KeyBindings()
    result: MergeResult | None = None
    status = {"value": ""}
    last_error: dict[str, Exception | None] = {"value": None}

    viewer_control = FormattedTextControl(
        lambda: controller.render(
            document,
            viewer_focused=get_app().layout.has_focus(viewer_control),
        ),
        focusable=True,
        show_cursor=False,
    )
    viewer_frame = build_focused_frame(
        Window(
            viewer_control,
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        ),
        title="PLAN · CONTEXT MAPPINGS",
        is_focused=lambda: get_app().layout.has_focus(viewer_control),
        height=Dimension(min=18, weight=1),
    )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        cursor = [("[SetCursorPosition]", "")] if focused else []
        if result is None:
            return [
                (
                    "class:report-neutral",
                    render_exact_command_review(merge_plan_exact_command_review(plan)),
                ),
                ("", "\n\n"),
                *cursor,
                (
                    focused_control_style(focused=focused),
                    "[ PRESS ENTER TO APPLY THE MERGE PLAN ]",
                ),
            ]
        created = sum(context.target_created for context in result.contexts)
        no_target_change = (
            not result.additions
            and not created
            and not any(
                resolution.decision.value == "TAKE_SOURCE"
                for resolution in result.resolutions
            )
        )
        outcome_line = "OUTCOME · NO TARGET CHANGE\n" if no_target_change else ""
        return [
            ("class:report-label", "STATUS · SUCCESS\n"),
            (
                "class:report-neutral",
                outcome_line
                + f"SOURCE · {safe_terminal_text(result.source_name)}\n"
                f"TARGET · {safe_terminal_text(result.target_name)}\n"
                f"RANGE · {result.reach.value}\n"
                f"CONTEXTS · {len(result.contexts)} · CREATED {created}\n"
                f"ADDED · {safe_terminal_text(merge_summary(result.additions))}\n"
                f"UNCHANGED · {len(result.unchanged)}\n"
                f"CHECKPOINTS · {len(result.checkpoint_uids)}\n"
                "RECOVERY · mem undo\n\n",
            ),
            *cursor,
            (
                focused_control_style(focused=focused),
                "[ PRESS ENTER TO CLOSE ]",
            ),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · REVIEWED PLAN",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension(min=15, max=18),
    )
    header = Window(
        FormattedTextControl(" MEM MERGE · REVIEW PLAN"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if result is not None:
            return " Enter/Esc/Q close · durable receipt shown above"
        if get_app().layout.has_focus(viewer_control):
            return " ↑/↓ mapping · Home/End · Tab exact plan · Esc cancel"
        return " Enter apply plan · ↑ Viewer · Tab Viewer · Esc cancel"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(viewer_frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[MergeResult | None] = Application(
        layout=Layout(root, focused_element=viewer_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_viewer(_event, delta: int) -> SurfaceMoveResult:
        before = controller.current(document)
        after = controller.move(document, delta)
        return "MOVED" if after != before else "BOUNDARY"

    def submit(event) -> SurfaceActionResult:
        nonlocal result
        if result is not None:
            event.app.exit(result=result)
            return "HANDLED"
        try:
            completed = apply_plan(plan)
            if not isinstance(completed, MergeResult):
                raise TypeError("Merge application returned an invalid result.")
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status["value"] = f"Merge failed · {error}"
            last_error["value"] = error
            return "HANDLED"
        result = completed
        status["value"] = ""
        last_error["value"] = None
        event.app.layout.focus(todo_control)
        event.app.invalidate()
        return "HANDLED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "VIEWER",
                viewer_control,
                move_vertical=move_viewer,
            ),
            FocusSurface(
                "TO_DO",
                todo_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=submit,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("home", eager=True)
    def _home(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            controller.home(document)
            event.app.invalidate()

    @bindings.add("end", eager=True)
    def _end(event) -> None:
        if event.app.layout.has_focus(viewer_control):
            controller.end(document)
            event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=result)

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        dispatch_tui_back(event, close=close)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        close(event)

    try:
        outcome = app.run()
    except (EOFError, KeyboardInterrupt):
        outcome = result
    if outcome is None and last_error["value"] is not None:
        raise MergeError(f"Interactive Merge failed: {last_error['value']}")
    return outcome
