"""Profile-local retrieval projections of retained workflow evidence.

The projections in this module are deliberately smaller than their durable
records. Search may rank what a person approved, but it must not dump operation
frames, source Memories, provider prompts, or concealed authority data.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

from memcommit.application.operations.rationale.cache import (
    list_rationale_inferences,
)
from memcommit.application.capabilities.retrieval_corpus.candidates import (
    RetrievalArtifact,
)
from memcommit.application.operations.compare.sessions import (
    iter_saved_comparisons,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


RetrievalArtifactRecord = tuple[str, str, RetrievalArtifact]
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
) -> list[RetrievalArtifactRecord]:
    records: list[RetrievalArtifactRecord] = []
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
                    RetrievalArtifact(
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
) -> list[RetrievalArtifactRecord]:
    by_uid = {context.uid: context for context in contexts}
    records: list[RetrievalArtifactRecord] = []
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
                RetrievalArtifact(
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
) -> list[RetrievalArtifactRecord]:
    records: list[RetrievalArtifactRecord] = []
    for context in contexts:
        # Meld latest slots use the target Context UID as their public storage
        # key. Loading only those exact keys keeps unrelated invalid sessions
        # outside this already-frozen artifact frame and avoids a dependency on
        # the terminal session picker's presentation catalog.
        session = store.load_meld_session(context.uid)
        if session is None:
            continue
        left, right = session.frames
        title = (
            f"{left.context_name} → {right.context_name}"
            if session.mode == "DIRECTIONAL"
            else (
                f"{left.context_name} + {right.context_name} → "
                f"{session.target.context_name}"
            )
        )
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
                RetrievalArtifact(
                    uid=session.uid,
                    artifact_kind="meld_session",
                    title=title,
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
) -> list[RetrievalArtifactRecord]:
    records: list[RetrievalArtifactRecord] = []
    for context in contexts:
        for saved in list_rationale_inferences(context.uid):
            inference = saved.inference
            records.append(
                (
                    context.uid,
                    context.name,
                    RetrievalArtifact(
                        # The selected Memory is the durable subject. Prefixing
                        # prevents collision with its ordinary candidate.
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


def collect_retrieval_artifacts(
    store: MemoryStore,
    contexts: Sequence[Context],
) -> tuple[RetrievalArtifactRecord, ...]:
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
