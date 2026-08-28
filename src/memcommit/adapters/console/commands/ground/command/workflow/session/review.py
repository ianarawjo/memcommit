"""Guard and apply reviewed commands for persisted Ground sessions."""

from __future__ import annotations

import subprocess

from memcommit.adapters.console.commands.ground.named_shell import (
    GroundCommandProposal,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground.model import (
    GroundError,
    GroundFrame,
    GroundSession,
    context_frame_digest,
)
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore, ground_session_record_digest

from .. import apply as approved_apply


def _ground_digest(session: GroundSession) -> str:
    return ground_session_record_digest(session)


def _ground_version_token(session: GroundSession) -> str:
    """Freeze one complete named-Ground state into an opaque CAS token."""
    return (
        f"v1:{session.uid}:{session.revision}:{ground_session_record_digest(session)}"
    )


def _parse_ground_version_token(
    value: str | None,
) -> tuple[str, int, str] | None:
    """Validate an internal exact-command precondition."""
    if value is None:
        return None
    parts = value.split(":")
    if len(parts) != 4 or parts[0] != "v1":
        raise GroundError("The expected Ground version token is invalid.")
    expected_uid, revision_text, expected_digest = parts[1:]
    try:
        expected_revision = int(revision_text)
    except ValueError as error:
        raise GroundError("The expected Ground version token is invalid.") from error
    if (
        not expected_uid
        or expected_revision < 0
        or str(expected_revision) != revision_text
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise GroundError("The expected Ground version token is invalid.")
    return expected_uid, expected_revision, expected_digest


def _with_ground_version_guard(
    session: GroundSession,
    argv: tuple[str, ...],
) -> tuple[str, ...]:
    """Attach the frozen save-boundary guard to one reviewed Ground argv."""
    if len(argv) < 3 or argv[:3] != (
        "mem",
        "ground",
        session.contract_name,
    ):
        raise GroundError("Cannot guard an invalid Ground command.")
    return (
        *argv[:3],
        "--if-ground-version",
        _ground_version_token(session),
        *argv[3:],
    )


def _context_version_token(context: Context) -> str:
    """Freeze one direct Context frame for an exact binding command."""
    direct_items = tuple(context.iter_items())
    return ":".join(
        (
            "v1",
            context.name,
            context.uid,
            context_frame_digest(context),
            str(sum(isinstance(item, Memory) for item in direct_items)),
            str(len(direct_items)),
        )
    )


def _parse_context_version_token(
    value: str,
) -> tuple[str, str, str, int, int]:
    parts = value.split(":")
    if len(parts) != 6 or parts[0] != "v1":
        raise GroundError("An expected Context version token is invalid.")
    name, uid, digest, memory_text, item_text = parts[1:]
    try:
        memory_count = int(memory_text)
        item_count = int(item_text)
    except ValueError as error:
        raise GroundError("An expected Context version token is invalid.") from error
    if (
        not name
        or not uid
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or memory_count < 0
        or item_count < memory_count
        or str(memory_count) != memory_text
        or str(item_count) != item_text
    ):
        raise GroundError("An expected Context version token is invalid.")
    return name, uid, digest, memory_count, item_count


def _with_context_version_guards(
    contexts: tuple[Context, ...],
    argv: tuple[str, ...],
) -> tuple[str, ...]:
    guarded = list(argv[:3])
    for context in contexts:
        guarded.extend(["--if-context-version", _context_version_token(context)])
    guarded.extend(argv[3:])
    return tuple(guarded)


def _assert_expected_binding_frames(
    session: GroundSession,
    expected: tuple[tuple[str, str, str, int, int], ...],
) -> None:
    """Match child-loaded binding frames to the locally reviewed versions."""
    by_name = {frame.context_name: frame for frame in session.frames}
    if (
        len(by_name) != len(session.frames)
        or len(expected) != len(session.frames)
        or set(by_name) != {item[0] for item in expected}
    ):
        raise GroundError("The binding Context set changed after it was reviewed.")
    for name, uid, digest, memory_count, item_count in expected:
        frame: GroundFrame = by_name[name]
        if (
            frame.context_uid != uid
            or frame.context_digest != digest
            or frame.direct_memory_count != memory_count
            or frame.direct_item_count != item_count
        ):
            raise GroundError(
                f"Binding Context '{name}' changed after it was reviewed."
            )


def _load_bound_contexts(
    store: MemoryStore,
    session: GroundSession,
    *,
    tolerate_missing: bool = False,
) -> tuple[Context, ...]:
    contexts: list[Context] = []
    for frame in session.frames:
        try:
            contexts.append(store.load(frame.context_name))
        except FileNotFoundError:
            if not tolerate_missing:
                raise
    return tuple(contexts)


def _validate_named_ground_proposal_command(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> None:
    """Require the approved argv to retain every frozen save precondition."""
    if (
        proposal.expected_ground_uid != session.uid
        or proposal.expected_revision != session.revision
        or proposal.expected_state_digest != _ground_digest(session)
    ):
        raise GroundError(
            "The reviewed command does not match the visible Ground state."
        )
    expected_ground_token = (
        f"v1:{proposal.expected_ground_uid}:{proposal.expected_revision}:"
        f"{proposal.expected_state_digest}"
    )
    _parse_ground_version_token(expected_ground_token)
    expected_prefix = (
        "mem",
        "ground",
        session.contract_name,
        "--if-ground-version",
        expected_ground_token,
    )
    argv = proposal.review.argv
    if argv[:5] != expected_prefix:
        raise GroundError("The reviewed Ground command lost its Ground revision check.")
    cursor = 5
    actual_context_versions: list[str] = []
    while cursor + 1 < len(argv) and argv[cursor] == "--if-context-version":
        actual_context_versions.append(argv[cursor + 1])
        cursor += 2
    if any(
        argument in {"--if-ground-version", "--if-context-version"}
        for argument in argv[cursor:]
    ):
        raise GroundError(
            "The reviewed Ground command contains an invalid version guard."
        )
    expected_context_versions = proposal.expected_context_versions
    if tuple(actual_context_versions) != expected_context_versions:
        raise GroundError(
            "The reviewed Ground command lost its Context revision checks."
        )
    if proposal.kind == "BIND":
        if not expected_context_versions:
            raise GroundError("A reviewed Ground binding requires Context guards.")
        parsed = tuple(
            _parse_context_version_token(value) for value in expected_context_versions
        )
        if len({value[0] for value in parsed}) != len(parsed):
            raise GroundError(
                "A reviewed Ground binding contains duplicate Context guards."
            )
    elif expected_context_versions:
        raise GroundError("Only a reviewed Ground binding may carry Context guards.")


def _apply_named_ground_proposal(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[GroundSession, str]:
    _validate_named_ground_proposal_command(session, proposal)
    store = MemoryStore(create=False)
    latest = store.load_ground_session(session.contract_name)
    if latest is None or latest.uid != proposal.expected_ground_uid:
        raise GroundError("The named Ground changed identity before approval.")
    if (
        latest.revision != proposal.expected_revision
        or _ground_digest(latest) != proposal.expected_state_digest
    ):
        raise GroundError(
            "The named Ground changed after this proposal. Refine the turn "
            "against the refreshed state."
        )
    try:
        result = approved_apply._run_approved_ground_command(proposal.review.argv)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GroundError(
            "The approved Ground command could not be completed."
        ) from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GroundError(
            "The approved Ground command failed"
            + (f": {safe_terminal_text(detail)}" if detail else ".")
        )
    updated = store.load_ground_session(session.contract_name)
    if updated is None or updated.uid != proposal.expected_ground_uid:
        raise GroundError(
            "The approved command reported success, but its Ground could not "
            "be reloaded safely."
        )
    expected_revision = (
        proposal.expected_revision
        if proposal.kind == "BIND"
        else proposal.expected_revision + 1
    )
    if (
        updated.revision < expected_revision
        or _ground_digest(updated) == proposal.expected_state_digest
    ):
        raise GroundError(
            "The approved command reported success, but the latest Ground "
            "does not contain its expected state transition."
        )
    return updated, result.stdout.strip()
