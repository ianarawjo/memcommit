"""Interactive frozen-plan review and exact Apply for Replace."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.clipboard import ClipboardError
from memcommit.context_targeting.tui.range_selection import ContextRangeSelectionState
from memcommit.context_targeting.tui.reach import render_context_reach
from memcommit.context_targeting.tui.selection import render_context_target_mode
from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.cli.replace import (
    render_replace_apply_result,
    render_replace_plan,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.exact_command_review import (
    render_exact_command_review,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.operations.replace.model import (
    ReplaceTuiOutcome,
    ReplaceTuiSetup,
)
from memcommit.replace_application import (
    FrozenReplacePlan,
    ReplaceApplyResult,
    ReplaceRequest,
)


ReplacePlanner = Callable[[ReplaceRequest], FrozenReplacePlan]
ReplaceApplier = Callable[[FrozenReplacePlan], ReplaceApplyResult]


def _choice(*values: tuple[str, str], selected: str) -> HorizontalChoiceState:
    return HorizontalChoiceState(
        tuple(HorizontalChoiceOption(uid, label) for uid, label in values),
        selected_uid=selected,
    )


def _flat_matches(plan: FrozenReplacePlan):
    return tuple(
        (context, match) for context in plan.contexts for match in context.matches
    )


def _render_plan_fragments(plan: FrozenReplacePlan, selected_index: int):
    matches = _flat_matches(plan)
    if not matches:
        return [
            ("class:report-label", "NO MATCHES\n"),
            (
                "class:report-neutral",
                "Apply records no checkpoint. The complete scanned scope remains reviewable.",
            ),
        ]
    fragments: list[tuple[str, str]] = []
    for index, (context, match) in enumerate(matches):
        focused = index == selected_index
        if focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                "class:detail-card.focused" if focused else "class:detail-card",
                f"[{index + 1}/{len(matches)}] {safe_terminal_text(context.context_name)}"
                f" · MEMORY {match.memory_uid[:8]}"
                f" · {len(match.spans)} OCCURRENCE(S)\n",
            )
        )
        fragments.extend(
            (
                (
                    "class:memory-diff.remove",
                    "- " + safe_terminal_text(match.before_content) + "\n",
                ),
                (
                    "class:memory-diff.add",
                    "+ " + safe_terminal_text(match.after_content),
                ),
            )
        )
        if index < len(matches) - 1:
            fragments.append(("", "\n\n"))
    return fragments


def _exact_review(plan: FrozenReplacePlan) -> ExactCommandReview:
    request = plan.request
    argv = ["mem", "replace", request.pattern, request.replacement]
    for name in request.target_names:
        argv.extend(("--context", name))
    argv.extend(
        (
            "--context-only",
            "--follow-embeds" if request.follow_embeds else "--exclude-embeds",
        )
    )
    if request.mode == "REGEX":
        argv.append("--regex")
    if request.ignore_case:
        argv.append("--ignore-case")
    argv.extend(("--apply", plan.plan_digest))
    effects = (
        (
            f"Replace {plan.occurrence_count} occurrence(s) in "
            f"{plan.changed_memory_count} Memory/ies."
        ),
        (
            "Create one Undo/Redo command unit across "
            f"{sum(bool(context.changed_matches) for context in plan.contexts)} "
            "changed Context(s)."
        ),
        "Reject the command if any frozen Context or namespace membership changed.",
    )
    return ExactCommandReview(tuple(argv), effects)


def run_replace_tui(
    request: ReplaceRequest | None,
    *,
    setup: ReplaceTuiSetup,
    prepare: ReplacePlanner,
    apply: ReplaceApplier,
    clipboard_writer: Callable[[str], None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ReplaceTuiOutcome | None:
    """Build, review, and explicitly Apply one exact deterministic plan."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Replace",
            snapshot_hint='Preview outside a terminal with mem replace "old" "new".',
        )
    if not isinstance(setup, ReplaceTuiSetup):
        raise TypeError("Replace TUI requires a ReplaceTuiSetup.")
    if request is not None and not isinstance(request, ReplaceRequest):
        raise TypeError("Replace TUI request must be a ReplaceRequest or None.")

    initial_targets = setup.initial_targets if request is None else request.target_names
    target_state = ContextRangeSelectionState.create(
        setup.names,
        current_name=setup.current_name,
        initial_target=initial_targets[0],
        multiple=True,
        include_descendants=False if request is None else request.include_descendants,
    )
    target_state.selection.replace(initial_targets)
    embed_choice = _choice(
        ("EXCLUDE", "EXCLUDE EMBEDS"),
        ("FOLLOW", "FOLLOW EMBEDS"),
        selected="FOLLOW"
        if request is not None and request.follow_embeds
        else "EXCLUDE",
    )
    mode_choice = _choice(
        ("LITERAL", "LITERAL"),
        ("REGEX", "REGEX"),
        selected="LITERAL" if request is None else request.mode,
    )
    case_choice = _choice(
        ("SENSITIVE", "CASE SENSITIVE"),
        ("IGNORE", "IGNORE CASE"),
        selected="IGNORE"
        if request is not None and request.ignore_case
        else "SENSITIVE",
    )
    plan: FrozenReplacePlan | None = None
    applied: ReplaceApplyResult | None = None
    plan_index = 0
    scope_row = 0
    status = "READY · ENTER A PATTERN AND REPLACEMENT"

    bindings = KeyBindings()
    pattern_area = TextArea(
        text="" if request is None else request.pattern,
        multiline=False,
        prompt="› ",
        height=1,
        name="replace-pattern",
    )
    replacement_area = TextArea(
        text="" if request is None else request.replacement,
        multiline=False,
        prompt="› ",
        height=1,
        name="replace-value",
    )

    def clear_plan() -> None:
        nonlocal plan, applied, plan_index, status
        plan = None
        applied = None
        plan_index = 0
        status = "READY · REQUEST CHANGED"

    pattern_area.buffer.on_text_changed += lambda _buffer: clear_plan()
    replacement_area.buffer.on_text_changed += lambda _buffer: clear_plan()

    def render_targets():
        return target_state.render_rows(
            focused=app.layout.has_focus(target_control),
            profile_label="ALL",
            profile_description="ALL LOCAL CONTEXTS",
        )

    target_control = FormattedTextControl(render_targets, focusable=True)
    target_window = Window(
        target_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_scope():
        focused = app.layout.has_focus(scope_control)
        fragments = render_context_target_mode(
            target_state.target_mode,
            focused=focused and scope_row == 0,
        )
        fragments.append(("", "\n"))
        fragments.extend(
            render_context_reach(
                target_state.reach,
                title="LEXICAL RANGE",
                focused=focused and scope_row == 1,
            )
        )
        for row, title, choice in (
            (2, "EMBEDDED CONTEXTS", embed_choice),
            (3, "MATCH", mode_choice),
            (4, "CASE", case_choice),
        ):
            fragments.append(("", "\n"))
            fragments.extend(
                render_horizontal_choice(
                    choice,
                    title=title,
                    focused=focused and scope_row == row,
                )
            )
        return fragments

    scope_control = FormattedTextControl(render_scope, focusable=True)

    def render_review():
        if applied is not None:
            return [("class:report-neutral", render_replace_apply_result(applied))]
        if plan is None:
            return [("", "Build a plan to inspect every exact before/after change.")]
        return _render_plan_fragments(plan, plan_index)

    review_control = FormattedTextControl(render_review, focusable=True)
    review_window = Window(
        review_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
        always_hide_cursor=True,
    )

    def render_todo():
        if applied is not None:
            return [("class:report-label", "APPLIED · ENTER TO CLOSE")]
        if plan is None:
            return [("", "BUILD A PLAN FIRST · ENTER ON PATTERN OR SCOPE")]
        return [
            ("class:report-neutral", render_exact_command_review(_exact_review(plan)))
        ]

    todo_control = FormattedTextControl(render_todo, focusable=True)

    def prepare_plan(_event=None):
        nonlocal plan, applied, plan_index, status
        targets = target_state.effective_names
        if not pattern_area.text:
            status = "PATTERN REQUIRED"
            app.layout.focus(pattern_area)
            return "HANDLED"
        if not targets:
            status = "SELECT AT LEAST ONE LOCAL CONTEXT"
            app.layout.focus(target_control)
            return "HANDLED"
        try:
            candidate = ReplaceRequest(
                pattern=pattern_area.text,
                replacement=replacement_area.text,
                target_names=targets,
                # Execute the exact visible checked set. This preserves an
                # independently unchecked descendant without hidden expansion.
                include_descendants=False,
                follow_embeds=embed_choice.selected_uid == "FOLLOW",
                mode=mode_choice.selected_uid,
                ignore_case=case_choice.selected_uid == "IGNORE",
            )
            plan = prepare(candidate)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status = safe_terminal_text(str(error)).upper()
            return "HANDLED"
        applied = None
        plan_index = 0
        status = (
            f"PLAN READY · {plan.changed_memory_count} CHANGED MEMORIES"
            f" · {plan.occurrence_count} OCCURRENCES"
        )
        app.layout.focus(review_control)
        return "HANDLED"

    def apply_or_close(event):
        nonlocal applied, status
        if applied is not None:
            event.app.exit(result=ReplaceTuiOutcome(plan, applied))
            return "HANDLED"
        if plan is None:
            status = "BUILD AND REVIEW A PLAN FIRST"
            event.app.layout.focus(pattern_area)
            return "HANDLED"
        try:
            applied = apply(plan)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            status = safe_terminal_text(str(error)).upper()
            return "HANDLED"
        status = "APPLIED" if applied.applied else "COMPLETE · NO CHANGES"
        return "HANDLED"

    def move_target(_event, delta):
        return "MOVED" if target_state.move_cursor(delta) else "BOUNDARY"

    def toggle_target(_event):
        if target_state.toggle_cursor():
            clear_plan()
        return "HANDLED"

    def move_scope(_event, delta):
        nonlocal scope_row
        candidate = scope_row + delta
        if not 0 <= candidate <= 4:
            return "BOUNDARY"
        scope_row = candidate
        return "MOVED"

    def move_review(_event, delta):
        nonlocal plan_index
        if plan is None or applied is not None:
            return "BOUNDARY"
        matches = _flat_matches(plan)
        if not matches or not 0 <= plan_index + delta < len(matches):
            return "BOUNDARY"
        plan_index += delta
        return "MOVED"

    surfaces = SurfaceFocusController(
        (
            FocusSurface("pattern", pattern_area, activate=prepare_plan),
            FocusSurface("replacement", replacement_area, activate=prepare_plan),
            FocusSurface(
                "targets",
                target_control,
                move_vertical=move_target,
                activate=toggle_target,
                on_vertical_enter=target_state.enter_from_boundary,
            ),
            FocusSurface(
                "scope",
                scope_control,
                move_vertical=move_scope,
                activate=prepare_plan,
                on_vertical_enter=lambda delta: _enter_scope(delta),
            ),
            FocusSurface("review", review_control, move_vertical=move_review),
            FocusSurface("todo", todo_control, activate=apply_or_close),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    def _enter_scope(delta: int) -> None:
        nonlocal scope_row
        scope_row = 0 if delta > 0 else 4

    @bindings.add("left", filter=has_focus(target_control), eager=True)
    def _target_left(event) -> None:
        target_state.collapse_cursor()
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(target_control), eager=True)
    def _target_right(event) -> None:
        target_state.expand_cursor()
        event.app.invalidate()

    def move_scope_choice(delta: int) -> None:
        changed = False
        if scope_row == 0:
            control, selection = target_state.move_target_mode(delta)
            changed = control or selection
        elif scope_row == 1:
            changed = target_state.move_reach(delta)
        elif scope_row == 2:
            changed = embed_choice.move(delta)
        elif scope_row == 3:
            changed = mode_choice.move(delta)
        else:
            changed = case_choice.move(delta)
        if changed:
            clear_plan()

    @bindings.add("left", filter=has_focus(scope_control), eager=True)
    def _scope_left(event) -> None:
        move_scope_choice(-1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(scope_control), eager=True)
    def _scope_right(event) -> None:
        move_scope_choice(1)
        event.app.invalidate()

    def copy_review(*, whole: bool) -> None:
        nonlocal status
        if plan is None or clipboard_writer is None:
            status = "NOTHING TO COPY"
            return
        matches = _flat_matches(plan)
        if whole or not matches:
            text = render_replace_plan(plan)
            label = "PLAN"
        else:
            context, match = matches[plan_index]
            text = "\n".join(
                (
                    f"{context.context_name} · MEMORY {match.memory_uid}",
                    "- " + match.before_content,
                    "+ " + match.after_content,
                )
            )
            label = "FOCUSED CHANGE"
        try:
            clipboard_writer(text)
        except ClipboardError as error:
            status = safe_terminal_text(str(error)).upper()
            return
        status = f"COPIED {label}"

    @bindings.add("y", filter=has_focus(review_control), eager=True)
    def _copy_focused(event) -> None:
        copy_review(whole=False)
        event.app.invalidate()

    @bindings.add("Y", filter=has_focus(review_control), eager=True)
    def _copy_whole(event) -> None:
        copy_review(whole=True)
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(
            result=None if plan is None else ReplaceTuiOutcome(plan, applied)
        )

    inputs_focused = has_focus(pattern_area) | has_focus(replacement_area)

    @bindings.add("q", filter=~inputs_focused, eager=True)
    def _close_q(event) -> None:
        event.app.exit(
            result=None if plan is None else ReplaceTuiOutcome(plan, applied)
        )

    header = Window(
        FormattedTextControl(
            [
                ("class:report-label", "MEM REPLACE\n"),
                (
                    "class:report-neutral",
                    "DETERMINISTIC · PLAN / REVIEW / ATOMIC APPLY · LOCAL CONTEXTS",
                ),
            ]
        ),
        height=2,
    )
    pattern_frame = build_focused_frame(
        pattern_area,
        title=" FIND ",
        is_focused=lambda: app.layout.has_focus(pattern_area),
        height=3,
    )
    replacement_frame = build_focused_frame(
        replacement_area,
        title=" REPLACE WITH · EMPTY REMOVES MATCHED TEXT ",
        is_focused=lambda: app.layout.has_focus(replacement_area),
        height=3,
    )
    target_frame = build_focused_frame(
        target_window,
        title=" CONTEXT · LOCAL CONTEXTS ONLY ",
        is_focused=lambda: app.layout.has_focus(target_control),
        height=Dimension(min=6, preferred=8, max=10),
    )
    scope_frame = build_focused_frame(
        Window(scope_control, height=5),
        title=" SCOPE ",
        is_focused=lambda: app.layout.has_focus(scope_control),
        height=7,
    )
    review_frame = build_focused_frame(
        review_window,
        title=" REVIEW ",
        is_focused=lambda: app.layout.has_focus(review_control),
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title=" TO DO ",
        is_focused=lambda: app.layout.has_focus(todo_control),
        height=Dimension(min=3, preferred=7, max=9),
    )
    status_window = Window(
        FormattedTextControl(lambda: [("class:memcommit.notification", status)]),
        height=1,
    )
    footer = Window(
        FormattedTextControl(
            "Tab/Shift-Tab move · Enter plan/select/apply · ←/→ change "
            "· y focused · Y plan · Esc/Q close"
        ),
        height=1,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(pattern_frame, separator_before=True),
        TuiRegion(replacement_frame),
        TuiRegion(target_frame, separator_before=True),
        TuiRegion(scope_frame, separator_before=True),
        TuiRegion(review_frame, separator_before=True),
        TuiRegion(todo_frame, separator_before=True),
        TuiRegion(status_window),
        TuiRegion(footer),
    )
    app = Application(
        layout=Layout(root, focused_element=pattern_area),
        key_bindings=bindings,
        full_screen=True,
        mouse_support=True,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        input=app_input,
        output=app_output,
    )
    return app.run()


__all__ = ["run_replace_tui"]
