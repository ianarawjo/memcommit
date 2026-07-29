"""Shared read-only presentation for validated semantic-operation results.

The common shell owns only information hierarchy, terminal safety, and case
navigation.  The operation adapter remains responsible for every semantic
judgment, reference, persisted artifact, provider call, and mutation.
"""
from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output

from memcommit.commands.tui_primitives import (
    TuiRegion,
    build_tui_frame,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.result_workbench import (
    ResultCase,
    ResultCaseDetail,
    ResultRef,
    ResultSection,
    ResultWorkbenchAdapter,
    ResultWorkbenchError,
    ResultWorkbenchView,
)


_COMPACT_TEXT_LIMIT = 120


def _compact(value: str, limit: int = _COMPACT_TEXT_LIMIT) -> str:
    normalized = " ".join(safe_terminal_text(value).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _section_text(section: ResultSection) -> str:
    text = safe_terminal_text(section.text)
    if section.state == "PRESENT":
        return text
    marker = (
        "(none reported under this operation's bounded contract)"
        if section.state == "NONE_REPORTED"
        else "(not recorded by this result artifact)"
    )
    return f"{marker}\n{text}" if text else marker


def _ref_text(reference: ResultRef) -> str:
    return (
        f"{safe_terminal_text(reference.kind)}:"
        f"{safe_terminal_text(reference.key)}"
    )


def _refs_text(refs: tuple[ResultRef, ...]) -> str:
    return ", ".join(_ref_text(reference) for reference in refs)


def _case_row(
    case: ResultCase,
    *,
    index: int,
    selected: bool,
    expanded: bool,
) -> list[tuple[str, str]]:
    marker = "▾" if selected and expanded else ("›" if selected else " ")
    fragments: list[tuple[str, str]] = []
    if selected:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.extend(
        [
            (
                "class:selected" if selected else "",
                (
                    f" {marker} {index:>2}. [{case.role}] "
                    f"{_compact(case.title)}\n"
                ),
            ),
            ("", f"       {_compact(case.summary)}\n"),
        ]
    )
    return fragments


def _case_detail_fragments(
    view: ResultWorkbenchView,
    detail: ResultCaseDetail,
) -> list[tuple[str, str]]:
    detail = view.validate_detail(detail)
    case = view.case(detail.case_uid)
    case_number = next(
        index
        for index, candidate in enumerate(view.cases, start=1)
        if candidate.uid == case.uid
    )
    fragments: list[tuple[str, str]] = [
        (
            "class:section",
            (
                f"\n CASE DETAIL · {case_number}/{len(view.cases)} · "
                f"{case.role}\n"
            ),
        ),
        ("class:case-title", f" {safe_terminal_text(case.title)}\n"),
        ("class:detail-heading", "\n WHY SELECTED\n"),
        ("", f" {safe_terminal_text(case.why_selected)}\n"),
        ("class:detail-heading", "\n OPERATION DETAIL\n"),
    ]
    # Detail blocks are operation-authored and deliberately retain their
    # supplied order.  The common layer must not reinterpret their semantics.
    for block in detail.blocks:
        fragments.extend(
            [
                (
                    "class:block-heading",
                    f" {safe_terminal_text(block.heading)}\n",
                ),
                ("", f" {safe_terminal_text(block.text)}\n"),
            ]
        )
        if block.refs:
            fragments.append(
                ("class:trace", f" refs · {_refs_text(block.refs)}\n")
            )
    fragments.extend(
        [
            ("class:detail-heading", "\n TRACE\n"),
            (
                "class:trace",
                f" EVIDENCE   · {_refs_text(detail.evidence_refs)}\n",
            ),
            (
                "class:trace",
                f" → JUDGMENT · {_refs_text(detail.judgment_refs)}\n",
            ),
        ]
    )
    if detail.outcome_refs:
        fragments.append(
            (
                "class:trace",
                f" → OUTCOME  · {_refs_text(detail.outcome_refs)}\n",
            )
        )
    if detail.unresolved_refs:
        fragments.append(
            (
                "class:trace",
                f" → UNRESOLVED · {_refs_text(detail.unresolved_refs)}\n",
            )
        )
    return fragments


def _screen_fragments(
    view: ResultWorkbenchView,
    *,
    selected_index: int,
    detail: ResultCaseDetail | None,
) -> list[tuple[str, str]]:
    metrics = "".join(
        (
            f" · {safe_terminal_text(metric.label)}="
            f"{metric.value:,}"
        )
        for metric in view.metrics
    )
    fragments: list[tuple[str, str]] = [
        (
            "class:title",
            (
                f" RESULT · {safe_terminal_text(view.operation)} · "
                f"{safe_terminal_text(view.title)}\n"
            ),
        ),
        (
            "class:metadata",
            f" STATUS · {safe_terminal_text(view.status)}{metrics}\n",
        ),
        ("class:section", "\n WHAT MEM UNDERSTOOD\n"),
        ("", f" {_section_text(view.understood)}\n"),
        ("class:section", "\n WHAT HAPPENED\n"),
        ("", f" {_section_text(view.happened)}\n"),
        ("class:section", "\n WHAT REMAINS UNRESOLVED\n"),
        ("", f" {_section_text(view.unresolved)}\n"),
        ("class:section", "\n REPRESENTATIVE / BOUNDARY CASES\n"),
    ]
    if not view.cases:
        fragments.append(("", "  (no inspection cases recorded)\n"))
        return fragments
    expanded_uid = detail.case_uid if detail is not None else None
    for index, case in enumerate(view.cases):
        fragments.extend(
            _case_row(
                case,
                index=index + 1,
                selected=index == selected_index,
                expanded=case.uid == expanded_uid,
            )
        )
    if detail is not None:
        fragments.extend(_case_detail_fragments(view, detail))
    return fragments


def _fragments_text(fragments: list[tuple[str, str]]) -> str:
    return "".join(text for style, text in fragments if style != "[SetCursorPosition]")


def render_result_workbench_snapshot(
    view: ResultWorkbenchView,
    *,
    selected_case_uid: str | None = None,
    detail: ResultCaseDetail | None = None,
) -> str:
    """Render one deterministic result frame without ANSI control sequences.

    ``detail`` is accepted only when it belongs to the exact immutable
    artifact represented by ``view``.  This makes the pure snapshot renderer
    useful both for non-TTY CLI output and for focused integration tests.
    """
    snapshot = _fragments_text(
        result_workbench_fragments(
            view,
            selected_case_uid=selected_case_uid,
            detail=detail,
        )
    )
    return snapshot.rstrip() + "\n"


def result_workbench_fragments(
    view: ResultWorkbenchView,
    *,
    selected_case_uid: str | None = None,
    detail: ResultCaseDetail | None = None,
) -> list[tuple[str, str]]:
    """Return the validated common frame for embedding in another workbench.

    The cursor marker remains attached to the selected compact case, allowing
    an operation-owned shell to reuse the exact information hierarchy without
    copying its presentation or semantic validation rules.
    """
    if not isinstance(view, ResultWorkbenchView):
        raise ResultWorkbenchError("Invalid result workbench view.")
    if detail is not None:
        detail = view.validate_detail(detail)
        if (
            selected_case_uid is not None
            and selected_case_uid != detail.case_uid
        ):
            raise ResultWorkbenchError(
                "Expanded result detail does not match the selected case."
            )
        selected_case_uid = detail.case_uid
    if selected_case_uid is None:
        selected_index = 0
    else:
        selected_case = view.case(selected_case_uid)
        selected_index = view.cases.index(selected_case)
    return _screen_fragments(
        view,
        selected_index=selected_index,
        detail=detail,
    )


def run_result_workbench_shell(
    adapter: ResultWorkbenchAdapter,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ResultWorkbenchView:
    """Navigate one frozen result projection without changing operation state."""
    if require_tty:
        require_interactive_terminal(
            "Result workbench",
            snapshot_hint=(
                "Use the operation's snapshot option for non-interactive "
                "inspection."
            ),
        )
    # Freeze one validated operation projection for the entire UI session.
    # Detail lookups must match this digest; an adapter cannot quietly switch
    # artifacts while the person is inspecting a case.
    view = adapter.view()
    if not isinstance(view, ResultWorkbenchView):
        raise ResultWorkbenchError("Invalid result workbench view.")

    selected = {"index": 0}
    expanded = {"detail": None}
    status = {"value": ""}
    bindings = KeyBindings()

    body_control = FormattedTextControl(
        lambda: _screen_fragments(
            view,
            selected_index=selected["index"],
            detail=expanded["detail"],
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def collapse() -> None:
        expanded["detail"] = None
        status["value"] = ""

    def move(delta: int) -> None:
        if not view.cases:
            return
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(view.cases) - 1),
        )
        collapse()

    @bindings.add("down", filter=has_focus(body_control))
    def _down(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(body_control))
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(body_control))
    def _expand(event) -> None:
        if not view.cases:
            status["value"] = "No inspection case is available."
            event.app.invalidate()
            return
        case = view.cases[selected["index"]]
        current = expanded["detail"]
        if current is not None and current.case_uid == case.uid:
            collapse()
            event.app.invalidate()
            return
        try:
            detail = adapter.case_detail(case.uid)
            expanded["detail"] = view.validate_detail(detail)
            status["value"] = ""
        except ResultWorkbenchError as error:
            expanded["detail"] = None
            status["value"] = f"Cannot open case: {error}"
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(body_control))
    @bindings.add("backspace", filter=has_focus(body_control))
    def _collapse(event) -> None:
        collapse()
        event.app.invalidate()

    @bindings.add("q", filter=has_focus(body_control), eager=True)
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        event.app.exit(result=view)

    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status['value']}"
                if status["value"]
                else (
                    " ↑/↓ case  Enter expand  Esc/Backspace collapse  "
                    "Q quit · read-only "
                )
            )
        ),
        height=1,
        dont_extend_height=True,
    )
    application: Application[ResultWorkbenchView] = Application(
        layout=Layout(
            build_tui_frame(
                TuiRegion(body),
                TuiRegion(footer),
            ),
            focused_element=body_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
    )
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return view
