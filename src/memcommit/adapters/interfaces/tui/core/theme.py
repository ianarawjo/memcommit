"""Service-wide style tokens for shared terminal components and viewers."""

from __future__ import annotations

from prompt_toolkit.styles import Style

from memcommit.adapters.interfaces.console.theme import (
    DETAIL_HEX,
    ERROR_HEX,
    FOCUS_HEX,
    FOCUS_TEXT_HEX,
    MEMORY_HEX,
    PEACH_HEX,
    PLACEHOLDER_HEX,
    REPORT_HEX,
    SemanticColorRole,
    semantic_action_role,
    semantic_color_hex,
)


def semantic_role_style(role: SemanticColorRole) -> str:
    """Return the prompt-toolkit class for one shared semantic color role."""

    return f"class:semantic.{role.value}"


def semantic_action_style(value: str, *, fallback: str = "") -> str:
    """Resolve a command/effect label to its shared TUI style class."""

    role = semantic_action_role(value)
    return semantic_role_style(role) if role is not None else fallback


_SEMANTIC_ROLE_STYLES = {
    f"semantic.{role.value}": f"fg:{semantic_color_hex(role)} bold"
    for role in SemanticColorRole
}


# Focus belongs to terminal chrome, while blue fill records retained selection.
MEMCOMMIT_TUI_STYLE = Style.from_dict(
    {
        "memcommit.focused frame.border": f"fg:{FOCUS_HEX} bold",
        "memcommit.focused frame.label": f"fg:{FOCUS_HEX} bold",
        "memcommit.notification": f"fg:{PEACH_HEX} bold",
        "memcommit.error": f"fg:{ERROR_HEX} bold",
        "memcommit.table.selected": "reverse bold",
        "memcommit.control.focused": "bold",
        "memcommit.choice.active": f"fg:{FOCUS_TEXT_HEX} bg:{FOCUS_HEX}",
        "memcommit.choice.active.focused": (
            f"fg:{FOCUS_TEXT_HEX} bg:{FOCUS_HEX} bold"
        ),
        "memcommit.choice.border.focused": f"fg:{FOCUS_HEX} bold",
        "source-ownership": (
            f"fg:{semantic_color_hex(SemanticColorRole.GRANT)} bold"
        ),
        "source-access": (
            f"fg:{semantic_color_hex(SemanticColorRole.CAPABILITY)} bold"
        ),
        "source-capability": (
            f"fg:{semantic_color_hex(SemanticColorRole.CAPABILITY)} bold"
        ),
        "source-reach": f"fg:{REPORT_HEX}",
        "source-state": f"fg:{PEACH_HEX} bold",
        "context-embedded": (
            f"fg:{semantic_color_hex(SemanticColorRole.EMBED)}"
        ),
        "context-grant-token": (
            f"fg:{semantic_color_hex(SemanticColorRole.NAVIGATION_GRANT)} bold"
        ),
        "context-query-only": (
            f"fg:{semantic_color_hex(SemanticColorRole.REFERENCE)}"
        ),
        **_SEMANTIC_ROLE_STYLES,
    }
)


