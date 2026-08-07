"""Read-only terminal workbench for one exact saved Compare analysis."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_focused_frame_style,
    display_escape_text,
)
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonIssue,
    ComparisonMember,
    ComparisonRelation,
)
from memcommit.session_workbench_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
)


CompareWorkbenchAction = Literal["close", "ledger", "meld", "rationale"]


@dataclass(frozen=True)
class CompareWorkbenchReceipt:
    """One process-local navigation result from the read-only workbench."""

    action: CompareWorkbenchAction
    context_name: str | None = None
    memory_uid: str | None = None


@dataclass(frozen=True)
class _WorkbenchRow:
    kind: Literal["REPORT", "SECTION", "ISSUE", "LEDGER", "RELATION"]
    key: str
    label: str
    section: str | None = None
    relation_uid: str | None = None
    issue_uid: str | None = None


def _compact(value: str, limit: int = 104) -> str:
    escaped = " ".join(display_escape_text(value).split())
    return escaped if len(escaped) <= limit else escaped[: limit - 1] + "…"


def _display_multiline(value: str) -> str:
    """Preserve trusted layout newlines while escaping each untrusted line."""
    return "\n".join(display_escape_text(line) for line in value.split("\n"))


def _focused_section_line(value: str) -> str:
    """Mark one Viewer section without changing the persisted report text."""
    return f"── {value} ──"


def _reader_section_offsets(value: str) -> tuple[int, ...]:
    """Return stable logical-line starts for reader-level semantic sections."""
    headings = (
        "MEM COMPARE ·",
        "WHAT MEM UNDERSTOOD",
        "WHAT BOTH CONTAIN",
        "WHAT DIFFERS",
        "ONLY IN ",
        "GROUNDING CANDIDATES",
        "POTENTIAL CONFLICTS",
        "POTENTIAL CONFLICT ·",
        "RELATION LEDGER",
        "SOURCE-LINKED DETAIL",
        "RELATION ·",
        "ALL RELATIONS",
    )
    offsets = tuple(
        index
        for index, line in enumerate(value.split("\n"))
        if index == 0 or line.startswith(headings)
    )
    return tuple(dict.fromkeys(offsets))


def _next_viewer_section_index(value: str, current: int, delta: int) -> int:
    """Move focus between headings while the Window owns minimal scrolling."""
    offsets = _reader_section_offsets(value)
    return max(0, min(current + delta, len(offsets) - 1))


def _relation_groups(
    analysis: ComparisonAnalysis,
) -> dict[str, tuple[ComparisonRelation, ...]]:
    reference, compared = analysis.frames
    return {
        "both": tuple(
            relation
            for relation in analysis.relations
            if relation.kind in {"EQUIVALENT", "COMPATIBLE"}
        ),
        "differences": tuple(
            relation
            for relation in analysis.relations
            if relation.kind in {"SCOPED", "CONFLICT", "UNCLEAR"}
        ),
        "reference_only": tuple(
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(member.frame_uid == reference.uid for member in relation.members)
        ),
        "compared_only": tuple(
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(member.frame_uid == compared.uid for member in relation.members)
        ),
    }


def _rows(analysis: ComparisonAnalysis) -> tuple[_WorkbenchRow, ...]:
    reference, compared = analysis.frames
    groups = _relation_groups(analysis)
    result = [
        _WorkbenchRow(
            kind="REPORT",
            key="report",
            label="Complete Compare report",
        )
    ]
    sections = (
        ("understanding", "What Mem understood", 1),
        ("both", "What both contain", len(groups["both"])),
        ("differences", "What differs", len(groups["differences"])),
        (
            "reference_only",
            f"Only in {reference.context_name}",
            len(groups["reference_only"]),
        ),
        (
            "compared_only",
            f"Only in {compared.context_name}",
            len(groups["compared_only"]),
        ),
        ("issues", "Potential conflicts", len(analysis.issues)),
    )
    result.extend(
        _WorkbenchRow(
            kind="SECTION",
            key=f"section:{key}",
            label=f"  {label} · {count}",
            section=key,
        )
        for key, label, count in sections
        if key == "understanding" or count
    )
    result.extend(
        _WorkbenchRow(
            kind="ISSUE",
            key=issue.uid,
            label=f"    {issue.title}",
            issue_uid=issue.uid,
        )
        for issue in analysis.issues
    )
    result.append(
        _WorkbenchRow(
            kind="LEDGER",
            key="ledger",
            label=f"Relation ledger · {len(analysis.relations)}",
        )
    )
    result.extend(
        _WorkbenchRow(
            kind="RELATION",
            key=relation.uid,
            label=f"R{index} · {relation.kind} · {_compact(relation.summary)}",
            relation_uid=relation.uid,
        )
        for index, relation in enumerate(analysis.relations, start=1)
    )
    return tuple(result)


def _relation_for_row(
    analysis: ComparisonAnalysis,
    row: _WorkbenchRow,
) -> ComparisonRelation | None:
    relation_by_uid = {relation.uid: relation for relation in analysis.relations}
    if row.relation_uid is not None:
        return relation_by_uid.get(row.relation_uid)
    if row.issue_uid is not None:
        issue = next(
            issue for issue in analysis.issues if issue.uid == row.issue_uid
        )
        return relation_by_uid.get(issue.relation_uids[0])
    return None


def _issue_for_row(
    analysis: ComparisonAnalysis,
    row: _WorkbenchRow,
) -> ComparisonIssue | None:
    if row.issue_uid is None:
        return None
    return next(issue for issue in analysis.issues if issue.uid == row.issue_uid)


def _member_location(
    analysis: ComparisonAnalysis,
    member: ComparisonMember,
) -> tuple[str, str]:
    for frame in analysis.frames:
        if frame.uid != member.frame_uid:
            continue
        for memory in frame.memories:
            if memory.uid == member.memory_uid:
                return frame.context_name, memory.content
    raise ValueError("Compare workbench relation references an unknown Memory.")


def run_compare_workbench(
    analysis: ComparisonAnalysis,
    *,
    report_text: str | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    workbench_navigation: SessionWorkbenchNavigation | None = None,
) -> CompareWorkbenchReceipt:
    """Browse an immutable analysis and return one explicit follow-up action."""
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Compare requires a terminal.")
    rows = _rows(analysis)
    selected = {"member": 0, "expanded": False}
    navigation = workbench_navigation or SessionWorkbenchNavigation()
    groups = _relation_groups(analysis)
    windows: dict[str, Window] = {}
    bindings = KeyBindings()

    def current_row() -> _WorkbenchRow:
        return rows[navigation.row_index]

    def current_viewer_row() -> _WorkbenchRow:
        return rows[navigation.viewer_row_index]

    def current_relation() -> ComparisonRelation | None:
        return _relation_for_row(analysis, current_row())

    def current_members() -> tuple[ComparisonMember, ...]:
        relation = current_relation()
        return () if relation is None else relation.members

    def move_row(delta: int) -> None:
        navigation.move_row(len(rows), delta)
        navigation.preview_selected_row()
        selected["member"] = 0
        selected["expanded"] = False

    def move_member(delta: int) -> None:
        members = current_members()
        if not members:
            return
        current = members[selected["member"]]
        frame_order = [frame.uid for frame in analysis.frames]
        available_frames = [
            frame_uid
            for frame_uid in frame_order
            if any(member.frame_uid == frame_uid for member in members)
        ]
        if len(available_frames) > 1:
            frame_index = available_frames.index(current.frame_uid)
            target_frame = available_frames[
                (frame_index + delta) % len(available_frames)
            ]
            selected["member"] = next(
                index
                for index, member in enumerate(members)
                if member.frame_uid == target_frame
            )
            return
        selected["member"] = (selected["member"] + delta) % len(members)

    def back_to_report() -> None:
        navigation.row_index = 0
        navigation.viewer_row_index = 0
        selected["member"] = 0
        selected["expanded"] = False
        navigation.section_uid = None

    def render_rows():
        fragments: list[tuple[str, str]] = []
        for index, row in enumerate(rows):
            active = index == navigation.row_index
            if active:
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if active else " "
            style = (
                "class:memcommit.table.selected"
                if active and navigation.pane == "items"
                else "bold"
                if active
                else ""
            )
            kind = "ITEM" if row.kind == "ISSUE" else row.kind
            if row.kind == "RELATION":
                fragments.append((style, f"{pointer} {_compact(row.label)}"))
            else:
                fragments.append(
                    (style, f"{pointer} {kind:<8} {_compact(row.label)}")
                )
            if index < len(rows) - 1:
                fragments.append(("", "\n"))
        return fragments

    def section_relations(row: _WorkbenchRow) -> tuple[ComparisonRelation, ...]:
        if row.section in groups:
            return groups[row.section]
        if row.section == "issues":
            relation_uids = {
                uid for issue in analysis.issues for uid in issue.relation_uids
            }
            return tuple(
                relation
                for relation in analysis.relations
                if relation.uid in relation_uids
            )
        return ()

    def append_relation_sources(
        lines: list[str],
        relations: tuple[ComparisonRelation, ...],
    ) -> None:
        for relation in relations:
            lines.append(f"{relation.kind} · {relation.summary}")
            for index, member in enumerate(relation.members):
                context_name, content = _member_location(analysis, member)
                marker = "›" if index == selected["member"] else " "
                lines.append(
                    f"{marker} {context_name} [{member.memory_uid[:8]}] {content}"
                )

    def fallback_report() -> str:
        reports = analysis.reports
        reference, compared = analysis.frames
        lines = ["WHAT MEM UNDERSTOOD", analysis.understanding.text]
        if reports is not None:
            sections = (
                ("WHAT BOTH CONTAIN", reports.both),
                ("WHAT DIFFERS", reports.differences),
                (f"ONLY IN {reference.context_name}", reports.reference_only),
                (f"ONLY IN {compared.context_name}", reports.compared_only),
            )
            for heading, content in sections:
                if content:
                    lines.extend(["", heading, content])
        if analysis.issues:
            lines.extend(["", f"POTENTIAL CONFLICTS · {len(analysis.issues)}"])
            lines.extend(
                f"{index}. {issue.title} · {issue.why_it_matters}"
                for index, issue in enumerate(analysis.issues, start=1)
            )
        return "\n".join(lines)

    def render_detail() -> str:
        row = current_viewer_row()
        if row.kind == "REPORT":
            return _display_multiline(report_text or fallback_report())

        if row.kind == "SECTION":
            reports = analysis.reports
            reference, compared = analysis.frames
            content_by_section = {
                "understanding": analysis.understanding.text,
                "both": "" if reports is None else reports.both,
                "differences": "" if reports is None else reports.differences,
                "reference_only": "" if reports is None else reports.reference_only,
                "compared_only": "" if reports is None else reports.compared_only,
                "issues": "\n".join(
                    f"{index}. {issue.title} · {issue.why_it_matters}"
                    for index, issue in enumerate(analysis.issues, start=1)
                ),
            }
            heading_by_section = {
                "understanding": "WHAT MEM UNDERSTOOD",
                "both": "WHAT BOTH CONTAIN",
                "differences": "WHAT DIFFERS",
                "reference_only": f"ONLY IN {reference.context_name}",
                "compared_only": f"ONLY IN {compared.context_name}",
                "issues": "POTENTIAL CONFLICTS",
            }
            lines = [
                heading_by_section[row.section or "understanding"],
                content_by_section[row.section or "understanding"] or "(none)",
            ]
            if selected["expanded"]:
                lines.extend(["", "SOURCE-LINKED DETAIL"])
                append_relation_sources(lines, section_relations(row))
            return _display_multiline("\n".join(lines))

        if row.kind == "LEDGER":
            counts: dict[str, int] = {}
            for relation in analysis.relations:
                counts[relation.kind] = counts.get(relation.kind, 0) + 1
            lines = [
                f"RELATION LEDGER · {len(analysis.relations)}",
                " · ".join(
                    f"{kind} {counts.get(kind, 0)}"
                    for kind in (
                        "EQUIVALENT",
                        "COMPATIBLE",
                        "SCOPED",
                        "CONFLICT",
                        "DISTINCT",
                        "UNCLEAR",
                    )
                ),
                "Select a relation below to inspect its exact source Memories.",
            ]
            if selected["expanded"]:
                lines.extend(["", "ALL RELATIONS"])
                lines.extend(
                    f"{index}. {relation.kind} · {relation.summary}"
                    for index, relation in enumerate(analysis.relations, start=1)
                )
            return _display_multiline("\n".join(lines))

        issue = _issue_for_row(analysis, row)
        relation = _relation_for_row(analysis, row)
        lines: list[str] = []
        if issue is not None:
            lines.extend(
                [
                    f"POTENTIAL CONFLICT · {issue.title}",
                    issue.why_it_matters,
                    issue.question,
                ]
            )
            if selected["expanded"]:
                lines.extend(
                    f"{index}. {option.label} · {option.text}"
                    for index, option in enumerate(issue.options, start=1)
                )
        if relation is not None:
            lines.extend(
                [
                    f"RELATION · {relation.kind} · {relation.status}",
                    relation.summary,
                    relation.reason,
                ]
            )
            if selected["expanded"] or issue is not None:
                for index, member in enumerate(relation.members):
                    context_name, content = _member_location(analysis, member)
                    marker = "›" if index == selected["member"] else " "
                    lines.append(
                        f"{marker} {context_name} "
                        f"[{member.memory_uid[:8]}] {content}"
                    )
        return _display_multiline("\n".join(lines))

    def _current_reader_sections() -> tuple[WorkbenchSection, ...]:
        offsets = _reader_section_offsets(render_detail())
        return tuple(
            WorkbenchSection(
                uid=f"COMPARE:{current_viewer_row().key}:LINE:{offset}",
                kind="REPORT_SECTION",
            )
            for offset in offsets
        )

    def render_reader():
        """Anchor focus at one heading and let the viewport follow minimally.

        Keeping the full report lets prompt-toolkit retain the current viewport
        while the focused heading remains visible. It scrolls only when that
        hidden cursor crosses the upper or lower boundary, like a normal list.
        """
        lines = render_detail().split("\n")
        offsets = _reader_section_offsets("\n".join(lines))
        sections = _current_reader_sections()
        section_index = navigation.section_index(sections)
        anchor = offsets[section_index]
        fragments: list[tuple[str, str]] = []
        for index, line in enumerate(lines):
            if index == anchor:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:viewer-section" if index == anchor else "",
                    _focused_section_line(line) if index == anchor else line,
                )
            )
            if index < len(lines) - 1:
                fragments.append(("", "\n"))
        return fragments

    @bindings.add("down")
    def _down(event) -> None:
        if navigation.pane == "viewer":
            navigation.move_section(
                _current_reader_sections(),
                1,
            )
        else:
            move_row(1)
        event.app.invalidate()

    @bindings.add("up")
    def _up(event) -> None:
        if navigation.pane == "viewer":
            navigation.move_section(
                _current_reader_sections(),
                -1,
            )
        else:
            move_row(-1)
        event.app.invalidate()

    @bindings.add("pagedown")
    def _page_down(event) -> None:
        if navigation.pane == "viewer":
            navigation.move_section(_current_reader_sections(), 8)
        else:
            move_row(8)
        event.app.invalidate()

    @bindings.add("pageup")
    def _page_up(event) -> None:
        if navigation.pane == "viewer":
            navigation.move_section(_current_reader_sections(), -8)
        else:
            move_row(-8)
        event.app.invalidate()

    @bindings.add("home")
    def _home(event) -> None:
        if navigation.pane == "viewer":
            navigation.move_section(_current_reader_sections(), -1_000_000)
        else:
            move_row(-1_000_000)
        event.app.invalidate()

    @bindings.add("end")
    def _end(event) -> None:
        if navigation.pane == "viewer":
            navigation.move_section(_current_reader_sections(), 1_000_000)
        else:
            move_row(1_000_000)
        event.app.invalidate()

    @bindings.add("right")
    def _right(event) -> None:
        if navigation.pane != "items":
            return
        move_member(1)
        event.app.invalidate()

    @bindings.add("left")
    def _left(event) -> None:
        if navigation.pane != "items":
            return
        move_member(-1)
        event.app.invalidate()

    @bindings.add("enter")
    def _expand(event) -> None:
        if navigation.pane == "items":
            selected["expanded"] = True
            navigation.section_uid = None
            navigation.open_selected()
            event.app.layout.focus(windows["viewer"])
            event.app.invalidate()
            return
        selected["expanded"] = not selected["expanded"]
        navigation.section_uid = None
        event.app.invalidate()

    @bindings.add("tab")
    @bindings.add("s-tab")
    def _switch_pane(event) -> None:
        pane = navigation.toggle_frames()
        event.app.layout.focus(windows[pane])
        event.app.invalidate()

    @bindings.add("r", eager=True)
    def _rationale(event) -> None:
        row = (
            current_viewer_row()
            if navigation.pane == "viewer"
            else current_row()
        )
        relation = _relation_for_row(analysis, row)
        members = () if relation is None else relation.members
        if not members:
            return
        member = members[selected["member"]]
        context_name, _content = _member_location(analysis, member)
        event.app.exit(
            result=CompareWorkbenchReceipt(
                action="rationale",
                context_name=context_name,
                memory_uid=member.memory_uid,
            )
        )

    @bindings.add("l", eager=True)
    def _ledger(event) -> None:
        event.app.exit(result=CompareWorkbenchReceipt(action="ledger"))

    @bindings.add("m", eager=True)
    def _meld(event) -> None:
        event.app.exit(result=CompareWorkbenchReceipt(action="meld"))

    @bindings.add("b", eager=True)
    def _back(event) -> None:
        back_to_report()
        navigation.focus("items")
        event.app.layout.focus(windows["items"])
        event.app.invalidate()

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _escape(event) -> None:
        if navigation.row_index != 0 or selected["expanded"]:
            back_to_report()
            navigation.focus("items")
            event.app.layout.focus(windows["items"])
            event.app.invalidate()
            return
        event.app.exit(result=CompareWorkbenchReceipt(action="close"))

    @bindings.add("q", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=CompareWorkbenchReceipt(action="close"))

    reference, compared = analysis.frames
    header = Window(
        FormattedTextControl(
            " MEM COMPARE · "
            + display_escape_text(reference.context_name)
            + " ↔ "
            + display_escape_text(compared.context_name)
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    list_window = Window(
        FormattedTextControl(render_rows, focusable=True, show_cursor=False),
        height=Dimension(min=4, preferred=6, max=8, weight=3),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    detail_window = Window(
        FormattedTextControl(render_reader, focusable=True, show_cursor=False),
        height=Dimension(min=10, preferred=16, weight=7),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    windows["detail"] = detail_window
    windows["viewer"] = detail_window
    windows["items"] = list_window
    reader_frame = Frame(detail_window, title="VIEWER")
    items_frame = Frame(list_window, title="ITEMS")
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" FOCUS {navigation.pane.upper()} · B/Esc/Backspace back · Q close · "
                "Tab switch · ↑↓ section/item · Enter deeper · ←→ source · "
                "PgUp/PgDn page · Home/End · R rationale · L ledger · M meld"
                f"  ·  {navigation.row_index + 1}/{len(rows)}"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[CompareWorkbenchReceipt] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    reader_frame,
                    items_frame,
                    footer,
                ]
            ),
            focused_element=list_window,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                SEMANTIC_VIEWER_STYLE,
            ]
        ),
    )
    for pane_name, frame in (("viewer", reader_frame), ("items", items_frame)):
        bind_focused_frame_style(
            frame,
            is_focused=lambda pane_name=pane_name: navigation.pane == pane_name,
        )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return CompareWorkbenchReceipt(action="close")
