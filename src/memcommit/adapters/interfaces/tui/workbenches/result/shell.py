"""Shared read-only presentation for validated semantic-operation results.

The common shell owns only information hierarchy, terminal safety, and case
navigation.  The operation adapter remains responsible for every semantic
judgment, reference, persisted artifact, provider call, and mutation.
"""

from __future__ import annotations

from memcommit.adapters.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.adapters.interfaces.tui.core.text_layout import (
    single_line_terminal_text,
)
from memcommit.adapters.interfaces.tui.viewers.semantic.detail import (
    semantic_detail_block_fragments,
    semantic_detail_header_fragments,
    semantic_trace_fragments,
)
from memcommit.adapters.interfaces.tui.viewers.semantic import (
    semantic_viewer_block_fragments,
)
from memcommit.application.reviewing.result_workbench import (
    ResultCase,
    ResultCaseDetail,
    ResultSection,
    ResultWorkbenchError,
    ResultWorkbenchView,
)


def _compact(value: str) -> str:
    """Keep one logical case row; the live Window owns visual wrapping."""

    return single_line_terminal_text(safe_terminal_text(value))


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


def _case_row(
    case: ResultCase,
    *,
    index: int,
    active: bool,
    expanded: bool,
) -> list[tuple[str, str]]:
    marker = "▾" if expanded else ("›" if active else " ")
    return semantic_viewer_block_fragments(
        [
            (
                "class:case-title",
                (f" {marker} {index:>2}. [{case.role}] {_compact(case.title)}\n"),
            ),
            ("", f"       {_compact(case.summary)}\n"),
        ],
        active=active,
    )


def _case_detail_fragments(
    view: ResultWorkbenchView,
    detail: ResultCaseDetail,
    *,
    focused_uid: str | None = None,
) -> list[tuple[str, str]]:
    detail = view.validate_detail(detail)
    case = view.case(detail.case_uid)
    case_number = next(
        index
        for index, candidate in enumerate(view.cases, start=1)
        if candidate.uid == case.uid
    )
    fragments = semantic_viewer_block_fragments(
        semantic_detail_header_fragments(
            label=f"CASE DETAIL · {case_number}/{len(view.cases)} · {case.role}",
            title=case.title,
            why_heading="WHY SELECTED",
            why=case.why_selected,
        ),
        active=focused_uid == f"RESULT:CASE:{case.uid}:DETAIL",
        anchor="end",
    )
    # Detail blocks are operation-authored and deliberately retain their
    # supplied order.  The common layer must not reinterpret their semantics.
    for block_index, block in enumerate(detail.blocks):
        fragments.extend(
            semantic_viewer_block_fragments(
                semantic_detail_block_fragments(
                    heading=block.heading,
                    text=block.text,
                    refs=block.refs,
                ),
                active=(focused_uid == f"RESULT:CASE:{case.uid}:BLOCK:{block_index}"),
                anchor="end",
            )
        )
    fragments.extend(
        semantic_viewer_block_fragments(
            semantic_trace_fragments(
                evidence_refs=detail.evidence_refs,
                judgment_refs=detail.judgment_refs,
                outcome_refs=detail.outcome_refs,
                unresolved_refs=detail.unresolved_refs,
            ),
            active=focused_uid == f"RESULT:CASE:{case.uid}:TRACE",
            anchor="end",
        )
    )
    return fragments


def _screen_fragments(
    view: ResultWorkbenchView,
    *,
    selected_index: int,
    detail: ResultCaseDetail | None,
    focused_uid: str | None = None,
) -> list[tuple[str, str]]:
    metrics = "".join(
        (f" · {safe_terminal_text(metric.label)}={metric.value:,}")
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
    ]
    for uid, heading, section in (
        ("RESULT:UNDERSTOOD", "WHAT MEM UNDERSTOOD", view.understood),
        ("RESULT:HAPPENED", "WHAT HAPPENED", view.happened),
        ("RESULT:UNRESOLVED", "WHAT REMAINS UNRESOLVED", view.unresolved),
    ):
        fragments.extend(
            semantic_viewer_block_fragments(
                [
                    ("class:section", f"\n {heading}\n"),
                    ("class:viewer-body", f" {_section_text(section)}\n"),
                ],
                active=focused_uid == uid,
                focus_indices=(0, 1),
            )
        )
    fragments.append(("class:section", "\n REPRESENTATIVE / BOUNDARY CASES\n"))
    if not view.cases:
        fragments.append(("", "  (no inspection cases recorded)\n"))
        return fragments
    expanded_uid = detail.case_uid if detail is not None else None
    for index, case in enumerate(view.cases):
        fragments.extend(
            _case_row(
                case,
                index=index + 1,
                active=(
                    focused_uid == f"RESULT:CASE:{case.uid}"
                    if focused_uid is not None
                    else index == selected_index
                ),
                expanded=case.uid == expanded_uid,
            )
        )
    if detail is not None:
        fragments.extend(_case_detail_fragments(view, detail, focused_uid=focused_uid))
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
        if selected_case_uid is not None and selected_case_uid != detail.case_uid:
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
