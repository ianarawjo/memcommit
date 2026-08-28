"""Interpret and conduct dialogue for persisted Ground sessions."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Literal

import typer

from memcommit.adapters.console.commands.ground.named_shell import (
    GroundCommandProposal,
    run_named_ground_shell,
)
from memcommit.adapters.console.coordination.command_review.model import CommandReview
from memcommit.application.operations.fit.runtime import execute_and_save_ground_fit
from memcommit.application.operations.fit.store import FitStore
from memcommit.application.operations.ground.context_catalog import (
    discover_ground_context_locators,
)
from memcommit.application.operations.ground.dialogue import (
    GROUND_DIALOGUE_USER_TEXT_LIMIT,
)
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GROUND_TEXT_LIMIT,
    GroundError,
    GroundSession,
    is_bound_ground_schema,
    stale_ground_frames,
    validate_ground_goal,
)
from memcommit.application.operations.ground.turn_dialogue import (
    GroundBlockedTarget,
    GroundTurnAction,
    GroundTurnDraft,
    GroundTurnDraftBatch,
    ground_turn_aliases,
    interpret_ground_turn,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import connect_codex_chatgpt_provider

from . import review as session_review


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
        raise GroundError(f"Ground turn selector '{alias}' is not a {kind.title()}.")
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
    contexts = session_review._load_bound_contexts(store, session)
    candidate_frame = next(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    candidate_context = next(
        context for context in contexts if context.uid == candidate_frame.context_uid
    )
    matches = [
        item
        for item in candidate_context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(action.source_selector)
    ]
    if len(matches) != 1:
        raise GroundError("The proposed Ground Memory source is missing or ambiguous.")
    allowed_targets = {
        frame.context_name
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    }
    if not action.targets or any(
        target not in allowed_targets for target in action.targets
    ):
        raise GroundError("The proposed Ground Memory names an invalid target.")
    if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
        if not action.content.strip():
            raise GroundError(
                "A version-3 Ground Memory proposal requires its reviewed proposition."
            )
        argv = [
            "mem",
            "ground",
            session.contract_name,
            "--propose-example",
            action.content,
            "--example-source",
            matches[0].uid,
            "--example-rule",
            rule_uid,
        ]
        for target in action.targets:
            argv.extend(["--example-target", target])
        if action.expected:
            argv.extend(
                [
                    "--example-input",
                    matches[0].content,
                    "--example-expected",
                    action.expected,
                ]
            )
    else:
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
    bound = is_bound_ground_schema(session.schema_version)
    if (kind == "BIND") == bound:
        raise GroundError(
            "The proposed action does not match the current Ground state."
        )
    if bound:
        current_contexts = session_review._load_bound_contexts(store, session)
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
        if len(set(names)) != len(names) or len(
            {context.uid for context in contexts}
        ) != len(contexts):
            raise GroundError("Binding Contexts must be independent.")
        expected_context_versions = tuple(
            session_review._context_version_token(context) for context in contexts
        )
        argv = session_review._with_context_version_guards(
            contexts,
            _binding_argv(session, action),
        )
        effects = (
            ("Ground binding: SET explicit Task and selected Context versions"),
            "Goal: unchanged",
            "Rules: unchanged",
            "Ground Memories: unchanged",
            "Contexts and Context Memories: unchanged",
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
            "Rules and Ground Memories: unchanged",
            "Contexts and Context Memories: unchanged",
            "Checkpoints: unchanged",
        )
    elif kind == "PROPOSE_RULE":
        argv_list = [
            "mem",
            "ground",
            session.contract_name,
            "--propose-rule",
            action.content,
        ]
        for target in action.targets:
            argv_list.extend(["--propose-rule-target", target])
        argv_list.extend(
            [
                "--rationale",
                action.rationale,
                "--rule-provenance",
                action.rule_provenance,
            ]
        )
        argv = tuple(argv_list)
        effects = (
            "Rules: ADD one PROPOSED Rule",
            (
                "Placement targets: "
                + (
                    ", ".join(action.targets)
                    if action.targets
                    else "publication target"
                )
            ),
            "Acceptance: unchanged; proposal is not approval",
            "Goal and Ground Memories: unchanged",
            "Contexts and Context Memories: unchanged",
            "Checkpoints: unchanged",
        )
    elif kind == "PROPOSE_CASE":
        argv, source_memory = _case_argv(session, action, store)
        effects = (
            "Ground Memories: ADD one traceable PROPOSED Ground Memory",
            (
                f"Source Context Memory [{source_memory.uid[:8]}]: "
                f"{source_memory.content}"
            ),
            "Linked Rule: relation only; acceptance unchanged",
            "Goal: unchanged",
            "Contexts and Context Memories: unchanged",
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
            f"Selected Rule/Ground Memory: {action.decision}",
            "One review Decision: RECORD",
            "Other Goal–Rules–Memories items: unchanged",
            "Contexts and Context Memories: unchanged",
            "Checkpoints: unchanged",
        )
    else:  # pragma: no cover - validated semantic union
        raise GroundError("Unsupported Ground turn action.")
    guarded_argv = session_review._with_ground_version_guard(session, tuple(argv))
    return GroundCommandProposal(
        kind=kind,
        understanding=action.understanding,
        question=action.question,
        review=CommandReview(
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
        expected_state_digest=session_review._ground_digest(session),
        expected_context_versions=(expected_context_versions if kind == "BIND" else ()),
    )


def _ground_rule_draft_proposal(
    session: GroundSession,
    draft: GroundTurnDraft,
) -> GroundCommandProposal:
    """Reduce one reviewed unsaved Rule draft through the normal save path."""
    if draft.kind != "RULE" or draft.status != "READY":
        raise GroundError("Only a READY Rule draft can be proposed.")
    if not is_bound_ground_schema(session.schema_version):
        raise GroundError(
            "Bind this Ground to explicit Context frames before proposing a Rule."
        )
    return _ground_action_proposal(
        session,
        GroundTurnAction(
            kind="PROPOSE_RULE",
            understanding=(
                "The selected comment unit is a READY Rule candidate: "
                f"{draft.classification_reason}"
            ),
            question="Approve adding this extracted Rule as PROPOSED?",
            content=draft.content,
            rationale=draft.proposal_rationale,
            rule_provenance=draft.rule_provenance,
            targets=tuple(
                frame.context_name
                for frame in session.frames
                if frame.role == "PUBLICATION_TARGET"
            ),
        ),
    )


def _argv_option_values(argv: tuple[str, ...], option: str) -> tuple[str, ...]:
    return tuple(
        argv[index + 1] for index, value in enumerate(argv[:-1]) if value == option
    )


def _replace_repeatable_argv_option(
    argv: tuple[str, ...],
    *,
    option: str,
    values: tuple[str, ...],
    after: str,
) -> tuple[str, ...]:
    cleaned: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == option:
            if index + 1 >= len(argv):
                raise GroundError(f"The reviewed command has an incomplete {option}.")
            index += 2
            continue
        cleaned.append(argv[index])
        index += 1
    try:
        insertion = cleaned.index(after) + 2
    except ValueError as error:
        raise GroundError(
            "The reviewed Ground command cannot be retargeted."
        ) from error
    replacement = [argument for value in values for argument in (option, value)]
    return tuple((*cleaned[:insertion], *replacement, *cleaned[insertion:]))


def _ground_retarget_proposal(
    session: GroundSession,
    proposal: GroundCommandProposal,
    target_name: str,
) -> GroundCommandProposal:
    """Bind one locally selected placement to the frozen proposal shape."""

    if proposal.kind == "BIND":
        argv = proposal.review.argv
        publication = _argv_option_values(argv, "--publication-target")
        if len(publication) != 1 or publication[0] == target_name:
            raise GroundError(
                "A direct placement target must differ from the publication target."
            )
        blocked: list[GroundBlockedTarget] = []
        for raw in _argv_option_values(argv, "--blocked-target"):
            name, separator, reason = raw.partition("=")
            if separator and name in {publication[0], target_name}:
                blocked.append(GroundBlockedTarget(name, reason))
        required = {
            option: _argv_option_values(argv, option)
            for option in (
                "--description",
                "--raw-context",
                "--derived-context",
            )
        }
        if any(len(values) != 1 for values in required.values()):
            raise GroundError("The reviewed Ground binding cannot be retargeted.")
        return _ground_action_proposal(
            session,
            GroundTurnAction(
                kind="BIND",
                understanding=proposal.understanding,
                question=proposal.question,
                description=required["--description"][0],
                raw_context=required["--raw-context"][0],
                derived_context=required["--derived-context"][0],
                publication_target=publication[0],
                placement_targets=(target_name,),
                blocked_targets=tuple(blocked),
            ),
        )
    option_and_anchor = {
        "PROPOSE_RULE": ("--propose-rule-target", "--propose-rule"),
        "PROPOSE_CASE": (
            ("--example-target", "--propose-example")
            if "--propose-example" in proposal.review.argv
            else ("--propose-target", "--propose-source")
        ),
    }.get(proposal.kind)
    if option_and_anchor is None:
        raise GroundError("This Ground proposal has no placement target.")
    option, anchor = option_and_anchor
    argv = _replace_repeatable_argv_option(
        proposal.review.argv,
        option=option,
        values=(target_name,),
        after=anchor,
    )
    effects = tuple(
        effect
        for effect in proposal.review.effects
        if not effect.startswith("Placement targets:")
    )
    return replace(
        proposal,
        review=CommandReview(
            argv=argv,
            effects=(
                *effects,
                f"Placement target: {target_name} · direct local selection",
            ),
        ),
    )


def _ground_direct_edit_proposal(
    session: GroundSession,
    target: str,
    selector: str,
    edited: str,
    comment: str,
) -> GroundCommandProposal:
    """Freeze one pane-local replacement without model rewriting.

    The comment may explain the edit, but the direct field is authoritative:
    it is copied verbatim into the one reviewed mutation. Context binding and
    source Ground Memory text deliberately have no equivalent free-text path.
    """
    if not isinstance(edited, str) or not edited.strip():
        raise GroundError("A direct Ground edit cannot be blank.")
    if len(edited) > GROUND_TEXT_LIMIT:
        raise GroundError("A direct Ground edit is too long.")
    explanation = comment.strip()
    if len(explanation) > GROUND_DIALOGUE_USER_TEXT_LIMIT:
        raise GroundError("A Ground agent comment is too long.")
    if not is_bound_ground_schema(session.schema_version):
        raise GroundError(
            "This saved Ground is still an empty unbound scaffold. Edit its "
            "Goal before creation, or bind it before revising saved items."
        )
    if target == "GOAL":
        action = GroundTurnAction(
            kind="REVISE_GOAL",
            understanding=(
                "The Goal pane contains an exact direct replacement."
                + (f" Agent comment: {explanation}" if explanation else "")
            ),
            question="Approve replacing the Goal with this exact wording?",
            content=edited,
            rationale=(explanation or "Direct edit submitted in the Goal pane."),
        )
    elif target in {"RULE", "MEMORY"}:
        expected_kind = "RULE" if target == "RULE" else "CASE"
        item_uid = _resolve_ground_alias(
            session,
            selector,
            kind=expected_kind,
        )
        item = next(
            candidate for candidate in session.items if candidate.uid == item_uid
        )
        if item.status not in {"PROPOSED", "ACCEPTED"}:
            raise GroundError(
                f"{target.title()} {selector} is {item.status}; only a "
                "PROPOSED or ACCEPTED item can be directly refined."
            )
        layer = (
            "Rule"
            if target == "RULE"
            else (
                "Ground Memory proposition"
                if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                else "Ground Memory expected output"
            )
        )
        action = GroundTurnAction(
            kind="REVIEW_ITEM",
            understanding=(
                f"The selected {layer} contains an exact direct replacement."
                + (f" Agent comment: {explanation}" if explanation else "")
            ),
            question=f"Approve replacing this {layer} with the exact edit?",
            selector=selector,
            decision="REFINE",
            response=edited,
        )
    else:
        raise GroundError("This Ground pane does not support direct editing.")
    return _ground_action_proposal(session, action)


def _ground_example_use_proposal(
    session: GroundSession,
    selector: str,
) -> GroundCommandProposal:
    """Freeze one binary USE change without invoking the provider."""

    if not is_bound_ground_schema(session.schema_version):
        raise GroundError("Bind this Ground before changing Example USE.")
    contexts = session_review._load_bound_contexts(
        MemoryStore(create=False),
        session,
    )
    if stale_ground_frames(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Refresh or replace its explicit "
            "binding before changing Example USE."
        )
    item_uid = _resolve_ground_alias(session, selector, kind="CASE")
    item = next(candidate for candidate in session.items if candidate.uid == item_uid)
    if item.status not in {"PROPOSED", "ACCEPTED"}:
        raise GroundError(
            f"Memory {selector} is {item.status}; only a PROPOSED or ACCEPTED "
            "Example can change USE."
        )
    next_use = "EXCLUDE" if item.disposition == "INCLUDE" else "INCLUDE"
    argv = session_review._with_ground_version_guard(
        session,
        (
            "mem",
            "ground",
            session.contract_name,
            "--set-example-use",
            item.uid,
            "--use",
            next_use,
        ),
    )
    return GroundCommandProposal(
        kind="SET_EXAMPLE_USE",
        understanding=(
            f"Memory {selector} will be "
            f"{'used' if next_use == 'INCLUDE' else 'excluded'} by future "
            "Fit and Ground Distill runs."
        ),
        question=f"Approve setting Memory {selector} USE to {next_use}?",
        review=CommandReview(
            argv=argv,
            effects=(
                (
                    "Precondition: apply only to the reviewed Ground at "
                    f"revision {session.revision}"
                ),
                f"Memory {selector} USE: {item.disposition} -> {next_use}",
                "Future Fit and Ground Distill input: REFREEZE",
                "Existing Fit receipts: retained but stale",
                "Rules, Contexts, and Context Memories: unchanged",
            ),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest=session_review._ground_digest(session),
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
    if not is_bound_ground_schema(session.schema_version):
        return text, {}
    candidate_frame = next(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    candidate_context = store.load(candidate_frame.context_name)
    memories = tuple(
        item for item in candidate_context.iter_items() if isinstance(item, Memory)
    )
    alias_by_uid = {
        memory.uid: f"m{index}" for index, memory in enumerate(memories, start=1)
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
        if _UUID_TOKEN.fullmatch(token) or (
            len(token) >= 8 and ("-" not in token or token[8:9] == "-")
        ):
            return "<unrecognized-identifier>"
        return token

    return _MEMORY_SELECTOR_TOKEN.sub(redact, text), selector_by_alias


def _interpret_named_ground_turn(
    session: GroundSession,
    dialogue_text: str,
    draft_source_text: str,
):
    store = MemoryStore(create=False)
    provider_text, source_selector_by_alias = _redact_ground_source_selectors(
        session, dialogue_text, store
    )
    provider_source_text, _source_aliases = _redact_ground_source_selectors(
        session,
        draft_source_text,
        store,
    )
    turn = interpret_ground_turn(
        session,
        provider_text,
        connect_codex_chatgpt_provider,
        draft_source_text=provider_source_text,
    )
    if (
        isinstance(turn, GroundTurnDraftBatch)
        and provider_source_text != draft_source_text
    ):
        # An mN alias is intentionally ephemeral and cannot be represented as
        # an exact quote from the person's comment or saved as Rule wording.
        raise GroundError(
            "Ground comment classification cannot preserve exact source "
            "spans when the submitted turn contains Memory selectors. "
            "Remove those selectors or handle the referenced Ground Memory "
            "separately."
        )
    if isinstance(turn, GroundTurnAction):
        if turn.kind == "PROPOSE_CASE":
            source_uid = source_selector_by_alias.get(turn.source_selector)
            if source_uid is None:
                raise GroundError(
                    "A Ground Memory proposal must use a source Context "
                    "Memory selector supplied in this visible turn."
                )
            turn = replace(turn, source_selector=source_uid)
        return _ground_action_proposal(session, turn)
    return turn


def _run_existing_ground_shell(
    session: GroundSession,
    *,
    initial_receipt: str = "",
    context_hints: tuple[str, ...] = (),
    new_context_hint: str | None = None,
) -> Literal["CLOSED", "BACK_TO_PICKER"]:
    placement_catalog_names = tuple(
        locator.name
        for locator in discover_ground_context_locators(MemoryStore(create=False))
    )

    def reload_session(contract_name: str) -> GroundSession:
        refreshed = MemoryStore(create=False).load_ground_session(contract_name)
        if refreshed is None:
            raise GroundError(f"Named Ground '{contract_name}' no longer exists.")
        return refreshed

    def run_fit(active: GroundSession):
        return execute_and_save_ground_fit(
            store=MemoryStore(create=False),
            ground_name=active.contract_name,
            provider_factory=connect_codex_chatgpt_provider,
        )

    def lookup_fit(active: GroundSession):
        return FitStore(MemoryStore(create=False)).latest_for_ground(active)

    result = run_named_ground_shell(
        session,
        interpret=_interpret_named_ground_turn,
        apply=session_review._apply_named_ground_proposal,
        prepare_rule_draft=_ground_rule_draft_proposal,
        prepare_direct_edit=_ground_direct_edit_proposal,
        prepare_use_toggle=_ground_example_use_proposal,
        retarget_proposal=_ground_retarget_proposal,
        reload_session=reload_session,
        run_fit=run_fit,
        lookup_fit=lookup_fit,
        auto_fit=True,
        initial_receipt=initial_receipt,
        context_hints=context_hints,
        new_context_hint=new_context_hint,
        placement_catalog_names=placement_catalog_names,
    )
    if result.status == "BACK_TO_PICKER":
        return "BACK_TO_PICKER"
    typer.echo(
        f"Ground chat closed. {len(result.applied_argvs)} approved "
        "command(s) applied in this named-Ground view."
    )
    typer.echo(
        f"Ground '{result.session.contract_name}' remains saved at "
        f"revision {result.session.revision}."
    )
    return "CLOSED"
