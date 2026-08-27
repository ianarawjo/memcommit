"""Profile-local searchable projections of retained workflow evidence.

The projections in this module are deliberately smaller than their durable
records. Search may rank what a person approved, but it must not dump operation
frames, source Memories, provider prompts, or concealed authority data.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

from memcommit.adapters.console.commands.compare.sessions import iter_saved_comparisons
from memcommit.adapters.console.commands.meld.sessions import list_meld_session_catalog
from memcommit.context import Context
from memcommit.application.operations.rationale.cache import list_rationale_inferences
from memcommit.application.operations.search.model import SearchArtifact
from memcommit.persistence.store import MemoryStore


SearchArtifactRecord = tuple[str, str, SearchArtifact]
_ARTIFACT_CONTENT_LIMIT = 40_000


def _bounded(value: str) -> str:
    text = value.strip()
    if len(text) <= _ARTIFACT_CONTENT_LIMIT:
        return text
    return text[: _ARTIFACT_CONTENT_LIMIT - 1].rstrip() + "…"


def _single_line(value: str, *, limit: int = 360) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _json_projection(value: object) -> str:
    return _bounded(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    )


def _checkpoint_artifacts(
    store: MemoryStore,
    contexts: Sequence[Context],
) -> list[SearchArtifactRecord]:
    records: list[SearchArtifactRecord] = []
    for context in contexts:
        for checkpoint in store.list_checkpoints(context.name):
            uid = checkpoint.get("uid")
            if not isinstance(uid, str) or not uid:
                continue
            command = checkpoint.get("command")
            command_text = command if isinstance(command, str) and command else "manual"
            description = checkpoint.get("description")
            message = checkpoint.get("message")
            timestamp = checkpoint.get("timestamp")
            parts = [
                f"Command: {command_text}",
                f"Timestamp: {timestamp}" if isinstance(timestamp, str) else "",
                (
                    f"Description: {description}"
                    if isinstance(description, str) and description.strip()
                    else ""
                ),
                (
                    f"Message: {message}"
                    if isinstance(message, str) and message.strip()
                    else ""
                ),
            ]
            records.append(
                (
                    context.uid,
                    context.name,
                    SearchArtifact(
                        uid=uid,
                        artifact_kind="trace",
                        title=f"{command_text} checkpoint",
                        content="\n".join(part for part in parts if part),
                        summary=(
                            description.strip()
                            if isinstance(description, str) and description.strip()
                            else command_text
                        ),
                    ),
                )
            )
    return records


def _comparison_artifacts(
    store: MemoryStore,
    contexts: Sequence[Context],
) -> list[SearchArtifactRecord]:
    by_uid = {context.uid: context for context in contexts}
    records: list[SearchArtifactRecord] = []
    for analysis, _path in iter_saved_comparisons(store):
        owners = [
            by_uid[frame.context_uid]
            for frame in analysis.frames
            if frame.context_uid in by_uid
        ]
        if not owners:
            continue
        projection = {
            "sources": [frame.context_name for frame in analysis.frames],
            "created_at": analysis.created_at,
            "overview": analysis.understanding.text,
            "reports": (
                analysis.reports.to_dict()
                if analysis.reports is not None
                else None
            ),
            "relations": [relation.to_dict() for relation in analysis.relations],
            "issues": [issue.to_dict() for issue in analysis.issues],
        }
        owner = owners[0]
        records.append(
            (
                owner.uid,
                owner.name,
                SearchArtifact(
                    uid=analysis.uid,
                    artifact_kind="compare_session",
                    title=(
                        f"Compare {analysis.frames[0].context_name} and "
                        f"{analysis.frames[1].context_name}"
                    ),
                    content=_json_projection(projection),
                    summary=_single_line(analysis.understanding.text),
                ),
            )
        )
    return records


def _meld_artifacts(
    store: MemoryStore,
    contexts: Sequence[Context],
) -> list[SearchArtifactRecord]:
    by_uid = {context.uid: context for context in contexts}
    records: list[SearchArtifactRecord] = []
    # Meld records are target-scoped.  Do not validate or open sessions owned
    # by Contexts outside this frozen artifact frame: they are neither evidence
    # for this request nor a precondition for searching these Contexts.
    for entry in list_meld_session_catalog(
        store,
        target_context_uids=by_uid,
    ):
        context = by_uid.get(entry.key)
        if context is None:
            continue
        session = store.load_meld_session(entry.key)
        if session is None:
            continue
        projection: dict[str, object] = {
            "mode": session.mode,
            "state": session.state,
            "sources": [frame.context_name for frame in session.frames],
            "target": session.target.context_name,
            "turns": [
                {
                    "sequence": turn.sequence,
                    "scope": turn.scope,
                    "revision": turn.revision,
                    "comment": turn.comment,
                    "overview": (
                        turn.assessment.overview
                        if turn.assessment is not None
                        else None
                    ),
                }
                for turn in session.turns
            ],
            "application": (
                session.application.to_dict()
                if session.application is not None
                else None
            ),
        }
        if session.comparison_seed is not None:
            analysis = session.comparison_seed.analysis
            projection["comparison"] = {
                "overview": analysis.understanding.text,
                "issues": [issue.to_dict() for issue in analysis.issues],
            }
        records.append(
            (
                context.uid,
                context.name,
                SearchArtifact(
                    uid=session.uid,
                    artifact_kind="meld_session",
                    title=entry.title,
                    content=_json_projection(projection),
                    summary=_single_line(
                        (
                            f"{session.state}; latest review: "
                            f"{next((turn.comment for turn in reversed(session.turns) if turn.comment.strip()), 'no written resolution')}"
                        )
                    ),
                ),
            )
        )
    return records


def _rationale_artifacts(
    contexts: Sequence[Context],
) -> list[SearchArtifactRecord]:
    records: list[SearchArtifactRecord] = []
    for context in contexts:
        for saved in list_rationale_inferences(context.uid):
            inference = saved.inference
            records.append(
                (
                    context.uid,
                    context.name,
                    SearchArtifact(
                        # The selected Memory is the durable subject. Prefixing
                        # prevents collision with its ordinary SearchCandidate.
                        uid=f"rationale:{saved.selected_memory_uid}",
                        artifact_kind="rationale",
                        title=(
                            "Rationale for Memory "
                            f"{saved.selected_memory_uid[:8]}"
                        ),
                        content=_json_projection(
                            {
                                "explanation": inference.explanation,
                                "support_memory_uids": (
                                    inference.support_memory_uids
                                ),
                            }
                        ),
                        summary=_single_line(inference.explanation),
                    ),
                )
            )
    return records


def collect_search_artifacts(
    store: MemoryStore,
    contexts: Sequence[Context],
) -> tuple[SearchArtifactRecord, ...]:
    """Collect bounded artifacts owned by the active Profile and frame."""
    unique_contexts = tuple({context.uid: context for context in contexts}.values())
    return tuple(
        [
            *_checkpoint_artifacts(store, unique_contexts),
            *_comparison_artifacts(store, unique_contexts),
            *_meld_artifacts(store, unique_contexts),
            *_rationale_artifacts(unique_contexts),
        ]
    )
