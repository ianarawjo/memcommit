"""Create, bind, and revise a named common-grounding workbench."""
from __future__ import annotations

import re
import sys
import subprocess
from dataclasses import replace
from typing import Annotated, Iterable, Optional

import typer

from memcommit.commands.ground_shell import (
    GroundShellProposal,
    proposal_argv,
    run_ground_shell,
)
from memcommit.commands.exact_command_review import ExactCommandReview
from memcommit.commands.ground_named_shell import (
    GroundCommandProposal,
    run_named_ground_shell,
)
from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.context import Context, Memory
from memcommit.ground import (
    GROUND_SCHEMA_VERSION,
    GroundError,
    GroundFrame,
    GroundSession,
    GroundTargetSpec,
    accepted_ground_case_count,
    bind_ground_workbench,
    context_frame_digest,
    create_ground_session,
    propose_ground_case,
    propose_ground_round,
    propose_ground_rule,
    resolve_ground_requirement,
    review_ground_item,
    revise_ground_goal,
    revise_ground_requirement,
    select_ground_candidate,
    stale_ground_frames,
    target_requirement_status,
    validate_ground_contract_name,
    validate_ground_goal,
)
from memcommit.ground_dialogue import (
    GROUND_DIALOGUE_USER_TEXT_LIMIT,
    GroundDialogueError,
    GroundDialogueProposal,
    interpret_ground_dialogue,
)
from memcommit.ground_turn_dialogue import (
    GroundTurnAction,
    ground_turn_aliases,
    interpret_ground_turn,
)
from memcommit.query_provider import connect_codex_chatgpt_provider
from memcommit.store import (
    ConcurrentGroundUpdateError,
    MemoryStore,
    ground_session_record_digest,
)


def _validated_start_request(value: str) -> str:
    """Validate one unsaved natural-language Ground entry."""
    text = value.strip()
    if not text or len(text) > GROUND_DIALOGUE_USER_TEXT_LIMIT:
        raise GroundDialogueError(
            "Ground dialogue input must be non-empty and no longer than "
            f"{GROUND_DIALOGUE_USER_TEXT_LIMIT} characters."
        )
    return text


