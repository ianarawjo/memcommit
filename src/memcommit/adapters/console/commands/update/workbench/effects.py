"""One exact Update Viewer body shared by preview, saved Impact and Apply."""

from __future__ import annotations

from dataclasses import replace

from memcommit.adapters.console.commands.update.workbench.presentation import (
    UpdateResolutionWorkbenchAdapter,
    _source_references,
)
from memcommit.adapters.console.terminal.components.resolution.effect_preview import (
    EffectReportDetail,
    EffectReportPresentation,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchView,
)
from memcommit.application.operations.update.model import UpdateSession


def update_effect_view(
    session: UpdateSession, *, applying: bool = False
) -> ResolutionWorkbenchView:
    """Keep artifact and endpoint identity without creating review obligations."""

    view = UpdateResolutionWorkbenchAdapter(session).view()
    return replace(
        view,
        items=(),
        results=(),
        metrics=(),
        overview="",
        overview_sections=(),
        report_items_summary=None,
        show_results=False,
        context_locations=tuple(
            replace(location, state="GRANT" if binding is not None else "")
            for location, binding in zip(
                view.context_locations,
                (session.granted_source, session.granted_target),
                strict=True,
            )
        ),
        capabilities=frozenset({"ACCEPT"}) if applying else frozenset(),
        accept_enabled=applying and session.status == "staged",
    )


def update_effect_report(session: UpdateSession) -> EffectReportPresentation:
    """Attach frozen provenance to its diff, without a separate Items surface."""

    count = len(session.operations)
    return EffectReportPresentation(
        apply_label=f"Apply {count} {'change' if count == 1 else 'changes'} to {session.target_name}",
        entry_details=tuple(
            EffectReportDetail(
                operation.memory_uid,
                "SOURCE REFERENCES",
                _source_references(operation.source_refs),
            )
            for operation in session.operations
        ),
    )
