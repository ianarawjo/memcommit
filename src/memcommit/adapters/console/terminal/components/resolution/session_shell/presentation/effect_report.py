"""A focused exact-effect report using the shared diff and Viewer mechanics."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.resolution.effect_preview import (
    EffectPreviewEntry,
    EffectPreviewView,
    EffectReportPresentation,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    semantic_viewer_block_fragments,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    WorkbenchSection,
)

from .formatting import _visual_wrap
from .reporting import _impact_entry_fragments, _impact_entry_section_uid


UNCHANGED_EFFECTS_UID = "REPORT:UNCHANGED_EFFECTS"


def effect_report_groups(
    impact: EffectPreviewView,
    presentation: EffectReportPresentation,
) -> tuple[
    tuple[tuple[int, EffectPreviewEntry], ...],
    tuple[tuple[int, EffectPreviewEntry], ...],
]:
    """Collapse declared retained entries only after proving exact equality."""

    changed, unchanged = [], []
    if not presentation.unchanged_entry_uids <= {entry.uid for entry in impact.entries}:
        raise ValueError("A retained entry is unavailable in the exact preview.")
    for index, entry in enumerate(impact.entries, start=1):
        retained = entry.uid in presentation.unchanged_entry_uids
        if retained and (entry.before is None or entry.before != entry.after):
            raise ValueError("A retained entry must preserve its exact Memory value.")
        # Equality alone does not prove KEEP: a declared same-text EDIT may
        # still create a new revision and must remain in the visible changes.
        group = unchanged if retained else changed
        group.append((index, entry))
    return tuple(changed), tuple(unchanged)


def effect_report_sections(
    impact: EffectPreviewView,
    presentation: EffectReportPresentation,
    *,
    unchanged_expanded: bool = False,
) -> tuple[WorkbenchSection, ...]:
    changed, unchanged = effect_report_groups(impact, presentation)
    return (
        WorkbenchSection("REPORT:INSTRUCTION", "INSTRUCTION", 0),
        *(
            WorkbenchSection(_impact_entry_section_uid(entry, index), "IMPACT_ENTRY", 0)
            for index, entry in changed
        ),
        *(
            (WorkbenchSection(UNCHANGED_EFFECTS_UID, "IMPACT_GROUP", 0),)
            if unchanged
            else ()
        ),
        *(
            WorkbenchSection(_impact_entry_section_uid(entry, index), "IMPACT_ENTRY", 0)
            for index, entry in unchanged
            if unchanged_expanded
        ),
    )


def effect_report_fragments(
    view: ResolutionWorkbenchView,
    impact: EffectPreviewView,
    presentation: EffectReportPresentation,
    *,
    focused_section: int,
    expanded_uid: str | None,
    content_width: int,
    unchanged_expanded: bool = False,
) -> list[tuple[str, str]]:
    """Show identity, instruction, exact changes, and one retained-value group."""

    changed, unchanged = effect_report_groups(impact, presentation)
    fragments = [("class:title", f" {safe_terminal_text(view.title)}\n\n")]
    for location in view.context_locations:
        fragments.append(
            (
                "",
                f" {safe_terminal_text(location.role)} · {safe_terminal_text(location.name)}"
                + (f" · {safe_terminal_text(location.state)}" if location.state else "")
                + "\n",
            )
        )
    fragments.append(("", "\n"))
    fragments.extend(
        semantic_viewer_block_fragments(
            [("class:block-heading", " INSTRUCTION\n")]
            + [
                ("", f" {line}\n")
                for line in _visual_wrap(
                    presentation.instruction, max(12, content_width - 2)
                )
            ]
            + [("", "\n")],
            active=focused_section == 0,
            focus_indices=(0,),
        )
    )
    source_location = (
        view.context_locations[0].name if len(view.context_locations) == 1 else ""
    )
    for section_index, (index, entry) in enumerate(changed, start=1):
        fragments.extend(
            _impact_entry_fragments(
                view,
                entry,
                index,
                active=focused_section == section_index,
                expanded_impact_section_uid=expanded_uid,
                treatment_width=0,
                content_width=content_width,
                read_only=True,
                draft_values={},
                compact=True,
                source_location=source_location,
            )
        )
    if unchanged:
        count = len(unchanged)
        parts = [
            (
                "class:block-heading",
                f" {'▾' if unchanged_expanded else '▸'} {safe_terminal_text(presentation.unchanged_label)}"
                f" · {count} {'Memory' if count == 1 else 'Memories'} unchanged\n",
            )
        ]
        fragments.extend(
            semantic_viewer_block_fragments(
                parts,
                active=focused_section == len(changed) + 1,
                focus_indices=(0,),
            )
        )
        if unchanged_expanded:
            # Retained Memories become ordinary Viewer stops so even a large
            # group stays readable without creating new review obligations.
            for section_index, (index, entry) in enumerate(
                unchanged, start=len(changed) + 2
            ):
                fragments.extend(
                    _impact_entry_fragments(
                        view,
                        entry,
                        index,
                        active=focused_section == section_index,
                        expanded_impact_section_uid=expanded_uid,
                        treatment_width=0,
                        content_width=content_width,
                        read_only=True,
                        draft_values={},
                        compact=True,
                        source_location=source_location,
                    )
                )
    return fragments
