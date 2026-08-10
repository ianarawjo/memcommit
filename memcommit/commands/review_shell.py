"""Prompt-toolkit controller and deterministic snapshot for semantic review."""
from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import TextArea

from memcommit.commands.tui_primitives import (
    TuiRegion,
    bind_case_insensitive_key,
    build_tui_frame,
    dispatch_tui_back,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.context import Context, Memory
from memcommit.review import (
    REVIEW_RESPONSE_CHAR_LIMIT,
    ReviewItem,
    ReviewSession,
)


RESPONSE_LABEL = "REFINE, COMMENT, OR ENTER A DIFFERENT READING"
ATOMIZE_RESPONSE_LABEL = RESPONSE_LABEL


class ReviewCancelled(Exception):
    """The interactive review closed normally without applying Memories."""


def visible_ordinal_index(selector: str, item_count: int) -> int | None:
    """Resolve only the canonical spelling of a visible 1-based ordinal.

    A UUID prefix can legally contain digits only. Treating every decimal
    string as an ordinal makes an eight-character prefix such as ``12345678``
    unreachable, so out-of-range and zero-padded decimals must remain
    available to the ordinary UID-prefix resolver.
    """
    if not selector.isdecimal():
        return None
    ordinal = int(selector)
    if selector != str(ordinal) or not 1 <= ordinal <= item_count:
        return None
    return ordinal - 1


def _direct_memory_map(ctx: Context) -> dict[str, Memory]:
    return {
        item.uid: item
        for item in ctx.iter_items()
        if isinstance(item, Memory)
    }


def _item_number(session: ReviewSession, item: ReviewItem) -> int:
    return next(
        index
        for index, candidate in enumerate(session.ordered_items(), start=1)
        if candidate.uid == item.uid
    )


def _status_marker(session: ReviewSession, item: ReviewItem) -> str:
    response = session.responses.get(item.uid)
    return "✓" if response is not None and response.answered else "·"


def _response_label(session: ReviewSession) -> str:
    return (
        ATOMIZE_RESPONSE_LABEL
        if session.kind == "atomize"
        else RESPONSE_LABEL
    )


def _empty_finding_label(session: ReviewSession) -> str:
    return (
        "no uncertain atomize items"
        if session.kind == "atomize"
        else "no actionable ambiguity findings"
    )


def _render_list_text(session: ReviewSession) -> str:
    current = session.current_item()
    lines = ["ISSUES"]
    for index, item in enumerate(session.ordered_items(), start=1):
        pointer = "›" if current is not None and item.uid == current.uid else " "
        lines.append(
            f"{pointer} {index:>2}. {_status_marker(session, item)} "
            f"{item.interpretation}/{item.clarification} "
            f"[{safe_terminal_text(item.uid[:8])}]"
        )
    if len(lines) == 1:
        lines.append(f"  ({_empty_finding_label(session)})")
    return "\n".join(lines)


def _render_detail_text(
    session: ReviewSession,
    memories: dict[str, Memory],
) -> str:
    item = session.current_item()
    if item is None:
        return (
            f"{_empty_finding_label(session).capitalize()}.\n\n"
            "The review session is still saved as a read-only record."
        )
    source = memories.get(item.source_uids[0])
    source_text = (
        safe_terminal_text(source.content)
        if source is not None
        else "[source Memory unavailable]"
    )
    selected_index = session.selected_choice_index(item)
    issue_label = (
        "ATOMIZE UNCERTAINTY"
        if session.kind == "atomize"
        else "AMBIGUITY"
    )
    lines = [
        f"{issue_label} {_item_number(session, item)}/{len(session.items)}",
        "",
        f"SOURCE [{safe_terminal_text(item.source_uids[0][:8])}]",
        source_text,
        "",
        "CLASSIFICATION",
        f"{item.interpretation} · {item.clarification}",
        "",
        (
            "WHY ATOMIZE IS BLOCKED"
            if session.kind == "atomize"
            else "WHY THIS IS UNCLEAR"
        ),
        safe_terminal_text(item.reason),
    ]
    if item.question:
        lines.extend(
            [
                "",
                "CLARIFICATION PROMPT",
                safe_terminal_text(item.question),
            ]
        )
    if item.choices:
        lines.extend(["", "READING OPTIONS"])
        for index, choice in enumerate(item.choices, start=1):
            pointer = "›" if selected_index == index - 1 else " "
            lines.append(
                f"{pointer} {index}. [{safe_terminal_text(choice.label)}] "
                f"{safe_terminal_text(choice.text)}"
            )
    return "\n".join(lines)


def render_review_snapshot(session: ReviewSession, ctx: Context) -> str:
    """Render one stable text frame without ANSI control sequences."""
    memories = _direct_memory_map(ctx)
    item = session.current_item()
    response = (
        session.response_for(item.uid)
        if item is not None
        else None
    )
    response_text = ""
    if response is not None and response.text:
        response_text = safe_terminal_text(response.text)
    return "\n".join(
        [
            (
                f"REVIEW · {session.kind} · Context: "
                f"{safe_terminal_text(session.context_name)}"
            ),
            (
                f"Order: {session.sort_mode} · "
                f"Answered: {session.answered_count}/{len(session.items)}"
            ),
            "",
            _render_list_text(session),
            "",
            _render_detail_text(session, memories),
            "",
            _response_label(session),
            f"> {response_text}",
            "",
            (
                "SOURCE means canonical Context order; Memory creation "
                "timestamps are not recorded."
            ),
            "No Memory changes have been applied.",
        ]
    )


def run_review_shell(
    session: ReviewSession,
    ctx: Context,
    *,
    save: Callable[[ReviewSession], None],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ReviewSession:
    """Run one resumable semantic-review adapter and return its staged state."""
    if require_tty:
        require_interactive_terminal(
            "Review",
            snapshot_hint=(
                "Use 'mem review --snapshot' to inspect the saved session."
            ),
        )

    memories = _direct_memory_map(ctx)
    bindings = KeyBindings()
    status_message = {"value": ""}

    list_control = FormattedTextControl(
        text=lambda: _render_list_text(session),
        focusable=True,
        show_cursor=False,
    )
    detail_control = FormattedTextControl(
        text=lambda: _render_detail_text(session, memories),
        focusable=False,
        show_cursor=False,
    )
    response_area = TextArea(
        text="",
        multiline=True,
        wrap_lines=True,
        scrollbar=True,
        height=Dimension(min=3, max=5),
        prompt="> ",
    )

    detail_window = Window(
        detail_control,
        wrap_lines=True,
    )
    response_label = Window(
        FormattedTextControl(_response_label(session)),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    detail_panel = HSplit(
        [
            detail_window,
            Window(height=1, char="─"),
            response_label,
            response_area,
        ]
    )
    # This legacy entry point remains callable for compatibility, but its
    # presentation follows the same one-column frame rule as the current
    # Resolution Session used by the CLI.
    body = build_tui_frame(
        TuiRegion(
            Window(
                list_control,
                height=Dimension(min=5, preferred=8, max=10),
                wrap_lines=False,
            )
        ),
        TuiRegion(detail_panel, separator_before=True),
    )
    header = Window(
        FormattedTextControl(
            lambda: [
                (
                    "class:title",
                    (
                        f" mem review · {session.kind} · "
                        f"{safe_terminal_text(session.context_name)} "
                    ),
                ),
                (
                    "",
                    (
                        f"sort={session.sort_mode} "
                        f"answered={session.answered_count}/{len(session.items)}"
                    ),
                ),
            ]
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status_message['value']}"
                if status_message["value"]
                else (
                    " ←/→ issue  "
                    + (
                        "↑/↓ reading  1-5 choose  "
                        if session.kind == "ambiguities"
                        else ""
                    )
                    + "Enter input  "
                    "Esc back/quit  F2/Ctrl-S save+next  S sort  Q quit "
                )
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def current_response_text() -> str:
        item = session.current_item()
        if item is None:
            return ""
        return session.response_for(item.uid).text

    def load_response() -> None:
        response_area.text = current_response_text()
        response_area.buffer.cursor_position = len(response_area.text)

    def capture_response() -> bool:
        item = session.current_item()
        if item is None:
            return True
        if len(response_area.text) > REVIEW_RESPONSE_CHAR_LIMIT:
            status_message["value"] = (
                "Response is too long to save "
                f"({len(response_area.text):,}/"
                f"{REVIEW_RESPONSE_CHAR_LIMIT:,} characters)."
            )
            return False
        session.response_for(item.uid).text = response_area.text
        status_message["value"] = ""
        return True

    def persist() -> bool:
        if not capture_response():
            return False
        save(session)
        return True

    def move(delta: int) -> None:
        if not capture_response():
            return
        session.move(delta)
        load_response()
        save(session)

    def move_choice(delta: int) -> None:
        item = session.current_item()
        if item is None or not item.choices:
            return
        current = session.selected_choice_index(item)
        next_index = 0 if current is None else current + delta
        next_index = max(0, min(next_index, len(item.choices) - 1))
        session.select_choice(next_index)
        save(session)

    @bindings.add("right", filter=has_focus(list_control))
    def _next_issue(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(list_control))
    def _previous_issue(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(list_control))
    def _next_reading(event) -> None:
        move_choice(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(list_control))
    def _previous_reading(event) -> None:
        move_choice(-1)
        event.app.invalidate()

    for number in range(1, 6):

        @bindings.add(str(number), filter=has_focus(list_control))
        def _choose_number(event, number=number) -> None:
            item = session.current_item()
            if item is not None and number <= len(item.choices):
                session.select_choice(number - 1)
                save(session)
                event.app.invalidate()

    @bindings.add("0", filter=has_focus(list_control))
    def _clear_choice(event) -> None:
        session.select_choice(None)
        save(session)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(list_control))
    @bindings.add("tab", filter=has_focus(list_control))
    def _focus_response(event) -> None:
        event.app.layout.focus(response_area)

    @bindings.add("tab", filter=has_focus(response_area))
    def _focus_review(event) -> None:
        if not capture_response():
            event.app.invalidate()
            return
        save(session)
        event.app.layout.focus(list_control)
        event.app.invalidate()

    @bindings.add("f2", eager=True)
    @bindings.add("c-s", eager=True)
    def _save_and_next(event) -> None:
        if not persist():
            event.app.invalidate()
            return
        event.app.layout.focus(list_control)
        session.move(1)
        load_response()
        save(session)
        event.app.invalidate()

    @bindings.add("s", filter=has_focus(list_control))
    def _toggle_sort(event) -> None:
        if not capture_response():
            event.app.invalidate()
            return
        session.toggle_sort()
        load_response()
        save(session)
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings, "q", filter=has_focus(list_control), eager=True
    )
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        if not persist():
            event.app.invalidate()
            return
        event.app.exit(result=session)

    def _return_to_review(event) -> bool:
        if not event.app.layout.has_focus(response_area):
            return False
        _focus_review(event)
        return True

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        dispatch_tui_back(event, _return_to_review, close=_quit)

    @bindings.add("backspace", filter=has_focus(list_control), eager=True)
    def _backspace_from_review(event) -> None:
        _quit(event)

    app: Application[ReviewSession] = Application(
        layout=Layout(
            build_tui_frame(
                TuiRegion(header),
                TuiRegion(body),
                TuiRegion(footer),
            ),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
    )
    load_response()
    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt) as error:
        if not persist():
            raise ValueError(status_message["value"]) from error
        raise ReviewCancelled from error
    return result
