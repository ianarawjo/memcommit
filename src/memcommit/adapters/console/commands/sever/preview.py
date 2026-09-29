"""Read the complete Sever result before applying its exact treatments."""

from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change,
)
from memcommit.adapters.console.terminal.components.preview import run_preview_screen
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.operations.sever.model import SeverSession


def project_sever_preview(session: SeverSession) -> SemanticViewerDocument:
    retained = {source.uid: content for _, source, content in session.results()}
    fragments = [
        (
            "class:report-label",
            f"SOURCE · {display_escape_text(session.source.root_name)} · {len(session.source.memories)} → {len(retained)} notes\n",
        ),
        (
            "class:report-label",
            f"CRITERIA · {display_escape_text(session.criteria.root_name)}\n",
        ),
        ("class:report-neutral", "SOURCE → RESULT\n\n"),
    ]
    for source in session.source.memories:
        after = retained.get(source.uid)
        identity = f"[{source.context_name}:{source.uid[:8]}]"
        if session.save_mode == "OTHER_SAVE" and after is not None:
            from memcommit.application.operations.sever.apply.projection import (
                sever_result_memory_uid,
            )

            identity += f" → [{session.output_name}:{sever_result_memory_uid(session.uid, source.uid, after)[:8]}]"
        fragments.extend(
            render_inline_memory_change(
                MemoryChange(
                    "~", "SEVER", source.context_name, source.uid, source.content, after
                ),
                identity=identity,
            )
        )
    if not session.source.memories:
        fragments.append(("class:report-neutral", "(empty Context)\n"))
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid="sever:preview",
                kind="POST_IMAGE",
                block=SemanticViewerBlock(tuple(fragments)),
            ),
        )
    )


def run_sever_preview(session: SeverSession, *, apply_preview, **terminal_options):
    return run_preview_screen(
        project_sever_preview(session),
        operation="SEVER",
        apply_preview=apply_preview,
        **terminal_options,
    )
