"""Complete Merge results and located decision history, followed by exact Apply."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change,
)
from memcommit.adapters.console.terminal.components.preview import run_preview_screen
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.reviewing.context_diff import (
    context_item_changes,
    context_item_text,
)
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.operations.merge.apply import (
    validate_merge_result,
)
from memcommit.application.operations.merge.inputs import (
    PreparedMerge,
)
from memcommit.application.operations.merge.records import LiteralMergeRound
from memcommit.application.operations.merge.result import MergeResult


def _section(uid, kind, fragments):
    return SemanticViewerSection(
        uid=uid, kind=kind, block=SemanticViewerBlock(tuple(fragments))
    )


def _change(uid, location, before, after):
    treatment = (
        "ADD"
        if before is None
        else "REMOVE"
        if after is None
        else "KEEP"
        if before == after
        else "EDIT"
    )
    return MemoryChange(
        marker={"ADD": "+", "REMOVE": "-", "KEEP": "=", "EDIT": "~"}[treatment],
        treatment=treatment,
        location=location,
        memory_uid=uid,
        before=before,
        after=after,
    )


def _result_section(index, source_names, before, after, *, created=False):
    changes, _, reordered = context_item_changes(before.to_dict(), after.to_dict())
    fragments = [
        (
            "class:section",
            ("\n\n" if index else "")
            + "FROM · "
            + " + ".join(safe_terminal_text(name) for name in source_names)
            + f"\nTO · {safe_terminal_text(before.name)}"
            + (" · NEW CONTEXT" if created else "")
            + "\n",
        ),
        (
            "class:report-neutral",
            f"{len(before.memories)} → {len(after.memories)} items · complete result\n\n",
        ),
    ]
    for change in changes:
        fragments.extend(
            render_inline_memory_change(
                _change(
                    change.uid,
                    before.name,
                    context_item_text(change.before),
                    context_item_text(change.after),
                )
            )
        )
    if not changes:
        fragments.append(("class:report-neutral", "(empty Context)\n"))
    if all(change.treatment == "KEEP" for change in changes) and not reordered:
        fragments.append(
            (
                "class:report-neutral",
                "No content changes; a recovery checkpoint will be recorded.\n",
            )
        )
    if reordered:
        fragments.append(
            (
                "class:report-neutral",
                "Result order shown; retained items changed position.\n",
            )
        )
    return _section(f"MERGE:PREVIEW:{index}", "POST_IMAGE", fragments)


def _round_sections(rounds, target, *, group):
    sections = []
    destination = target.name
    destination_uids = set(target.memories)
    resolve_round = 0
    for number, round in enumerate(rounds, 1):
        literal = isinstance(round, LiteralMergeRound)
        if not literal:
            resolve_round += 1
        phase = "LITERAL" if literal else f"RESOLVE · ROUND {resolve_round}"
        if not round.decisions.decisions:
            destination_uids = set(round.after().memories)
            continue
        sections.append(
            _section(
                f"{group}:round:{number}",
                "SUMMARY",
                [
                    ("class:section", f"\n\nDECISIONS · {phase}\n\n"),
                ],
            )
        )
        before, after = round.before(), round.after()
        before_items, after_items = (
            before.to_dict()["memories"],
            after.to_dict()["memories"],
        )
        candidate = round.candidate if literal else None
        origins = (
            {origin.uid: origin for origin in candidate.origins} if candidate else {}
        )
        mappings = dict(round.input_result_uids or ())
        issues = {issue.uid: issue for issue in round.issues}
        for index, decision in enumerate(round.decisions.decisions):
            issue = issues[decision.issue_uid]
            fragments = [
                (
                    "class:section",
                    ("\n" if index else "") + issue.kind.replace("_", " ") + "\n",
                )
            ]
            for uid in round.affected_uids(issue.uid):
                result_uid = (
                    mappings.get(uid) if round.input_result_uids is not None else uid
                )
                old = context_item_text(before_items.get(uid))
                new = (
                    context_item_text(after_items.get(result_uid))
                    if result_uid
                    else None
                )
                if old is None and new is None:
                    continue
                origin = origins.get(uid)
                location, original_uid = (
                    (origin.context_name, origin.item_uid)
                    if origin
                    else (destination, uid)
                )
                identity = f"[{location}:{original_uid[:8]}]"
                if (
                    new is not None
                    and result_uid not in destination_uids
                    and (location != destination or original_uid != result_uid)
                ):
                    identity += f" → [{destination}:{result_uid[:8]}]"
                # An unchanged Source copy is still a whole addition to Target.
                # Later rounds compare against the previous prepared destination.
                if new is not None and result_uid not in destination_uids:
                    old = None
                fragments.extend(
                    render_inline_memory_change(
                        _change(original_uid, location, old, new), identity=identity
                    )
                )
            labels = {choice.uid: choice.label for choice in issue.choices}
            label = {
                "CONFIRM": "USE SUGGESTION",
                "INTENT": "YOUR INTENT",
                "FORCE": "LEAVE UNRESOLVED",
            }.get(
                decision.kind,
                labels.get(decision.kind, decision.kind.replace("_", " ")),
            )
            explanation = (
                decision.intent
                if decision.kind == "INTENT"
                else issue.proposed_direction
                if decision.kind == "CONFIRM"
                else "Preserve both original texts."
                if decision.kind == "KEEP_BOTH"
                else "Preserve the original text."
                if decision.kind == "KEEP_AS_IS"
                else ""
            )
            fragments.append(
                (
                    "class:report-neutral",
                    "Selected · "
                    + safe_terminal_text(label)
                    + (" — " + safe_terminal_text(explanation) if explanation else "")
                    + "\n",
                )
            )
            sections.append(
                _section(f"{group}:round:{number}:issue:{index}", "DECISION", fragments)
            )
        destination_uids = set(after_items)
    return sections


def project_merge_preview(
    prepared: PreparedMerge,
    result: MergeResult,
) -> SemanticViewerDocument:
    """Compare the original Target with the exact result, then show its decisions."""
    validate_merge_result(prepared, result)
    before = prepared.inputs.target()
    mode = "LITERAL" if prepared.request.method == "LITERAL" else "SEMANTIC + LITERAL"
    sections = [
        _section(
            "MERGE:PREVIEW:HEADER",
            "SUMMARY",
            [("class:title", f"MERGE PREVIEW · {mode}\n")],
        ),
        _result_section(0, (prepared.request.source,), before, result.post_image),
        *_round_sections(result.rounds, before, group="MERGE:0"),
    ]
    return SemanticViewerDocument(tuple(sections))


def run_merge_preview(prepared, result, *, apply_preview, **terminal_options):
    return run_preview_screen(
        project_merge_preview(prepared, result),
        operation="MERGE",
        apply_preview=lambda: apply_preview(result),
        **terminal_options,
    )
