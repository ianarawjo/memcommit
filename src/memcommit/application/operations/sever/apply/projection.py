"""Calculate detached Context post-images from exact reviewed Sever decisions."""

from __future__ import annotations

import hashlib
import uuid

from memcommit.application.operations.sever.application import (
    SeverApplicationError,
)
from memcommit.application.operations.sever.model import (
    SeverMemory,
    SeverSession,
)
from memcommit.application.operations.update.application import apply_update
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    SourceReference,
    UpdateError,
    UpdateOperation,
    UpdatePlan,
)
from memcommit.core.context import (
    Context,
    Memory,
)
from memcommit.persistence.store import (
    context_record_digest,
)


def _result_uid(session_uid: str, source_uid: str, content: str) -> str:
    return str(
        uuid.uuid5(uuid.UUID(session_uid), f"result\x1f{source_uid}\x1f{content}")
    )


def source_reference(
    session: SeverSession,
    source: SeverMemory,
) -> SourceReference:
    """Bind a Sever result step to its exact reviewed Source Memory."""

    matches = tuple(
        receipt
        for receipt in session.source.contexts
        if receipt[0] == source.context_name
    )
    if len(matches) != 1:
        raise SeverApplicationError(
            "The reviewed Sever Source does not identify one exact owner."
        )
    _context_name, context_uid, _context_digest = matches[0]
    return SourceReference(
        context_uid=context_uid,
        context_name=source.context_name,
        memory_uid=source.uid,
        content_digest=hashlib.sha256(source.content.encode("utf-8")).hexdigest(),
    )


def apply_projection(
    session: SeverSession,
    target: Context,
    operations: tuple[UpdateOperation, ...],
) -> Context:
    """Apply exact Sever effects through Update without publishing them."""

    try:
        result = apply_update(
            UpdatePlan(
                uid=session.uid,
                target_uid=target.uid,
                target_name=target.name,
                operations=operations,
            ),
            target,
        )
    except UpdateError as error:
        raise SeverApplicationError(
            "The reviewed Sever Result could not be applied to its working Target."
        ) from error
    post_image = result.post_image_for(target.uid)
    if post_image is not None:
        return post_image
    if operations:
        raise SeverApplicationError(
            "The reviewed Sever Result did not produce its Target post-image."
        )
    return Context.from_dict(target.to_dict())


def result_context(
    session: SeverSession,
    *,
    output_uid: str,
) -> tuple[Context, tuple[str, ...], list[dict[str, str]]]:
    output = Context(uid=output_uid, name=session.output_name)
    result_uids: list[str] = []
    sources: list[dict[str, str]] = []
    operations: list[UpdateOperation] = []
    for candidate, source, content in session.results():
        uid = _result_uid(session.uid, source.uid, content)
        operations.append(
            AddOperation(
                owner_context_uid=output.uid,
                owner_context_name=output.name,
                memory_uid=uid,
                new_content=content,
                source_refs=(source_reference(session, source),),
                reason=candidate.rationale,
            )
        )
        result_uids.append(uid)
        sources.append(
            {
                "candidate_uid": candidate.uid,
                "source_context": source.context_name,
                "source_memory_uid": source.uid,
                "selection": candidate.selection,
            }
        )
    output = apply_projection(session, output, tuple(operations))
    return output, tuple(result_uids), sources


def self_save_source_receipts(
    session: SeverSession,
) -> tuple[tuple[str, str, str], ...]:
    """Return every exact local Source owner updated by in-place Sever."""

    if (
        session.save_mode != "SELF_SAVE"
        or session.source.granted is not None
        or not session.source.contexts
    ):
        raise SeverApplicationError(
            "In-place Sever requires one ordinary local Source scope."
        )
    receipts = session.source.contexts
    if (
        receipts[0][0] != session.source.root_name
        or receipts[0][1] != session.source.root_uid
        or len({name for name, _uid, _digest in receipts}) != len(receipts)
        or len({uid for _name, uid, _digest in receipts}) != len(receipts)
    ):
        raise SeverApplicationError(
            "The in-place Source receipts do not identify one rooted owner scope."
        )
    return receipts


def self_save_contexts(
    session: SeverSession,
    originals: tuple[Context, ...],
) -> tuple[tuple[Context, ...], tuple[str, ...], list[dict[str, str]]]:
    """Project reviewed treatments back to each exact Source owner."""

    receipts = self_save_source_receipts(session)
    original_by_name = {context.name: context for context in originals}
    if len(original_by_name) != len(originals) or set(original_by_name) != {
        name for name, _uid, _digest in receipts
    }:
        raise SeverApplicationError(
            "The in-place Source owner set changed after review. Re-run Sever."
        )
    for source_name, source_uid, source_digest in receipts:
        original = original_by_name[source_name]
        if (
            original.uid != source_uid
            or context_record_digest(original) != source_digest
        ):
            raise SeverApplicationError(
                "The in-place Source changed after review. Re-run Sever."
            )

    retained = {
        source.uid: (candidate, content)
        for candidate, source, content in session.results()
    }
    operations_by_owner: dict[str, list[UpdateOperation]] = {
        name: [] for name, _uid, _digest in receipts
    }
    result_uids: list[str] = []
    sources: list[dict[str, str]] = []
    for candidate in session.candidates:
        source = session.source_memory(candidate.source_memory_uid)
        original = original_by_name.get(source.context_name)
        current = original.memories.get(source.uid) if original is not None else None
        if (
            original is None
            or not isinstance(current, Memory)
            or current.content != source.content
        ):
            raise SeverApplicationError(
                "An in-place Source owner no longer contains its reviewed Memories."
            )
        retained_result = retained.get(source.uid)
        if retained_result is None:
            operations_by_owner[source.context_name].append(
                RemoveOperation(
                    owner_context_uid=original.uid,
                    owner_context_name=original.name,
                    memory_uid=source.uid,
                    old_content=source.content,
                    source_refs=(source_reference(session, source),),
                    reason=candidate.rationale,
                )
            )
        else:
            _retained_candidate, content = retained_result
            if content != source.content:
                operations_by_owner[source.context_name].append(
                    EditOperation(
                        owner_context_uid=original.uid,
                        owner_context_name=original.name,
                        memory_uid=source.uid,
                        old_content=source.content,
                        new_content=content,
                        source_refs=(source_reference(session, source),),
                        reason=candidate.rationale,
                    )
                )
            result_uids.append(source.uid)
        sources.append(
            {
                "candidate_uid": candidate.uid,
                "source_context": source.context_name,
                "source_memory_uid": source.uid,
                "selection": candidate.selection,
            }
        )

    outputs = tuple(
        apply_projection(
            session,
            original_by_name[name],
            tuple(operations_by_owner[name]),
        )
        for name, _uid, _digest in receipts
    )
    return outputs, tuple(result_uids), sources


def self_save_context(
    session: SeverSession,
    original: Context,
) -> tuple[Context, tuple[str, ...], list[dict[str, str]]]:
    """Compatibility projection for one exact direct Source Context."""

    outputs, result_uids, sources = self_save_contexts(
        session,
        (original,),
    )
    if len(outputs) != 1:
        raise SeverApplicationError(
            "Direct self-save cannot project a recursive Source scope."
        )
    return outputs[0], result_uids, sources
