"""Arrow-key workbench for one saved Context meld."""
from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.tui_primitives import (
    TuiRegion,
    build_framed_multiline_input,
    build_tui_frame,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.meld import MeldSession
from memcommit.resolution_workbench import ResolutionNavigation


@dataclass(frozen=True)
class MeldShellAction:
    kind: str
    issue_uid: str | None = None
    choice_index: int | None = None
    comment: str = ""


def _line(value: str, limit: int = 100) -> str:
    normalized = " ".join(safe_terminal_text(value).split())
    if sum(get_cwidth(character) for character in normalized) <= limit:
        return normalized
    kept: list[str] = []
    width = 0
    for character in normalized:
        character_width = get_cwidth(character)
        if width + character_width > limit - 1:
            break
        kept.append(character)
        width += character_width
    return "".join(kept).rstrip() + "…"


def _screen_text(
    session: MeldSession,
    *,
    selected_index: int,
    expanded: bool,
    choice_index: int | None,
):
    assessment = session.current_assessment
    fragments: list[tuple[str, str]] = [
        ("class:title", f" MEM MELD · {session.mode}\n"),
        (
            "",
            (
                f" {session.frames[0].context_name} + "
                f"{session.frames[1].context_name} → "
                f"{session.target.context_name}\n"
            ),
        ),
        (
            "",
            (
                f" {session.state} · "
                f"{len(assessment.relations) if assessment else 0} relations · "
                f"{len(assessment.issues) if assessment else 0} issues · "
                f"{len(assessment.proposals) if assessment else 0} results\n\n"
            ),
        ),
    ]
    if assessment is None:
        fragments.append(("", " Analysis pending.\n"))
        return fragments
    fragments.extend(
        [
            ("class:section", " WHAT MEM UNDERSTOOD\n"),
            ("", " " + safe_terminal_text(assessment.overview) + "\n\n"),
            ("class:section", " ISSUES\n"),
        ]
    )
    relation_by_uid = {
        relation.uid: relation for relation in assessment.relations
    }
    relation_number = {
        relation.uid: index
        for index, relation in enumerate(assessment.relations, start=1)
    }
    frame_by_uid = {frame.uid: frame for frame in session.frames}
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in session.frames
        for memory in frame.memories
    }
    if not assessment.issues:
        fragments.append(("", "  (none)\n"))
    for index, issue in enumerate(assessment.issues):
        selected = index == selected_index
        if selected:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                "class:selected" if selected else "",
                (
                    f" {'▾' if selected and expanded else ('›' if selected else ' ')} "
                    f"{index + 1:>2}. [{issue.priority}] {_line(issue.title)}\n"
                ),
            )
        )
        fragments.append(("", f"       WHY · {_line(issue.why_it_matters)}\n"))
        if selected and expanded:
            fragments.append(
                (
                    "",
                    "       QUESTION · "
                    f"{safe_terminal_text(issue.question)}\n",
                )
            )
            for option_index, option in enumerate(issue.options):
                chosen = option_index == choice_index
                fragments.append(
                    (
                        "class:choice" if chosen else "",
                        (
                            f"       {'●' if chosen else '○'} "
                            f"{option_index + 1}. "
                            f"{safe_terminal_text(option.label)}\n"
                        ),
                    )
                )
                fragments.append(
                    ("", f"          {safe_terminal_text(option.text)}\n")
                )
            fragments.append(("class:section", "       SOURCE MEMORIES\n"))
            seen_members: set[tuple[str, str]] = set()
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                for member in relation.members:
                    key = (member.frame_uid, member.memory_uid)
                    if key in seen_members:
                        continue
                    seen_members.add(key)
                    frame = frame_by_uid[member.frame_uid]
                    memory = memory_by_key[key]
                    fragments.append(
                        (
                            "",
                            (
                                "       - "
                                f"{safe_terminal_text(frame.context_name)} "
                                f"#{memory.position + 1} "
                                f"[{memory.uid[:8]}] · "
                                f"{safe_terminal_text(memory.content)}\n"
                            ),
                        )
                    )
            fragments.append(("class:section", "       RELATED RELATIONS\n"))
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                fragments.append(
                    (
                        "",
                        (
                            f"       - R{relation_number[relation_uid]} "
                            f"{relation.kind} · "
                            f"{safe_terminal_text(relation.reason)}\n"
                        ),
                    )
                )
            affected = [
                proposal
                for proposal in assessment.proposals
                if set(proposal.relation_uids) & set(issue.relation_uids)
            ]
            fragments.append(("class:section", "       AFFECTED RESULTS\n"))
            if not affected:
                fragments.append(
                    (
                        "",
                        "       - unresolved; no target Memory proposed yet\n",
                    )
                )
            for proposal in affected:
                fragments.append(
                    (
                        "",
                        (
                            f"       - [{proposal.disposition}] "
                            f"{safe_terminal_text(proposal.content)}\n"
                        ),
                    )
                )
    fragments.extend(
        [
            ("", "\n"),
            ("class:section", " PROPOSED TARGET MEMORIES\n"),
        ]
    )
    if not assessment.proposals:
        fragments.append(("", "  (none yet)\n"))
    for index, proposal in enumerate(assessment.proposals, start=1):
        fragments.append(
            (
                "",
                (
                    f"  + {index:>2}. [{proposal.disposition}] "
                    f"{_line(proposal.content, 120)}\n"
                ),
            )
        )
    return fragments