SEMANTIC_VIEWER_STYLE = Style.from_dict(
    {
        "report-neutral": f"fg:{REPORT_HEX}",
        "finding-marker": f"fg:{REPORT_HEX}",
        "finding-marker.focused": f"fg:{FOCUS_HEX} bold",
        # The semantic class before this presentation class owns foreground;
        # hierarchy is quiet at rest and becomes emphatic only at focus.
        "finding-label": "nobold",
        "finding-label.focused": "bold",
        "report-label": f"fg:{REPORT_HEX} bold",
        "report-label.focused": f"fg:{FOCUS_HEX} bold",
        "viewer-section": f"fg:{FOCUS_HEX} bold",
        "viewer-body": f"fg:{REPORT_HEX}",
        "viewer-body.focused": f"fg:{FOCUS_HEX}",
        "loading-label": f"fg:{FOCUS_HEX} bold",
        "loading-status": (
            f"fg:{semantic_color_hex(SemanticColorRole.EMBED)} bold"
        ),
        "loading-complete": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} bold"
        ),
        "loading-placeholder": f"fg:{PLACEHOLDER_HEX}",
        "detail-card": f"fg:{DETAIL_HEX}",
        "detail-card.focused": f"fg:{FOCUS_HEX} bold",
        "memory-object": f"fg:{MEMORY_HEX}",
        "memory-object.focused": f"fg:{FOCUS_HEX} bold",
        "historical-memory-badge": (
            f"fg:{semantic_color_hex(SemanticColorRole.HISTORY)}"
        ),
        "history-receipt": (
            f"fg:{semantic_color_hex(SemanticColorRole.HISTORY)} bold"
        ),
        "history-source": f"fg:{REPORT_HEX} bold",
        "reference": (
            f"fg:{semantic_color_hex(SemanticColorRole.REFERENCE)}"
        ),
        "impact.keep": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} bold"
        ),
        "impact.keep.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} bold"
        ),
        "impact.redact": f"fg:{PEACH_HEX} bold",
        "impact.redact.focused": f"fg:{PEACH_HEX} bold",
        "impact.summarize": (
            f"fg:{semantic_color_hex(SemanticColorRole.ADD)} bold"
        ),
        "impact.summarize.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.ADD)} bold"
        ),
        "impact.reframe": (
            f"fg:{semantic_color_hex(SemanticColorRole.REFERENCE)} bold"
        ),
        "impact.reframe.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.REFERENCE)} bold"
        ),
        "impact.forget": (
            f"fg:{semantic_color_hex(SemanticColorRole.REMOVE)} bold"
        ),
        "impact.forget.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.REMOVE)} bold"
        ),
        "impact.custom": (
            f"fg:{semantic_color_hex(SemanticColorRole.EMBED)} bold"
        ),
        "impact.custom.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.EMBED)} bold"
        ),
        "impact.other": f"fg:{MEMORY_HEX} bold",
        "impact.other.focused": f"fg:{MEMORY_HEX} bold",
        "impact.edit": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} bold"
        ),
        "impact.edit.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} bold"
        ),
        "impact.add": (
            f"fg:{semantic_color_hex(SemanticColorRole.ADD)} bold"
        ),
        "impact.add.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.ADD)} bold"
        ),
        "impact.remove": (
            f"fg:{semantic_color_hex(SemanticColorRole.REMOVE)} bold"
        ),
        "impact.remove.focused": (
            f"fg:{semantic_color_hex(SemanticColorRole.REMOVE)} bold"
        ),
        "memory-diff.remove": f"fg:{DETAIL_HEX}",
        "memory-diff.before-marker": (
            f"fg:{semantic_color_hex(SemanticColorRole.REMOVE)} bold"
        ),
        "memory-diff.remove.changed": (
            f"fg:{semantic_color_hex(SemanticColorRole.REMOVE)} underline"
        ),
        "memory-diff.add": f"fg:{DETAIL_HEX}",
        "memory-diff.after-marker": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} bold"
        ),
        "memory-diff.add.changed": (
            f"fg:{semantic_color_hex(SemanticColorRole.EDIT)} underline"
        ),
        "memory-diff.equal": f"fg:{DETAIL_HEX}",
        "memory-diff.equal.changed": f"fg:{DETAIL_HEX} underline",
        "option-card": f"fg:{DETAIL_HEX}",
        "option-card.focused": f"fg:{FOCUS_HEX} bold underline",
        "option-card.selected": f"fg:{FOCUS_HEX} bold",
        "option-card.other": f"fg:{FOCUS_HEX} bold underline",
        "selection-badge": f"fg:{FOCUS_HEX} bold",
        "case-title": f"fg:{DETAIL_HEX} bold",
        "detail-heading": f"fg:{DETAIL_HEX} bold",
        "block-heading": f"fg:{DETAIL_HEX} bold",
        "trace": f"fg:{FOCUS_HEX}",
        **_SEMANTIC_ROLE_STYLES,
    }
)


def focused_control_style(*, focused: bool, selected: bool = False) -> str:
    """Return the shared nested-control focus/selection presentation class."""

    if selected:
        return (
            "class:memcommit.choice.active.focused"
            if focused
            else "class:memcommit.choice.active"
        )
    return "class:memcommit.control.focused" if focused else ""