def render_ground_start(initial_request: str = "") -> str:
    """Render the unsaved entry frame for a blank grounding conversation."""
    working_goal = (
        _validated_start_request(initial_request)
        if initial_request
        else ""
    )
    safe_goal = safe_terminal_text(working_goal).replace("\n", "\n  ")
    goal_lines = (
        ["  (not yet stated)"]
        if not safe_goal
        else [f"  {safe_goal}"]
    )
    dialogue_lines = (
        [
            "OPEN QUESTION · GOAL",
            "  What are you trying to understand, decide, or make together?",
            "",
            "  Start in your own words. You do not need a Ground name,",
            "  Rules, Cases, or final wording yet.",
            "",
            "  A rough outcome, concrete case, or uncertainty is enough.",
        ]
        if not safe_goal
        else [
            "DIALOGUE",
            "  YOU · STARTING REQUEST",
            f"  {safe_goal}",
            "",
            "  Run this command in an interactive terminal to interpret",
            "  the Working Goal and continue the dialogue.",
        ]
    )
    return "\n".join(
        [
            "MEM GROUND · WORKING · NOT SAVED",
            "",
            "GOAL",
            *goal_lines,
            "",
            "CONTEXTS",
            "  (not bound; not inferred)",
            "  No current Context was read.",
            "",
            "RULES",
            "  (none yet)",
            "",
            "CASES",
            "  (none yet)",
            "",
            *dialogue_lines,
            "",
            "DESCRIBE WHAT YOU HAVE SO FAR",
            "",
            "> ________________________________________________________________",
            (
                "  Reply to the agent; this snapshot does not read stdin."
                if not safe_goal
                else "  The starting request was not sent to a provider."
            ),
            "",
            "NEXT",
            "  The agent will restate a candidate Goal, suggest a portable",
            "  GROUND_NAME, and propose one exact mem ground command.",
            "  Nothing is created until you approve that command.",
            "",
            "No Ground has been created.",
            "No Context or Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _interpret_new_ground_turn(text: str):
    turn = interpret_ground_dialogue(
        text,
        connect_codex_chatgpt_provider,
    )
    if isinstance(turn, GroundDialogueProposal):
        existing = MemoryStore(create=False).load_ground_session(
            turn.ground_name
        )
        if existing is not None:
            raise GroundDialogueError(
                f"Ground '{turn.ground_name}' already exists. Refine the "
                "description so the agent can propose a different portable "
                "name, or resume that named Ground explicitly."
            )
    return turn


def _apply_new_ground_proposal(
    proposal: GroundShellProposal,
) -> str:
    """Run the exact creation argv frozen by the approval screen."""
    store = MemoryStore(create=False)
    if store.load_ground_session(proposal.ground_name) is not None:
        raise GroundError(
            f"Ground '{proposal.ground_name}' was created before approval; "
            "nothing was overwritten."
        )
    argv = proposal_argv(proposal)
    try:
        result = _run_approved_ground_command(argv)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GroundError(
            "The approved Ground command could not be completed; nothing "
            "was confirmed as applied."
        ) from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GroundError(
            "The approved Ground command failed"
            + (f": {safe_terminal_text(detail)}" if detail else ".")
        )
    return result.stdout.strip()


def _run_approved_ground_command(
    argv: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Execute an approved logical ``mem`` argv without invoking a shell."""
    if len(argv) < 2 or argv[:2] != ("mem", "ground"):
        raise GroundError("The approved command is not a Ground command.")
    return subprocess.run(
        [sys.executable, "-m", "memcommit.cli", *argv[1:]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def _run_new_ground_shell(initial_request: str = "") -> None:
    shell_kwargs = {
        "interpret": _interpret_new_ground_turn,
        "apply": _apply_new_ground_proposal,
    }
    if initial_request:
        shell_kwargs["initial_request"] = initial_request
    result = run_ground_shell(**shell_kwargs)
    if result.status == "APPLIED":
        proposal = result.proposal
        if proposal is None:
            raise GroundError(
                "The approved Ground was not available for continuation."
            )
        session = MemoryStore(create=False).load_ground_session(
            proposal.ground_name
        )
        if session is None:
            raise GroundError(
                "The approved Ground could not be reloaded."
            )
        _run_existing_ground_shell(
            session,
            initial_receipt=result.actual_output or "Ground created.",
        )
        return
    typer.echo("Ground dialogue cancelled. Nothing was created.")


def _ground_digest(session: GroundSession) -> str:
    return ground_session_record_digest(session)


def _ground_version_token(session: GroundSession) -> str:
    """Freeze one complete named-Ground state into an opaque CAS token."""
    return (
        f"v1:{session.uid}:{session.revision}:"
        f"{ground_session_record_digest(session)}"
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
        raise GroundError(
            "The expected Ground version token is invalid."
        ) from error
    if (
        not expected_uid
        or expected_revision < 0
        or str(expected_revision) != revision_text
        or len(expected_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_digest
        )
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
            str(
                sum(isinstance(item, Memory) for item in direct_items)
            ),
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
        raise GroundError(
            "An expected Context version token is invalid."
        ) from error
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
        guarded.extend(
            ["--if-context-version", _context_version_token(context)]
        )
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
        raise GroundError(
            "The binding Context set changed after it was reviewed."
        )
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


def _resolve_ground_alias(
    session: GroundSession,
    alias: str,
    *,
    kind: str | None = None,
) -> str:
    selector_by_alias, _payload = ground_turn_aliases(session)
    uid = selector_by_alias.get(alias)
    if uid is None:
        raise GroundError(
            f"Ground turn selector '{alias}' is not in the visible panel."
        )
    item = next(candidate for candidate in session.items if candidate.uid == uid)
    if kind is not None and item.kind != kind:
        raise GroundError(
            f"Ground turn selector '{alias}' is not a {kind.title()}."
        )
    return uid


def _binding_argv(
    session: GroundSession,
    action: GroundTurnAction,
) -> tuple[str, ...]:
    argv = [
        "mem",
        "ground",
        session.contract_name,
        "--description",
        action.description,
        "--raw-context",
        action.raw_context,
        "--derived-context",
        action.derived_context,
        "--publication-target",
        action.publication_target,
    ]
    for target in action.placement_targets:
        argv.extend(["--placement-target", target])
    for blocked in action.blocked_targets:
        argv.extend(
            [
                "--blocked-target",
                f"{blocked.context_name}={blocked.reason}",
            ]
        )
    return tuple(argv)


def _case_argv(
    session: GroundSession,
    action: GroundTurnAction,
    store: MemoryStore,
) -> tuple[tuple[str, ...], Memory]:
    rule_uid = _resolve_ground_alias(session, action.selector, kind="RULE")
    contexts = _load_bound_contexts(store, session)
    candidate_frame = next(
        frame
        for frame in session.frames
        if frame.role == "WORKING_CANDIDATES"
    )
    candidate_context = next(
        context
        for context in contexts
        if context.uid == candidate_frame.context_uid
    )
    matches = [
        item
        for item in candidate_context.iter_items()
        if isinstance(item, Memory)
        and item.uid.startswith(action.source_selector)
    ]
    if len(matches) != 1:
        raise GroundError(
            "The proposed Case source is missing or ambiguous."
        )
    allowed_targets = {
        frame.context_name
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    }
    if not action.targets or any(
        target not in allowed_targets for target in action.targets
    ):
        raise GroundError("The proposed Case names an invalid target.")
    argv = [
        "mem",
        "ground",
        session.contract_name,
        "--propose-source",
        matches[0].uid,
        "--fit-rule",
        rule_uid,
    ]
    for target in action.targets:
        argv.extend(["--propose-target", target])
    if action.expected:
        argv.extend(["--expected", action.expected])
    argv.extend(
        [
            "--rationale",
            action.rationale,
            "--case-role",
            action.case_role,
            "--disposition",
            action.disposition,
        ]
    )
    return tuple(argv), matches[0]


def _ground_action_proposal(
    session: GroundSession,
    action: GroundTurnAction,
) -> GroundCommandProposal:
    store = MemoryStore(create=False)
    kind = action.kind
    bound = session.schema_version == GROUND_SCHEMA_VERSION
    if (kind == "BIND") == bound:
        raise GroundError(
            "The proposed action does not match the current Ground state."
        )
    if bound:
        current_contexts = _load_bound_contexts(store, session)
        if stale_ground_frames(session, current_contexts):
            raise GroundError(
                "Grounding workbench is stale. Refresh or replace its "
                "explicit binding before proposing another command."
            )
    if kind == "BIND":
        names = (
            action.raw_context,
            action.derived_context,
            action.publication_target,
            *action.placement_targets,
        )
        contexts = tuple(store.load(name) for name in names)
        if (
            len(set(names)) != len(names)
            or len({context.uid for context in contexts}) != len(contexts)
        ):
            raise GroundError("Binding Contexts must be independent.")
        expected_context_versions = tuple(
            _context_version_token(context) for context in contexts
        )
        argv = _with_context_version_guards(
            contexts,
            _binding_argv(session, action),
        )
        effects = (
            (
                "Ground binding: SET explicit Task and frozen Context "
                "versions"
            ),
            "Goal: unchanged",
            "Rules: unchanged",
            "Cases: unchanged",
            "Contexts and Memories: unchanged",
            "Checkpoints: unchanged",
        )
    elif kind == "REVISE_GOAL":
        revised_goal = validate_ground_goal(
            action.content,
            label="revised Ground goal",
        )
        argv = (
            "mem",
            "ground",
            session.contract_name,
            "--revise-goal",
            revised_goal,
            "--change-reason",
            action.rationale,
        )
        effects = (
            "Goal: REVISE",
            "Rules and Cases: unchanged",
            "Contexts and Memories: unchanged",
            "Checkpoints: unchanged",
        )
    elif kind == "PROPOSE_RULE":
        argv = (
            "mem",
            "ground",
            session.contract_name,
            "--propose-rule",
            action.content,
            "--rationale",
            action.rationale,
            "--rule-provenance",
            action.rule_provenance,
        )
        effects = (
            "Rules: ADD one PROPOSED Rule",
            "Acceptance: unchanged; proposal is not approval",
            "Goal and Cases: unchanged",
            "Contexts and Memories: unchanged",
            "Checkpoints: unchanged",
        )
    elif kind == "PROPOSE_CASE":
        argv, source_memory = _case_argv(session, action, store)
        effects = (
            "Cases: ADD one traceable PROPOSED Case",
            (
                f"Source Memory [{source_memory.uid[:8]}]: "
                f"{source_memory.content}"
            ),
            "Linked Rule: relation only; acceptance unchanged",
            "Goal: unchanged",
            "Contexts and Memories: unchanged",
            "Checkpoints: unchanged",
        )
    elif kind == "REVIEW_ITEM":
        item_uid = _resolve_ground_alias(session, action.selector)
        argv_list = [
            "mem",
            "ground",
            session.contract_name,
            "--decide",
            item_uid,
            "--action",
            action.decision,
        ]
        if action.response:
            argv_list.extend(["--response", action.response])
        argv = tuple(argv_list)
        effects = (
            f"Selected Rule/Case: {action.decision}",
            "One review Decision: RECORD",
            "Other Goal–Rules–Cases items: unchanged",
            "Contexts and Memories: unchanged",
            "Checkpoints: unchanged",
        )
    else:  # pragma: no cover - validated semantic union
        raise GroundError("Unsupported Ground turn action.")
    guarded_argv = _with_ground_version_guard(session, tuple(argv))
    return GroundCommandProposal(
        kind=kind,
        understanding=action.understanding,
        question=action.question,
        review=ExactCommandReview(
            argv=guarded_argv,
            effects=(
                (
                    "Precondition: apply only to the reviewed Ground at "
                    f"revision {session.revision}"
                ),
                *effects,
            ),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest=_ground_digest(session),
        expected_context_versions=(
            expected_context_versions if kind == "BIND" else ()
        ),
    )


_MEMORY_SELECTOR_TOKEN = re.compile(
    r"(?<![0-9A-Za-z])[0-9A-Fa-f][0-9A-Fa-f-]{3,35}(?![0-9A-Za-z])"
)
_UUID_TOKEN = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)


def _redact_ground_source_selectors(
    session: GroundSession,
    text: str,
    store: MemoryStore,
) -> tuple[str, dict[str, str]]:
    """Replace locally resolvable candidate UID selectors before inference."""
    if session.schema_version != GROUND_SCHEMA_VERSION:
        return text, {}
    candidate_frame = next(
        frame
        for frame in session.frames
        if frame.role == "WORKING_CANDIDATES"
    )
    candidate_context = store.load(candidate_frame.context_name)
    memories = tuple(
        item
        for item in candidate_context.iter_items()
        if isinstance(item, Memory)
    )
    alias_by_uid = {
        memory.uid: f"m{index}"
        for index, memory in enumerate(memories, start=1)
    }
    selector_by_alias: dict[str, str] = {}

    def redact(match: re.Match[str]) -> str:
        token = match.group(0)
        normalized = token.casefold()
        matches = tuple(
            memory
            for memory in memories
            if memory.uid.casefold().startswith(normalized)
        )
        if len(matches) == 1:
            alias = alias_by_uid[matches[0].uid]
            selector_by_alias[alias] = matches[0].uid
            return alias
        if matches:
            return "<ambiguous-memory-selector>"
        if (
            _UUID_TOKEN.fullmatch(token)
            or (
                len(token) >= 8
                and (
                    "-" not in token
                    or token[8:9] == "-"
                )
            )
        ):
            return "<unrecognized-identifier>"
        return token

    return _MEMORY_SELECTOR_TOKEN.sub(redact, text), selector_by_alias


def _interpret_named_ground_turn(
    session: GroundSession,
    text: str,
):
    store = MemoryStore(create=False)
    provider_text, source_selector_by_alias = (
        _redact_ground_source_selectors(session, text, store)
    )
    turn = interpret_ground_turn(
        session,
        provider_text,
        connect_codex_chatgpt_provider,
    )
    if isinstance(turn, GroundTurnAction):
        if turn.kind == "PROPOSE_CASE":
            source_uid = source_selector_by_alias.get(
                turn.source_selector
            )
            if source_uid is None:
                raise GroundError(
                    "A Case proposal must use a source Memory selector "
                    "supplied in this visible turn."
                )
            turn = replace(turn, source_selector=source_uid)
        return _ground_action_proposal(session, turn)
    return turn


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
        raise GroundError(
            "The reviewed Ground command lost its frozen version guard."
        )
    cursor = 5
    actual_context_versions: list[str] = []
    while (
        cursor + 1 < len(argv)
        and argv[cursor] == "--if-context-version"
    ):
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
            "The reviewed Ground command lost its frozen Context guards."
        )
    if proposal.kind == "BIND":
        if not expected_context_versions:
            raise GroundError(
                "A reviewed Ground binding requires Context guards."
            )
        parsed = tuple(
            _parse_context_version_token(value)
            for value in expected_context_versions
        )
        if len({value[0] for value in parsed}) != len(parsed):
            raise GroundError(
                "A reviewed Ground binding contains duplicate Context guards."
            )
    elif expected_context_versions:
        raise GroundError(
            "Only a reviewed Ground binding may carry Context guards."
        )


def _apply_named_ground_proposal(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[GroundSession, str]:
    _validate_named_ground_proposal_command(session, proposal)
    store = MemoryStore(create=False)
    latest = store.load_ground_session(session.contract_name)
    if latest is None or latest.uid != proposal.expected_ground_uid:
        raise GroundError(
            "The named Ground changed identity before approval."
        )
    if (
        latest.revision != proposal.expected_revision
        or _ground_digest(latest) != proposal.expected_state_digest
    ):
        raise GroundError(
            "The named Ground changed after this proposal. Refine the turn "
            "against the refreshed state."
        )
    try:
        result = _run_approved_ground_command(proposal.review.argv)
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


def _run_existing_ground_shell(
    session: GroundSession,
    *,
    initial_receipt: str = "",
) -> None:
    def reload_session(contract_name: str) -> GroundSession:
        refreshed = MemoryStore(create=False).load_ground_session(contract_name)
        if refreshed is None:
            raise GroundError(
                f"Named Ground '{contract_name}' no longer exists."
            )
        return refreshed

    result = run_named_ground_shell(
        session,
        interpret=_interpret_named_ground_turn,
        apply=_apply_named_ground_proposal,
        reload_session=reload_session,
        initial_receipt=initial_receipt,
    )
    typer.echo(
        f"Ground dialogue closed. {len(result.applied_argvs)} approved "
        "command(s) applied in this named-Ground view."
    )
    typer.echo(
        f"Ground '{result.session.contract_name}' remains saved at "
        f"revision {result.session.revision}."
    )


def _count_items(session: GroundSession, kind: str) -> int:
    return sum(item.kind == kind for item in session.items)


def _frame_contexts_by_uid(
    contexts: Iterable[Context],
) -> dict[str, Context]:
    return {context.uid: context for context in contexts}


def _accepted_case_count(session: GroundSession, target_uid: str) -> int:
    return accepted_ground_case_count(session, target_uid)


def _render_unbound_snapshot(session: GroundSession) -> str:
    open_issues = sum(
        item.kind == "ISSUE" and item.status != "RESOLVED"
        for item in session.items
    )
    goal = session.goal or "(not yet stated)"
    scope = ", ".join(session.scope) if session.scope else "(unbound)"
    lines = [
        (
            f"GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status}"
        ),
        f"Revision: {session.revision}",
        "",
        "GOAL",
        f"  {safe_terminal_text(goal)}",
        "",
        f"SCOPE  {safe_terminal_text(scope)}",
        (
            f"RULES {_count_items(session, 'RULE')} · "
            f"CASES {_count_items(session, 'CASE')} · "
            f"UNRESOLVED {open_issues} · "
            f"DECISIONS {_count_items(session, 'DECISION')}"
        ),
        "",
        "No grounding material has been recorded.",
        "The session is ready to bind a Task description and Context frames.",
    ]
    return "\n".join(lines)


def _render_contract_layers(
    session: GroundSession,
    frame_name_by_uid: dict[str, str],
) -> list[str]:
    rules = [item for item in session.items if item.kind == "RULE"]
    cases = [item for item in session.items if item.kind == "CASE"]
    decisions = [item for item in session.items if item.kind == "DECISION"]
    lines = ["2 · RULES · DISTILLED / INDUCED"]
    if not rules:
        lines.append("  (none yet; distill from the Goal or induct from cases)")
    for item in rules:
        lines.append(
            f"  [{item.status} · {item.rule_provenance}] "
            f"[{item.uid[:8]}] "
            f"{safe_terminal_text(item.content)}"
        )
        if item.rationale:
            lines.append(
                f"    why: {safe_terminal_text(item.rationale)}"
            )
    lines.extend(["", "3 · CASES · FIT / BOUNDARY / CONTRAST"])
    if not cases:
        lines.append("  (none yet; proposed cases do not count as golden)")
    for item in cases:
        targets = ", ".join(
            frame_name_by_uid.get(uid, uid[:8])
            for uid in item.target_context_uids
        )
        related_rules = ", ".join(
            f"[{uid[:8]}]"
            for uid in item.related_uids
            if any(rule.uid == uid for rule in rules)
        )
        source = item.source_refs[0]
        lines.extend(
            [
                (
                    f"  [{item.status} · {item.case_role} · "
                    f"{item.disposition}] "
                    f"[{item.uid[:8]}] "
                    f"{safe_terminal_text(item.content)}"
                ),
                f"    rule: {related_rules or '(none)'}",
                (
                    f"    source: [{source.memory_uid[:8]}] in "
                    f"{safe_terminal_text(frame_name_by_uid.get(source.context_uid, source.context_uid[:8]))} "
                    f"· sha256:{source.content_digest[:12]}"
                ),
                f"    target: {safe_terminal_text(targets)}",
                (
                    f"    expected: {safe_terminal_text(item.expected)}"
                    if item.expected
                    else "    expected: (none)"
                ),
                f"    why: {safe_terminal_text(item.rationale)}",
            ]
        )
    if decisions:
        lines.extend(
            [
                "",
                f"REVISION LOG · {len(decisions)} decisions",
            ]
        )
        for item in decisions[-5:]:
            lines.append(
                f"  [{item.iteration}] {safe_terminal_text(item.content)} "
                f"— {safe_terminal_text(item.rationale)}"
            )
    return lines


def render_ground_snapshot(
    session: GroundSession,
    contexts: Iterable[Context] | None = None,
) -> str:
    """Render a stable, control-character-safe grounding frame."""
    if session.schema_version != GROUND_SCHEMA_VERSION:
        lines = _render_unbound_snapshot(session).splitlines()
        lines.extend(["", "METHOD READINGS"])
        for reference in session.references:
            lines.extend(
                [
                    (
                        f"  [{reference.reading_status} · agent-suggested] "
                        f"{safe_terminal_text(reference.title)}"
                    ),
                    f"    {safe_terminal_text(reference.url)}",
                ]
            )
        lines.extend(
            [
                "",
                "No Context or Memory changes have been applied.",
                "No checkpoint has been created.",
            ]
        )
        return "\n".join(lines)

    contexts_loaded = contexts is not None
    current_contexts = tuple(contexts or ())
    current_by_uid = _frame_contexts_by_uid(current_contexts)
    stale_names = (
        set(stale_ground_frames(session, current_contexts))
        if contexts_loaded
        else set()
    )
    frame_by_uid = {frame.context_uid: frame for frame in session.frames}
    frame_name_by_uid = {
        frame.context_uid: frame.context_name for frame in session.frames
    }
    raw = next(
        frame for frame in session.frames if frame.role == "RAW_EVIDENCE"
    )
    derived = next(
        frame
        for frame in session.frames
        if frame.role == "WORKING_CANDIDATES"
    )
    target_frames = [
        frame
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    ]
    freshness = (
        "FRESH"
        if contexts_loaded and not stale_names
        else ("STALE" if contexts_loaded else "BOUND")
    )
    lines = [
        (
            f"GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status} · {freshness}"
        ),
        f"Revision: {session.revision}",
        "",
        "SOURCE BRIEF · FIXED INPUT",
        f"  {safe_terminal_text(session.brief.content)}",
        "",
        "1 · GOAL",
        f"  {safe_terminal_text(session.goal or '(not yet stated)')}",
        "",
        "  TARGET REQUIREMENTS",
        (
            "    The Goal and requirements may be revised when cases expose "
            "a bad boundary."
        ),
    ]
    for requirement in session.requirements:
        frame = frame_by_uid[requirement.target_context_uid]
        status = target_requirement_status(session, requirement)
        accepted = _accepted_case_count(session, frame.context_uid)
        lines.append(
            f"    [{status:<7}] {safe_terminal_text(frame.context_name)} "
            f"· {frame.direct_memory_count} direct Memories "
            f"· {accepted}/{requirement.minimum_accepted_cases} accepted "
            f"[{requirement.uid[:8]}]"
        )
        lines.append(
            f"               {safe_terminal_text(requirement.description)}"
        )
        if requirement.blocked_reason:
            lines.append(
                "               BLOCKED: "
                + safe_terminal_text(requirement.blocked_reason)
            )

    lines.extend(["", *_render_contract_layers(session, frame_name_by_uid)])
    lines.extend(
        [
            "",
            "WORKBENCH",
            (
                f"  {raw.direct_memory_count} RAW → "
                f"{derived.direct_memory_count} CANDIDATES → "
                f"{len(target_frames)} TARGETS"
            ),
        ]
    )
    display_role = {
        "RAW_EVIDENCE": "RAW",
        "WORKING_CANDIDATES": "DERIVED",
    }
    for frame in (raw, derived):
        marker = (
            "STALE"
            if frame.context_name in stale_names
            else ("FRESH" if contexts_loaded else "BOUND")
        )
        lines.append(
            f"  [{marker}] {display_role[frame.role]:<7} "
            f"{safe_terminal_text(frame.context_name)} "
            f"· {frame.direct_memory_count} Memories"
        )
    lines.append(
        "  TARGETS "
        f"{len(target_frames)} · DIRECT MEMORIES "
        f"{sum(frame.direct_memory_count for frame in target_frames)}"
    )

    candidate_context = current_by_uid.get(derived.context_uid)
    candidate_memories = (
        [
            item
            for item in candidate_context.iter_items()
            if isinstance(item, Memory)
        ]
        if candidate_context is not None
        else []
    )
    lines.extend(["", "SELECTED CANDIDATE"])
    if derived.direct_memory_count == 0:
        lines.append("  (none; 0/0)")
    elif candidate_memories and session.cursor_position < len(candidate_memories):
        memory = candidate_memories[session.cursor_position]
        lines.extend(
            [
                (
                    f"  {session.cursor_position + 1}/"
                    f"{len(candidate_memories)} [{memory.uid[:8]}]"
                ),
                f"  {safe_terminal_text(memory.content)}",
            ]
        )
    else:
        lines.append(
            f"  {session.cursor_position + 1}/"
            f"{derived.direct_memory_count} (content not loaded)"
        )

    if stale_names:
        lines.extend(
            [
                "",
                "STALE FRAMES",
                *[
                    f"  {safe_terminal_text(name)}"
                    for name in sorted(stale_names)
                ],
                "  Ground changes and Case decisions are blocked.",
            ]
        )

    lines.extend(["", "METHOD READINGS"])
    for reference in session.references:
        lines.append(
            f"  [{reference.reading_status} · agent-suggested] "
            f"{safe_terminal_text(reference.title)}"
        )
    lines.extend(
        [
            "",
            "Grounding changed only this named Ground.",
            "No Context or Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )
    return "\n".join(lines)


def _focused_target(
    session: GroundSession,
    selector: str,
):
    requirement = resolve_ground_requirement(session, selector)
    frame_by_uid = {
        frame.context_uid: frame
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    }
    frame = frame_by_uid.get(requirement.target_context_uid)
    if frame is None:
        raise GroundError("Focused Ground target is missing or ambiguous.")
    return requirement, frame


def _current_direct_memory_count(context: Context | None) -> int | None:
    if context is None:
        return None
    return sum(isinstance(item, Memory) for item in context.iter_items())


def render_ground_focus(
    session: GroundSession,
    target_selector: str,
    contexts: Iterable[Context],
) -> str:
    """Render one compact, read-only Goal–Rules–Cases target frame."""
    if session.schema_version != GROUND_SCHEMA_VERSION:
        raise GroundError(
            "Bind the named Ground before focusing one of its targets."
        )
    current_contexts = tuple(contexts)
    current_by_uid = _frame_contexts_by_uid(current_contexts)
    stale_names = set(stale_ground_frames(session, current_contexts))
    requirement, target = _focused_target(session, target_selector)
    raw = next(
        frame for frame in session.frames if frame.role == "RAW_EVIDENCE"
    )
    candidates = next(
        frame
        for frame in session.frames
        if frame.role == "WORKING_CANDIDATES"
    )
    freshness = "STALE" if stale_names else "FRESH"
    target_status = target_requirement_status(session, requirement)
    accepted = _accepted_case_count(session, target.context_uid)
    rules = [item for item in session.items if item.kind == "RULE"]
    cases = [item for item in session.items if item.kind == "CASE"]
    accepted_items = sum(
        item.kind in {"RULE", "CASE"} and item.status == "ACCEPTED"
        for item in session.items
    )

    def material_line(label: str, frame) -> str:
        current_count = _current_direct_memory_count(
            current_by_uid.get(frame.context_uid)
        )
        if frame.context_name not in stale_names:
            count = frame.direct_memory_count
            suffix = f"{count} Memories"
        elif current_count is None:
            suffix = (
                f"{frame.direct_memory_count} bound Memories · current missing"
            )
        else:
            suffix = (
                f"{frame.direct_memory_count} bound · "
                f"{current_count} current Memories"
            )
        return (
            f"  {label:<12}"
            f"{safe_terminal_text(frame.context_name)} · {suffix}"
        )

    lines = [
        (
            f"MEM GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status} · {freshness}"
        ),
        f"Revision: {session.revision}",
        f"FOCUS · {safe_terminal_text(target.context_name)}",
        "",
        "GOAL",
        f"  {safe_terminal_text(session.goal or '(not yet stated)')}",
        "",
        "BOUND MATERIAL",
        material_line("RAW", raw),
        material_line("CANDIDATES", candidates),
        material_line("TARGET", target),
        "",
        "MEM UNDERSTANDS",
        (
            f"  [{target_status}] "
            f"{safe_terminal_text(requirement.description)}"
        ),
    ]
    if requirement.blocked_reason:
        lines.extend(
            [
                (
                    "  The saved Ground records this missing material: "
                    f"{safe_terminal_text(requirement.blocked_reason)}"
                ),
                (
                    "  Bound evidence may support a target slice, but it "
                    "does not by itself remove this recorded gap."
                ),
            ]
        )
    else:
        lines.append(
            f"  Accepted support: {accepted}/"
            f"{requirement.minimum_accepted_cases} Cases."
        )

    if stale_names:
        lines.extend(
            [
                "",
                "OPEN QUESTION · REQUIRED",
                (
                    "  The bound material changed. Create a fresh named "
                    "Ground or explicitly replace and rebind this one "
                    "before changing Goal, Rules, or Cases."
                ),
                "",
                "STALE BOUND MATERIAL",
                *[
                    f"  {safe_terminal_text(name)}"
                    for name in sorted(stale_names)
                ],
            ]
        )
    elif requirement.blocked_reason:
        lines.extend(
            [
                "",
                "OPEN QUESTION · REQUIRED",
                (
                    "  How should the current evidence and the missing "
                    "target material divide this Ground?"
                ),
                "",
                "    1  SUPPORTED SLICE",
                (
                    "       Ground only Cases supported by the bound "
                    "evidence and keep the missing material explicit."
                ),
                "",
                "    2  COMPLETE TARGET",
                (
                    "       Keep the full target as the scope boundary and "
                    "remain blocked until evidence is supplied."
                ),
                "",
                "  > 3  BOTH",
                (
                    "       Ground the supported Cases first, then record "
                    "the missing target requirements separately."
                ),
                "",
                "WHY THIS MATTERS",
                (
                    "  The answer changes the agreed scope and may "
                    "require one Goal or target-requirement command."
                ),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "OPEN QUESTION · NEXT",
                "  Which one Ground layer should the next command change?",
                "",
                "    1  GOAL",
                "    2  RULES",
                "    3  CASES",
            ]
        )

    lines.extend(
        [
            "",
            "REFINE, COMMENT, OR ENTER A DIFFERENT READING",
            "",
            "> ________________________________________________________________",
            "",
            "GROUND STATE",
            (
                f"  RULES {len(rules)} "
                f"({sum(item.status == 'PROPOSED' for item in rules)} "
                f"proposed) · "
                f"CASES {len(cases)} "
                f"({sum(item.status == 'PROPOSED' for item in cases)} "
                f"proposed) · "
                f"ACCEPTED {accepted_items}"
            ),
            "",
            "NEXT",
            (
                "  The agent may propose one exact mem command from your "
                "reply."
            ),
            (
                "  That command requires its own approval before the agent "
                "runs it."
            ),
            "",
            "No Context or Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )
    return "\n".join(lines)


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


def _parse_blocked_targets(
    values: list[str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, reason = value.partition("=")
        if not separator or not name.strip() or not reason.strip():
            raise GroundError(
                "--blocked-target must use CONTEXT=REASON."
            )
        if name in result:
            raise GroundError("A blocked target was supplied more than once.")
        result[name] = reason
    return result


def cmd(
    ground_name: Annotated[
        Optional[str],
        typer.Argument(
            metavar="[GROUND_NAME]",
            show_default=False,
            help=(
                "Portable Ground name to create or resume, or a natural-"
                "language starting request when the value cannot be a "
                "portable name; omit to start from a blank, unsaved frame"
            )
        ),
    ] = None,
    request: Annotated[
        Optional[str],
        typer.Option(
            "--request",
            help=(
                "Explicit unsaved starting request; useful when its text "
                "also looks like a portable Ground name"
            ),
        ),
    ] = None,
    goal: Annotated[
        Optional[str],
        typer.Option("--goal", help="Goal for a new named Ground"),
    ] = None,
    scope: Annotated[
        Optional[list[str]],
        typer.Option(
            "--scope",
            help="Descriptive scope label for a new Ground; repeatable",
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option(
            "--description",
            help="Task description copied into an explicit frame binding",
        ),
    ] = None,
    raw_context: Annotated[
        Optional[str],
        typer.Option(
            "--raw-context",
            help="Raw-evidence Context for an explicit frame binding",
        ),
    ] = None,
    derived_context: Annotated[
        Optional[str],
        typer.Option(
            "--derived-context",
            help="Working-candidate Context for an explicit frame binding",
        ),
    ] = None,
    publication_target: Annotated[
        Optional[str],
        typer.Option(
            "--publication-target",
            help="Publication target Context for an explicit binding",
        ),
    ] = None,
    placement_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--placement-target",
            help="Placement target Context; repeat for every required slot",
        ),
    ] = None,
    blocked_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--blocked-target",
            metavar="CONTEXT=REASON",
            help="Record one known target-fixture gap; repeatable",
        ),
    ] = None,
    focus_target: Annotated[
        Optional[str],
        typer.Option(
            "--focus-target",
            help=(
                "Show one compact target-focused Ground; may accompany one "
                "Goal or target-requirement revision"
            ),
        ),
    ] = None,
    select: Annotated[
        Optional[int],
        typer.Option(
            "--select",
            min=1,
            help="Select one 1-based working-candidate position",
        ),
    ] = None,
    propose_source: Annotated[
        Optional[str],
        typer.Option(
            "--propose-source",
            help="Working-candidate Memory uid or unambiguous prefix",
        ),
    ] = None,
    propose_rule: Annotated[
        Optional[str],
        typer.Option(
            "--propose-rule",
            help="New Rule; may be proposed before any Case",
        ),
    ] = None,
    fit_rule: Annotated[
        Optional[str],
        typer.Option(
            "--fit-rule",
            help="Existing Rule uid/prefix for a new Case",
        ),
    ] = None,
    propose_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--propose-target",
            help="Target Context for this case; repeatable",
        ),
    ] = None,
    expected: Annotated[
        Optional[str],
        typer.Option(
            "--expected",
            help="Expected target wording or result for a proposed case",
        ),
    ] = None,
    rationale: Annotated[
        Optional[str],
        typer.Option("--rationale", help="Reason for the proposed judgment"),
    ] = None,
    case_role: Annotated[
        Optional[str],
        typer.Option(
            "--case-role",
            help="FIT, BOUNDARY, or CONTRAST",
        ),
    ] = None,
    disposition: Annotated[
        Optional[str],
        typer.Option(
            "--disposition",
            help="INCLUDE, EXCLUDE, or UNRESOLVED",
        ),
    ] = None,
    rule_provenance: Annotated[
        Optional[str],
        typer.Option(
            "--rule-provenance",
            help=(
                "USER_STATED, DISTILLED_FROM_GOAL, "
                "or INDUCED_FROM_CASES; review creates JOINTLY_REVISED"
            ),
        ),
    ] = None,
    decide: Annotated[
        Optional[str],
        typer.Option(
            "--decide",
            help="Proposed rule/case uid or prefix to review",
        ),
    ] = None,
    action: Annotated[
        Optional[str],
        typer.Option(
            "--action",
            help="ACCEPT, REFINE, DEFER, or REJECT",
        ),
    ] = None,
    response: Annotated[
        Optional[str],
        typer.Option(
            "--response",
            help="Review note, or replacement text for REFINE",
        ),
    ] = None,
    revise_target: Annotated[
        Optional[str],
        typer.Option(
            "--revise-target",
            help="Target name or requirement uid/prefix to revise",
        ),
    ] = None,
    revise_goal: Annotated[
        Optional[str],
        typer.Option(
            "--revise-goal",
            help="Replacement top-level working Goal",
        ),
    ] = None,
    requirement_text: Annotated[
        Optional[str],
        typer.Option(
            "--requirement-text",
            help="Replacement target requirement",
        ),
    ] = None,
    minimum_cases: Annotated[
        Optional[int],
        typer.Option(
            "--minimum-cases",
            min=1,
            help="Replacement accepted-case minimum",
        ),
    ] = None,
    blocked_reason: Annotated[
        Optional[str],
        typer.Option(
            "--blocked-reason",
            help="Replacement gap; pass an empty string to clear it",
        ),
    ] = None,
    change_reason: Annotated[
        Optional[str],
        typer.Option(
            "--change-reason",
            help="Why the Goal or target requirement should change",
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the complete stable session frame",
        ),
    ] = False,
    replace_ground: Annotated[
        bool,
        typer.Option(
            "--replace-ground",
            help="Explicitly replace an existing or malformed named Ground",
        ),
    ] = False,
    if_ground_version: Annotated[
        Optional[str],
        typer.Option(
            "--if-ground-version",
            hidden=True,
        ),
    ] = None,
    if_context_version: Annotated[
        Optional[list[str]],
        typer.Option(
            "--if-context-version",
            hidden=True,
        ),
    ] = None,
) -> None:
    """Open or persist Ground judgments without directly editing Contexts."""
    bind_requested = any(
        value is not None
        for value in (
            description,
            raw_context,
            derived_context,
            publication_target,
            placement_target,
            blocked_target,
        )
    )
    proposal_requested = any(
        value is not None
        for value in (
            propose_source,
            propose_rule,
            fit_rule,
            propose_target,
            expected,
            rationale,
            case_role,
            disposition,
            rule_provenance,
        )
    )
    decision_requested = any(
        value is not None for value in (decide, action, response)
    )
    requirement_requested = any(
        value is not None
        for value in (
            revise_target,
            revise_goal,
            requirement_text,
            minimum_cases,
            blocked_reason,
            change_reason,
        )
    )
    action_count = sum(
        (
            bind_requested,
            select is not None,
            proposal_requested,
            decision_requested,
            requirement_requested,
        )
    )

    seed_conflict_requested = (
        any(
            value is not None
            for value in (
                goal,
                scope,
                focus_target,
                select,
            )
        )
        or action_count > 0
        or snapshot
        or replace_ground
        or if_ground_version is not None
        or bool(if_context_version)
    )
    initial_request: str | None = request
    if request is not None and ground_name is not None:
        typer.secho(
            "Ground error: choose either GROUND_NAME_OR_REQUEST or "
            "--request, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if request is not None and seed_conflict_requested:
        typer.secho(
            "Ground error: --request starts an unsaved dialogue and cannot "
            "be combined with Ground options.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if ground_name is not None:
        try:
            validate_ground_contract_name(ground_name)
        except GroundError:
            if seed_conflict_requested:
                typer.secho(
                    "Ground error: a natural-language starting request "
                    "cannot be combined with Ground options. Use a portable "
                    "GROUND_NAME for named actions.",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            # A value that cannot ever identify a saved Ground is safe to
            # reinterpret as the user's first unsaved turn. Valid names keep
            # their historical create/resume behavior.
            initial_request = ground_name
            ground_name = None
    if initial_request is not None:
        try:
            initial_request = _validated_start_request(initial_request)
        except GroundDialogueError as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if _interactive_terminal():
            _run_new_ground_shell(initial_request)
        else:
            typer.echo(render_ground_start(initial_request))
        return

    plain_named_tui_requested = (
        ground_name is not None
        and _interactive_terminal()
        and action_count == 0
        and goal is None
        and scope is None
        and focus_target is None
        and not snapshot
        and not replace_ground
        and if_ground_version is None
        and not if_context_version
    )
    if ground_name is None:
        option_requested = (
            any(
                value is not None
                for value in (
                    goal,
                    scope,
                    focus_target,
                    select,
                )
            )
            or action_count > 0
            or snapshot
            or replace_ground
            or if_ground_version is not None
            or bool(if_context_version)
        )
        if option_requested:
            typer.secho(
                "Ground error: GROUND_NAME is required when using options. "
                "Run 'mem ground' without options to start from a blank "
                "Ground.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if _interactive_terminal():
            _run_new_ground_shell()
        else:
            typer.echo(render_ground_start())
        return

    # Keep the legacy internal name localized; versioned session JSON still
    # uses contract_name, while the CLI presents the user-facing Ground model.
    contract_name = ground_name
    store = MemoryStore(create=False)
    try:
        expected_ground_state = _parse_ground_version_token(
            if_ground_version
        )
        expected_context_versions = tuple(
            _parse_context_version_token(value)
            for value in (if_context_version or ())
        )
        if expected_ground_state is not None and (
            action_count != 1 or replace_ground
        ):
            raise GroundError(
                "The expected Ground version guard requires exactly one "
                "non-replacement Ground action."
            )
        if expected_context_versions and (
            expected_ground_state is None or not bind_requested
        ):
            raise GroundError(
                "Expected Context version guards require one guarded binding "
                "action."
            )

        loaded_session: GroundSession | None = None

        def save_ground(
            value: GroundSession,
            *,
            replace: bool = False,
        ) -> None:
            if expected_ground_state is not None:
                expected_kwargs = {
                    "expected_uid": expected_ground_state[0],
                    "expected_revision": expected_ground_state[1],
                    "expected_digest": expected_ground_state[2],
                }
            elif loaded_session is not None and not replace:
                # Ordinary CLI writers participate in the same CAS boundary
                # as TUI-reviewed commands. Otherwise a stale unguarded
                # writer could overwrite a newer guarded update.
                expected_kwargs = {
                    "expected_uid": loaded_session.uid,
                    "expected_revision": loaded_session.revision,
                    "expected_digest": ground_session_record_digest(
                        loaded_session
                    ),
                }
            else:
                expected_kwargs = {}
            store.save_ground_session(
                value,
                replace=replace,
                verify_bound_frames=(
                    value.schema_version == GROUND_SCHEMA_VERSION
                ),
                **expected_kwargs,
            )

        if snapshot and focus_target is not None:
            raise GroundError(
                "Choose either --snapshot or --focus-target, not both."
            )
        if focus_target is not None and bind_requested:
            raise GroundError(
                "--focus-target requires an already bound Ground. Bind it "
                "first, then focus it in a read-only command."
            )
        if action_count > 1:
            raise GroundError(
                "Bind, select, propose, decide, and revise-target are "
                "separate grounding actions."
            )
        if (
            focus_target is not None
            and action_count == 1
            and not requirement_requested
        ):
            raise GroundError(
                "--focus-target currently combines only with one Goal or "
                "target-requirement revision."
            )
        session = (
            None
            if replace_ground
            else store.load_ground_session(contract_name)
        )
        loaded_session = session
        created = session is None
        if session is not None and any(
            value is not None for value in (goal, scope)
        ):
            raise GroundError(
                "The grounding session already exists. Start it without "
                "creation options, or use --replace-ground explicitly."
            )
        if session is None:
            session = create_ground_session(
                contract_name,
                goal=goal or "",
                scope=tuple(scope or ()),
            )
        if focus_target is not None:
            if session.schema_version != GROUND_SCHEMA_VERSION:
                raise GroundError(
                    "--focus-target requires an existing bound Ground or "
                    "an explicit binding in the same command."
                )
            # A view modifier must be valid before an action is saved. This
            # keeps a typo in --focus-target from turning one approved command
            # into a hidden mutation followed by a rendering error.
            focused_requirement, _ = _focused_target(
                session,
                focus_target,
            )
            if revise_target is not None:
                revised_requirement = resolve_ground_requirement(
                    session,
                    revise_target,
                )
                if revised_requirement.uid != focused_requirement.uid:
                    raise GroundError(
                        "--focus-target and --revise-target must identify "
                        "the same target so the command displays its own "
                        "effect."
                    )

        action_label = "created" if created else "resumed"
        if bind_requested:
            if (
                description is None
                or raw_context is None
                or derived_context is None
                or publication_target is None
            ):
                raise GroundError(
                    "Binding requires --description, --raw-context, "
                    "--derived-context, and --publication-target."
                )
            blocked = _parse_blocked_targets(blocked_target or [])
            target_names = (
                publication_target,
                *(placement_target or ()),
            )
            if len(set(target_names)) != len(target_names):
                raise GroundError("A target Context was supplied more than once.")
            unknown_blocked = set(blocked) - set(target_names)
            if unknown_blocked:
                raise GroundError(
                    "Blocked targets must also be bound targets: "
                    + ", ".join(sorted(unknown_blocked))
                )
            raw = store.load(raw_context)
            derived = store.load(derived_context)
            targets = tuple(store.load(name) for name in target_names)
            specs = (
                GroundTargetSpec(
                    context_name=publication_target,
                    role="PUBLICATION_TARGET",
                    description=(
                        "Maintain the organizational baseline and publish "
                        "every supported campus-facing change."
                    ),
                    blocked_reason=blocked.get(publication_target, ""),
                ),
                *(
                    GroundTargetSpec(
                        context_name=name,
                        role="PLACEMENT_TARGET",
                        description=(
                            "Establish at least one approved, traceable "
                            "placement case for this local category."
                        ),
                        blocked_reason=blocked.get(name, ""),
                    )
                    for name in (placement_target or ())
                ),
            )
            session = bind_ground_workbench(
                session,
                description=description,
                raw_context=raw,
                derived_context=derived,
                target_contexts=targets,
                target_requirements=specs,
            )
            if expected_context_versions:
                _assert_expected_binding_frames(
                    session,
                    expected_context_versions,
                )
            save_ground(
                session,
                replace=replace_ground,
            )
            action_label = "bound"
        elif select is not None:
            contexts = _load_bound_contexts(store, session)
            session = select_ground_candidate(
                session,
                select - 1,
                current_contexts=contexts,
            )
            save_ground(session)
            action_label = "selected"
        elif proposal_requested:
            contexts = _load_bound_contexts(store, session)
            if session.schema_version != GROUND_SCHEMA_VERSION:
                raise GroundError(
                    "Bind the grounding session before proposing rules or "
                    "cases."
                )
            if stale_ground_frames(session, contexts):
                raise GroundError(
                    "Grounding workbench is stale. Create a new named "
                    "Ground, or use --replace-ground and bind fresh frames."
                )
            if propose_rule is not None and fit_rule is not None:
                raise GroundError(
                    "Propose a new rule or fit a case to an existing rule, "
                    "not both."
                )
            case_requested = any(
                value is not None
                for value in (
                    propose_source,
                    fit_rule,
                    propose_target,
                    expected,
                    case_role,
                    disposition,
                )
            )
            if propose_rule is not None and not case_requested:
                if rationale is None:
                    raise GroundError(
                        "A rule proposal requires --rationale."
                    )
                session = propose_ground_rule(
                    session,
                    rule=propose_rule,
                    rationale=rationale,
                    current_contexts=contexts,
                    rule_provenance=(
                        rule_provenance or "DISTILLED_FROM_GOAL"
                    ).upper(),
                )
            else:
                case_disposition = (disposition or "INCLUDE").upper()
                if (
                    propose_source is None
                    or not propose_target
                    or rationale is None
                    or (
                        case_disposition == "INCLUDE"
                        and expected is None
                    )
                ):
                    raise GroundError(
                        "A case proposal requires --propose-source, "
                        "--propose-target, --rationale, and --expected for "
                        "INCLUDE."
                    )
                candidate_frame = next(
                    frame
                    for frame in session.frames
                    if frame.role == "WORKING_CANDIDATES"
                )
                candidate_context = next(
                    context
                    for context in contexts
                    if context.uid == candidate_frame.context_uid
                )
                if not propose_source.strip():
                    raise GroundError(
                        "The proposed source selector cannot be blank."
                    )
                matches = [
                    item
                    for item in candidate_context.iter_items()
                    if isinstance(item, Memory)
                    and item.uid.startswith(propose_source)
                ]
                if len(matches) != 1:
                    raise GroundError(
                        "The proposed source is missing or ambiguous."
                    )
                if fit_rule is not None:
                    if rule_provenance is not None:
                        raise GroundError(
                            "--rule-provenance applies only to a new rule."
                        )
                    session = propose_ground_case(
                        session,
                        rule_selector=fit_rule,
                        case=matches[0].content,
                        source_context_uid=candidate_context.uid,
                        source_memory_uid=matches[0].uid,
                        target_context_names=tuple(propose_target),
                        expected=expected or "",
                        rationale=rationale,
                        current_contexts=contexts,
                        case_role=(case_role or "FIT").upper(),
                        disposition=case_disposition,
                    )
                elif propose_rule is not None:
                    session = propose_ground_round(
                        session,
                        rule=propose_rule,
                        case=matches[0].content,
                        source_context_uid=candidate_context.uid,
                        source_memory_uid=matches[0].uid,
                        target_context_names=tuple(propose_target),
                        expected=expected or "",
                        rationale=rationale,
                        current_contexts=contexts,
                        case_role=(case_role or "FIT").upper(),
                        disposition=case_disposition,
                        rule_provenance=(
                            rule_provenance or "INDUCED_FROM_CASES"
                        ).upper(),
                    )
                else:
                    raise GroundError(
                        "A case proposal requires --fit-rule, or "
                        "--propose-rule to create and link a new rule."
                    )
            save_ground(session)
            action_label = "proposed"
        elif decision_requested:
            if decide is None or action is None:
                raise GroundError(
                    "A decision requires both --decide and --action."
                )
            contexts = _load_bound_contexts(store, session)
            session = review_ground_item(
                session,
                decide,
                action=action,
                response=response or "",
                current_contexts=contexts,
            )
            save_ground(session)
            action_label = action.casefold()
        elif requirement_requested:
            if change_reason is None:
                raise GroundError(
                    "A Goal or target revision requires --change-reason."
                )
            contexts = _load_bound_contexts(store, session)
            if revise_goal is not None:
                if (
                    revise_target is not None
                    or requirement_text is not None
                    or minimum_cases is not None
                    or blocked_reason is not None
                ):
                    raise GroundError(
                        "Revise either the Goal or one target requirement."
                    )
                session = revise_ground_goal(
                    session,
                    revise_goal,
                    reason=change_reason,
                    current_contexts=contexts,
                )
            else:
                if revise_target is None:
                    raise GroundError(
                        "A target revision requires --revise-target."
                    )
                session = revise_ground_requirement(
                    session,
                    revise_target,
                    description=requirement_text,
                    minimum_accepted_cases=minimum_cases,
                    blocked_reason=blocked_reason,
                    reason=change_reason,
                    current_contexts=contexts,
                )
            save_ground(session)
            action_label = "revised Ground"
        elif created:
            save_ground(
                session,
                replace=replace_ground,
            )
    except (
        FileNotFoundError,
        ConcurrentGroundUpdateError,
        GroundError,
        OSError,
        StopIteration,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Ground error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if plain_named_tui_requested:
        _run_existing_ground_shell(session)
        return

    if focus_target is not None:
        try:
            contexts = _load_bound_contexts(
                store,
                session,
                tolerate_missing=True,
            )
            typer.echo(
                render_ground_focus(
                    session,
                    focus_target,
                    contexts,
                )
            )
        except (
            FileNotFoundError,
            GroundError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    if snapshot:
        try:
            contexts = (
                _load_bound_contexts(
                    store,
                    session,
                    tolerate_missing=True,
                )
                if session.schema_version == GROUND_SCHEMA_VERSION
                else None
            )
        except (FileNotFoundError, GroundError, OSError, TypeError, ValueError) as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(render_ground_snapshot(session, contexts))
        return

    typer.secho(
        f"Grounding session '{session.contract_name}' {action_label}.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        f"Revision {session.revision}: "
        f"{_count_items(session, 'RULE')} rules, "
        f"{_count_items(session, 'CASE')} cases, "
        f"{_count_items(session, 'DECISION')} decisions."
    )
    typer.echo(
        f"Inspect it with 'mem ground {session.contract_name} --snapshot'."
    )
    typer.echo("No Context or Memory changes applied. No checkpoint created.")
