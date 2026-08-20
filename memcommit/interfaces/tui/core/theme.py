"""Service-wide style tokens for shared terminal components and viewers."""

from __future__ import annotations

from prompt_toolkit.styles import Style

from memcommit.interfaces.console.theme import SOURCE_CAPABILITY_HEX


# Focus belongs to terminal chrome, while blue fill records retained selection.
MEMCOMMIT_TUI_STYLE = Style.from_dict(
    {
        "memcommit.focused frame.border": "fg:#8bd5ff bold",
        "memcommit.focused frame.label": "fg:#8bd5ff bold",
        "memcommit.notification": "fg:#f5a97f bold",
        "memcommit.table.selected": "reverse bold",
        "memcommit.control.focused": "bold",
        "memcommit.choice.active": "fg:#10242f bg:#8bd5ff",
        "memcommit.choice.active.focused": "fg:#10242f bg:#8bd5ff bold",
        "memcommit.choice.border.focused": "fg:#8bd5ff bold",
        "source-ownership": "fg:#f4f5f7 bold",
        "source-access": "fg:#f4f5f7 bold",
        "source-capability": f"fg:{SOURCE_CAPABILITY_HEX} bold",
        "source-reach": "fg:#f4f5f7",
        "source-state": "fg:#f5a97f bold",
    }
)


SEMANTIC_VIEWER_STYLE = Style.from_dict(
    {
        "report-neutral": "fg:#f4f5f7",
        "report-label": "fg:#f4f5f7 bold",
        "report-label.focused": "fg:#8bd5ff bold",
        "viewer-section": "fg:#8bd5ff bold",
        "viewer-body": "fg:#f4f5f7",
        "viewer-body.focused": "fg:#8bd5ff",
        "loading-label": "fg:#8bd5ff bold",
        "loading-status": "fg:#eed49f bold",
        "loading-complete": "fg:#a6da95 bold",
        "loading-placeholder": "fg:#a5adcb",
        "detail-card": "fg:#ffffff",
        "detail-card.focused": "fg:#8bd5ff bold",
        "memory-object": "fg:#cad3f5",
        "memory-object.focused": "fg:#8bd5ff bold",
        "historical-memory-badge": "fg:#c9ad93",
        "reference": "fg:#c6a0f6",
        "impact.keep": "fg:#a6da95 bold",
        "impact.keep.focused": "fg:#a6da95 bold",
        "impact.redact": "fg:#f5a97f bold",
        "impact.redact.focused": "fg:#f5a97f bold",
        "impact.summarize": "fg:#8aadf4 bold",
        "impact.summarize.focused": "fg:#8aadf4 bold",
        "impact.reframe": "fg:#c6a0f6 bold",
        "impact.reframe.focused": "fg:#c6a0f6 bold",
        "impact.forget": "fg:#ed8796 bold",
        "impact.forget.focused": "fg:#ed8796 bold",
        "impact.custom": "fg:#eed49f bold",
        "impact.custom.focused": "fg:#eed49f bold",
        "impact.other": "fg:#cad3f5 bold",
        "impact.other.focused": "fg:#cad3f5 bold",
        "impact.edit": "fg:#a6da95 bold",
        "impact.edit.focused": "fg:#a6da95 bold",
        "impact.add": "fg:#8aadf4 bold",
        "impact.add.focused": "fg:#8aadf4 bold",
        "impact.remove": "fg:#ed8796 bold",
        "impact.remove.focused": "fg:#ed8796 bold",
        "memory-diff.remove": "fg:#ffffff",
        "memory-diff.remove.changed": "fg:#ed8796 underline",
        "memory-diff.add": "fg:#ffffff",
        "memory-diff.add.changed": "fg:#a6da95 underline",
        "memory-diff.equal": "fg:#ffffff",
        "memory-diff.equal.changed": "fg:#ffffff underline",
        "option-card": "fg:#ffffff",
        "option-card.focused": "fg:#8bd5ff bold underline",
        "option-card.selected": "fg:#8bd5ff bold",
        "option-card.other": "fg:#8bd5ff bold underline",
        "selection-badge": "fg:#8bd5ff bold",
        "case-title": "fg:#ffffff bold",
        "detail-heading": "fg:#ffffff bold",
        "block-heading": "fg:#ffffff bold",
        "trace": "fg:#8bd5ff",
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
