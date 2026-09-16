"""Sever checkpoint metadata shared by publication and exact recovery."""

from __future__ import annotations

from memcommit.application.operations.sever.model import (
    SeverSession,
    sever_record_digest,
)
from memcommit.core.context import (
    Context,
)


def build_checkpoint_args(
    session: SeverSession,
    output: Context,
    sources: list[dict[str, str]],
) -> dict[str, object]:
    args: dict[str, object] = {
        "sever": {
            "save_mode": session.save_mode,
            "session_uid": session.uid,
            "session_digest": sever_record_digest(session),
            "source": session.source.root_name,
            "source_scope": (
                "INCLUDE_DESCENDANTS"
                if session.source.include_descendants
                else "THIS_CONTEXT_ONLY"
            ),
            "criteria": session.criteria.root_name,
            "criteria_scope": (
                "INCLUDE_DESCENDANTS"
                if session.criteria.include_descendants
                else "THIS_CONTEXT_ONLY"
            ),
            "output": session.output_name,
            "results": sources,
        },
    }
    if session.save_mode == "OTHER_SAVE":
        args["context_creation"] = {
            "version": 1,
            "context_uid": output.uid,
            "context_name": output.name,
        }
    else:
        # Group every in-place owner checkpoint into one Undo/Redo unit.
        # The root remains the primary receipt, while descendants retain
        # their own Context and Memory identities.
        args["command_contexts"] = [
            {"uid": uid, "name": name} for name, uid, _digest in session.source.contexts
        ]
    return args


def checkpoint_args_match(
    actual: object, expected: dict[str, object], *, save_mode: str
) -> bool:
    """Accept only the exact metadata or its save-mode-specific legacy shape."""

    if save_mode == "SELF_SAVE":
        # Older direct self-save checkpoints predate grouped owner membership.
        legacy = {
            key: value for key, value in expected.items() if key != "command_contexts"
        }
    else:
        sever = expected.get("sever")
        legacy = (
            {
                **expected,
                "sever": {
                    key: value for key, value in sever.items() if key != "save_mode"
                },
            }
            if isinstance(sever, dict)
            else expected
        )
    return actual in (expected, legacy)