def run_meld_shell(
    session: MeldSession,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldShellAction | None:
    """Collect one semantic or terminal action; never call a provider."""
    if require_tty:
        require_interactive_terminal(
            "Interactive meld",
            snapshot_hint=(
                "Run the same 'mem meld LEFT RIGHT' command outside a TTY "
                "to render its saved snapshot."
            ),
        )
    assessment = session.current_assessment
    if assessment is None:
        return None
    selected = {"index": 0}
    expanded = {"value": False}
    choice = {"index": None}
    global_comment = {"value": False}
    status = {"value": ""}
    bindings = KeyBindings()

    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="meld-message",
    )
    input_area = composer.text_area
    body_control = FormattedTextControl(
        lambda: _screen_text(
            session,
            selected_index=selected["index"],
            expanded=expanded["value"],
            choice_index=choice["index"],
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def move(delta: int) -> None:
        if not assessment.issues:
            return
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(assessment.issues) - 1),
        )
        expanded["value"] = False
        choice["index"] = None
        global_comment["value"] = False
        composer.frame.title = "MESSAGE"

    def submit(event) -> None:
        text = input_area.text.strip()
        if global_comment["value"]:
            if not text:
                status["value"] = "Enter a whole-set comment first."
                return
            event.app.exit(
                result=MeldShellAction(kind="COMMENT_ALL", comment=text)
            )
            return
        if not assessment.issues:
            status["value"] = "There is no issue to comment on."
            return
        if not text and choice["index"] is None:
            status["value"] = "Choose a reading or enter a comment."
            return
        event.app.exit(
            result=MeldShellAction(
                kind="COMMENT_ISSUE",
                issue_uid=assessment.issues[selected["index"]].uid,
                choice_index=choice["index"],
                comment=text,
            )
        )

    @bindings.add("down", filter=~has_focus(input_area))
    def _down(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=~has_focus(input_area))
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=~has_focus(input_area))
    def _expand(event) -> None:
        if assessment.issues:
            expanded["value"] = not expanded["value"]
        event.app.invalidate()

    for number in range(1, 6):
        def choose_reading(event, index=number - 1) -> None:
            if (
                assessment.issues
                and index
                < len(assessment.issues[selected["index"]].options)
            ):
                expanded["value"] = True
                choice["index"] = (
                    None if choice["index"] == index else index
                )
            event.app.invalidate()

        bindings.add(str(number), filter=~has_focus(input_area))(
            choose_reading
        )

    @bindings.add("tab")
    def _focus_input(event) -> None:
        global_comment["value"] = False
        composer.frame.title = "MESSAGE"
        event.app.layout.focus(input_area)

    @bindings.add("g", filter=~has_focus(input_area))
    def _global_comment(event) -> None:
        global_comment["value"] = True
        composer.frame.title = "WHOLE-SET COMMENT"
        input_area.text = ""
        event.app.layout.focus(input_area)

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    @bindings.add("c-s", filter=has_focus(input_area), eager=True)
    def _submit_input(event) -> None:
        submit(event)

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    @bindings.add(
        "escape",
        "enter",
        filter=has_focus(input_area),
        eager=True,
    )
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("p", filter=~has_focus(input_area))
    def _preserve(event) -> None:
        event.app.exit(result=MeldShellAction(kind="PRESERVE_ALL"))

    @bindings.add("d", filter=~has_focus(input_area))
    def _defer(event) -> None:
        event.app.exit(result=MeldShellAction(kind="DEFER_ALL"))

    @bindings.add("a", filter=~has_focus(input_area))
    def _accept(event) -> None:
        if session.state != "READY_TO_APPLY":
            status["value"] = "Resolve REQUIRED issues before accepting."
            event.app.invalidate()
            return
        event.app.exit(result=MeldShellAction(kind="ACCEPT"))

    @bindings.add("q", filter=~has_focus(input_area), eager=True)
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        event.app.exit(result=None)

    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status['value']}"
                if status["value"]
                else (
                    " ↑/↓ issue  Enter detail  1-5 reading  Tab comment  "
                    "G comment all  Enter send  Ctrl-J/Alt-Enter newline  "
                    "P preserve all  D defer  A accept  Q quit "
                )
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(body),
        TuiRegion(composer.container),
        TuiRegion(footer),
    )
    application: Application[MeldShellAction | None] = Application(
        layout=Layout(root, focused_element=body_control),
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
        return None


# Keep the operation-specific renderer above as a compatibility snapshot while
# routing the live interaction through the shared resolution grammar.  The
# wrapper translates only the UID-bound action envelope; Meld still owns every
# semantic turn, provider call, saved assessment, and acceptance boundary.
_run_legacy_meld_shell = run_meld_shell


def run_meld_shell(
    session: MeldSession,
    *,
    navigation: ResolutionNavigation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldShellAction | None:
    """Collect one action through the shared dynamic resolution workbench."""
    from memcommit.commands.resolution_workbench_shell import (
        run_resolution_workbench_shell,
    )
    from memcommit.meld_resolution_adapter import (
        MeldResolutionWorkbenchAdapter,
    )

    snapshot_hint = (
        "Run the same 'mem meld' command outside a TTY to render its saved "
        "snapshot."
    )
    if require_tty:
        require_interactive_terminal(
            "Interactive meld",
            snapshot_hint=snapshot_hint,
        )
    if session.current_assessment is None:
        return None
    adapter = MeldResolutionWorkbenchAdapter(session)
    action = run_resolution_workbench_shell(
        adapter.view,
        navigation=navigation,
        app_input=app_input,
        app_output=app_output,
        require_tty=False,
        terminal_label="Interactive meld",
        snapshot_hint=snapshot_hint,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind == "SUBMIT_ALL":
        return MeldShellAction(kind="COMMENT_ALL", comment=action.comment)
    if action.kind == "PRESERVE_ALL":
        return MeldShellAction(kind="PRESERVE_ALL")
    if action.kind == "DEFER":
        return MeldShellAction(kind="DEFER_ALL")
    if action.kind == "ACCEPT":
        return MeldShellAction(kind="ACCEPT")
    if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
        raise ValueError(
            f"Unsupported resolution action '{action.kind}' for Meld."
        )
    issue = adapter.view().item(action.item_uid)
    choice_index = (
        next(
            index
            for index, option in enumerate(issue.options)
            if option.uid == action.option_uid
        )
        if action.option_uid is not None
        else None
    )
    return MeldShellAction(
        kind="COMMENT_ISSUE",
        issue_uid=action.item_uid,
        choice_index=choice_index,
        comment=action.comment,
    )
