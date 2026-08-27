"""Validated state transitions for durable Ground sessions."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Iterable

from memcommit.core.context import Context, Memory

from .records import (
    GROUND_LEGACY_SCHEMA_VERSION,
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GROUND_SCHEMA_VERSION,
    LEGACY_COMPLETION_MARKER,
    METHOD_REFERENCES,
    GroundBrief,
    GroundCaseRole,
    GroundDisposition,
    GroundError,
    GroundFrame,
    GroundFrameRole,
    GroundItem,
    GroundOrigin,
    GroundRuleProvenance,
    GroundSession,
    GroundSourceRef,
    GroundTargetRequirement,
    GroundTargetSpec,
    GroundTargetStatus,
    _CASE_ROLES,
    _DISPOSITIONS,
    _ORIGINS,
    _REVIEW_ACTIONS,
    _RULE_PROVENANCE,
    _TARGET_FRAME_ROLES,
    _integer,
    _sha256_text,
    _string,
    context_frame_digest,
    is_bound_ground_schema,
    validate_ground_contract_name,
    validate_ground_goal,
)


def create_ground_session(
    contract_name: str,
    *,
    goal: str = "",
    completion_criterion: str = LEGACY_COMPLETION_MARKER,
    scope: tuple[str, ...] = (),
) -> GroundSession:
    """Create a validated scaffold without inferring Rules or Memories."""
    goal = validate_ground_goal(goal, empty=True)
    session = GroundSession(
        uid=str(uuid.uuid4()),
        contract_name=validate_ground_contract_name(contract_name),
        goal=goal,
        completion_criterion=completion_criterion,
        scope=scope,
        status="OPEN",
        revision=0,
        items=(),
        references=METHOD_REFERENCES,
        schema_version=GROUND_LEGACY_SCHEMA_VERSION,
    )
    return GroundSession.from_dict(session.to_dict())


def _frame(role: GroundFrameRole, ctx: Context) -> GroundFrame:
    direct_items = tuple(ctx.iter_items())
    return GroundFrame(
        role=role,
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=context_frame_digest(ctx),
        direct_memory_count=sum(isinstance(item, Memory) for item in direct_items),
        direct_item_count=len(direct_items),
    )


def bind_ground_workbench(
    session: GroundSession,
    *,
    description: str,
    raw_context: Context,
    derived_context: Context,
    target_contexts: tuple[Context, ...],
    target_requirements: tuple[GroundTargetSpec, ...],
) -> GroundSession:
    """Upgrade an empty scaffold into an exact, non-mutating workbench."""
    if (
        session.schema_version != GROUND_LEGACY_SCHEMA_VERSION
        or session.status != "OPEN"
        or session.revision != 0
        or session.items
    ):
        raise GroundError(
            "Only an empty schema version 1 grounding session can be bound."
        )
    description = _string(
        description,
        "grounding Task description",
    )
    if not target_contexts or len(target_contexts) != len(target_requirements):
        raise GroundError(
            "Every grounding target requires exactly one target specification."
        )
    target_by_name = {context.name: context for context in target_contexts}
    if len(target_by_name) != len(target_contexts):
        raise GroundError("Grounding target Contexts must be unique.")
    spec_by_name = {spec.context_name: spec for spec in target_requirements}
    if len(spec_by_name) != len(target_requirements) or set(spec_by_name) != set(
        target_by_name
    ):
        raise GroundError(
            "Grounding target specifications do not match target Contexts."
        )
    all_contexts = (raw_context, derived_context, *target_contexts)
    if len({context.uid for context in all_contexts}) != len(all_contexts) or len(
        {context.name for context in all_contexts}
    ) != len(all_contexts):
        raise GroundError("Grounding workbench Contexts must be independent.")

    frames = [
        _frame("RAW_EVIDENCE", raw_context),
        _frame("WORKING_CANDIDATES", derived_context),
    ]
    requirements: list[GroundTargetRequirement] = []
    for context in target_contexts:
        spec = spec_by_name[context.name]
        if spec.role not in _TARGET_FRAME_ROLES:
            raise GroundError("Invalid grounding target role.")
        minimum = _integer(
            spec.minimum_accepted_cases,
            "grounding target minimum",
        )
        if minimum < 1:
            raise GroundError("Invalid grounding target minimum.")
        frames.append(_frame(spec.role, context))
        requirements.append(
            GroundTargetRequirement(
                uid=str(uuid.uuid4()),
                target_context_uid=context.uid,
                description=_string(
                    spec.description,
                    "grounding target description",
                    empty=True,
                ),
                minimum_accepted_cases=minimum,
                blocked_reason=_string(
                    spec.blocked_reason,
                    "grounding target blocked reason",
                    empty=True,
                ),
            )
        )

    bound = replace(
        session,
        schema_version=GROUND_SCHEMA_VERSION,
        brief=GroundBrief(
            content=description,
            provenance="USER_PROVIDED_TASK_DESCRIPTION",
            digest=_sha256_text(description),
        ),
        frames=tuple(frames),
        requirements=tuple(requirements),
        cursor_position=0,
    )
    return GroundSession.from_dict(bound.to_dict())


def _contexts_by_uid(
    contexts: Iterable[Context],
) -> dict[str, Context]:
    result: dict[str, Context] = {}
    for context in contexts:
        if context.uid in result:
            raise GroundError("Duplicate current grounding Context uid.")
        result[context.uid] = context
    return result


def upgrade_ground_to_propositions(session: GroundSession) -> GroundSession:
    """Explicitly migrate one bound v2 Ground to proposition-authoritative v3.

    The migration preserves every durable identity, semantic iteration, link,
    source reference, target, and exact-output projection.  It changes the
    record digest, so all earlier Fit receipts become stale even though no
    semantic revision is invented merely for a storage-shape transition.
    """

    if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
        return GroundSession.from_dict(session.to_dict())
    if session.schema_version != GROUND_SCHEMA_VERSION:
        raise GroundError("Only a bound version-2 Ground can be upgraded.")
    migrated_items = tuple(
        (
            replace(
                item,
                proposition=(
                    f"{item.content} -> {item.expected}"
                    if item.expected
                    else item.content
                ),
            )
            if item.kind == "CASE"
            else item
        )
        for item in session.items
    )
    upgraded = replace(
        session,
        schema_version=GROUND_PROPOSITION_SCHEMA_VERSION,
        items=migrated_items,
    )
    return GroundSession.from_dict(upgraded.to_dict())


def stale_ground_frames(
    session: GroundSession,
    contexts: Iterable[Context],
) -> tuple[str, ...]:
    """Return bound frame names that no longer match their exact Context."""
    if not is_bound_ground_schema(session.schema_version):
        return ()
    current = _contexts_by_uid(contexts)
    stale: set[str] = set()
    for frame in session.frames:
        context = current.get(frame.context_uid)
        if context is None or _frame(frame.role, context) != frame:
            stale.add(frame.context_name)

    frame_name_by_uid = {
        frame.context_uid: frame.context_name for frame in session.frames
    }
    for item in session.items:
        for source_ref in item.source_refs:
            context = current.get(source_ref.context_uid)
            memory = (
                next(
                    (
                        candidate
                        for candidate in context.iter_items()
                        if isinstance(candidate, Memory)
                        and candidate.uid == source_ref.memory_uid
                    ),
                    None,
                )
                if context is not None
                else None
            )
            if (
                memory is None
                or _sha256_text(memory.content) != source_ref.content_digest
                or (
                    session.schema_version == GROUND_SCHEMA_VERSION
                    and item.kind == "CASE"
                    and item.content != memory.content
                )
            ):
                stale.add(
                    frame_name_by_uid.get(
                        source_ref.context_uid,
                        source_ref.context_uid,
                    )
                )
    return tuple(
        frame.context_name for frame in session.frames if frame.context_name in stale
    )


def ground_matches_workbench(
    session: GroundSession,
    contexts: Iterable[Context],
) -> bool:
    """Return whether all bound frames still match their recorded bytes."""
    return is_bound_ground_schema(session.schema_version) and not stale_ground_frames(
        session, contexts
    )


def _find_memory(ctx: Context, selector: str) -> Memory:
    selector = _string(
        selector,
        "grounding candidate selector",
        limit=100,
    )
    memories = [item for item in ctx.iter_items() if isinstance(item, Memory)]
    matches = [memory for memory in memories if memory.uid.startswith(selector)]
    if not matches:
        raise GroundError(f"No bound candidate Memory starts with '{selector}'.")
    if len(matches) > 1:
        raise GroundError(f"Candidate prefix '{selector}' is ambiguous.")
    return matches[0]


def _find_rule(session: GroundSession, selector: str) -> GroundItem:
    selector = _string(selector, "grounding rule selector", limit=100)
    matches = [
        item
        for item in session.items
        if item.kind == "RULE" and item.uid.startswith(selector)
    ]
    if not matches:
        raise GroundError(f"No grounding rule starts with '{selector}'.")
    if len(matches) > 1:
        raise GroundError(f"Grounding rule prefix '{selector}' is ambiguous.")
    return matches[0]


def _proposal_contexts(
    session: GroundSession,
    current_contexts: Iterable[Context],
) -> tuple[Context, ...]:
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one."
        )
    if session.status != "OPEN":
        raise GroundError("Grounding workbench is not open.")
    return contexts


def propose_ground_rule(
    session: GroundSession,
    *,
    rule: str,
    rationale: str,
    current_contexts: Iterable[Context],
    rule_provenance: GroundRuleProvenance = "DISTILLED",
    target_context_names: tuple[str, ...] = (),
) -> GroundSession:
    """Propose one reusable Rule without manufacturing a Ground Memory."""
    _proposal_contexts(session, current_contexts)
    rule = _string(rule, "grounding proposed rule")
    if rule_provenance not in _RULE_PROVENANCE or rule_provenance == "JOINTLY_REVISED":
        raise GroundError(
            "A new rule must be USER_STATED or DISTILLED; legacy "
            "DISTILLED_FROM_GOAL and INDUCED_FROM_CASES remain readable; "
            "JOINTLY_REVISED is created by review."
        )
    # A directly stated Rule may be complete in the person's own wording.
    # Derived Rules still need an explicit inference rationale so provenance
    # cannot silently turn a user statement into model-authored reasoning.
    rationale = _string(
        rationale,
        "grounding proposal rationale",
        empty=rule_provenance == "USER_STATED",
    )
    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if not target_context_names:
        target_context_names = tuple(
            frame.context_name
            for frame in session.frames
            if frame.role == "PUBLICATION_TARGET"
        )
    if (
        not target_context_names
        or len(set(target_context_names)) != len(target_context_names)
        or any(name not in target_frame_by_name for name in target_context_names)
    ):
        raise GroundError("Grounding Rule names an invalid target Context.")
    iteration = session.revision + 1
    proposed_rule = GroundItem(
        uid=str(uuid.uuid4()),
        kind="RULE",
        content=rule,
        expected="",
        rationale=rationale,
        status="PROPOSED",
        origin=("USER" if rule_provenance == "USER_STATED" else "AGENT"),
        iteration=iteration,
        related_uids=(),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid for name in target_context_names
        ),
        rule_provenance=rule_provenance,
    )
    result = replace(
        session,
        revision=iteration,
        items=(*session.items, proposed_rule),
    )
    return GroundSession.from_dict(result.to_dict())


def propose_ground_case(
    session: GroundSession,
    *,
    rule_selector: str,
    case: str,
    source_context_uid: str,
    source_memory_uid: str,
    target_context_names: tuple[str, ...],
    expected: str,
    rationale: str,
    current_contexts: Iterable[Context],
    case_role: GroundCaseRole = "FIT",
    disposition: GroundDisposition = "INCLUDE",
) -> GroundSession:
    """Attach one traceable fit, boundary, or contrast Memory to a Rule."""
    contexts = _proposal_contexts(session, current_contexts)
    rule = _find_rule(session, rule_selector)
    if rule.status in {"REJECTED", "DEFERRED"}:
        raise GroundError(
            "A Ground Memory cannot attach to a rejected or deferred Rule."
        )
    case = _string(case, "proposed Ground Memory")
    rationale = _string(rationale, "grounding proposal rationale")
    expected = _string(
        expected,
        "grounding proposed expected result",
        empty=disposition != "INCLUDE",
    )
    if case_role not in _CASE_ROLES or disposition not in _DISPOSITIONS:
        raise GroundError("Invalid Ground Memory classification.")

    source_frame = next(
        (
            frame
            for frame in session.frames
            if frame.context_uid == source_context_uid
            and frame.role == "WORKING_CANDIDATES"
        ),
        None,
    )
    contexts_by_uid = _contexts_by_uid(contexts)
    if source_frame is None or source_context_uid not in contexts_by_uid:
        raise GroundError(
            "Ground Memories must use the bound working-candidate Context."
        )
    memory = _find_memory(
        contexts_by_uid[source_context_uid],
        source_memory_uid,
    )
    if case != memory.content:
        raise GroundError(
            "Ground Memory content must exactly match its bound source "
            "Context Memory; put rewritten output in expected."
        )

    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if (
        not target_context_names
        or len(set(target_context_names)) != len(target_context_names)
        or any(name not in target_frame_by_name for name in target_context_names)
    ):
        raise GroundError("Grounding proposal names an invalid target Context.")

    iteration = session.revision + 1
    case_uid = str(uuid.uuid4())
    proposed_case = GroundItem(
        uid=case_uid,
        kind="CASE",
        content=case,
        expected=expected,
        rationale=rationale,
        status="PROPOSED",
        origin="AGENT",
        iteration=iteration,
        related_uids=(rule.uid,),
        source_refs=(
            GroundSourceRef(
                context_uid=source_context_uid,
                memory_uid=memory.uid,
                content_digest=_sha256_text(memory.content),
            ),
        ),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid for name in target_context_names
        ),
        case_role=case_role,
        disposition=disposition,
    )
    linked_rule = replace(
        rule,
        related_uids=(*rule.related_uids, case_uid),
    )
    items = tuple(
        linked_rule if item.uid == rule.uid else item for item in session.items
    )
    result = replace(
        session,
        revision=iteration,
        items=(*items, proposed_case),
    )
    return GroundSession.from_dict(result.to_dict())


def propose_ground_example(
    session: GroundSession,
    *,
    proposition: str,
    rationale: str,
    current_contexts: Iterable[Context],
    rule_selectors: tuple[str, ...] = (),
    source_context_uid: str | None = None,
    source_memory_uid: str | None = None,
    target_context_names: tuple[str, ...] = (),
    input_text: str = "",
    expected_output: str = "",
    case_role: GroundCaseRole = "FIT",
    disposition: GroundDisposition = "INCLUDE",
    origin: GroundOrigin = "USER",
) -> GroundSession:
    """Propose one native concrete proposition in a version-3 Ground.

    Evidence, materialization targets, exact-output projection, and Rule links
    are independent optional metadata.  A pre-Rule observation therefore
    remains durable without fabricating a Rule or source Memory.
    """

    contexts = _proposal_contexts(session, current_contexts)
    if session.schema_version != GROUND_PROPOSITION_SCHEMA_VERSION:
        raise GroundError(
            "Native Examples require an explicit proposition-schema upgrade."
        )
    proposition = _string(proposition, "Ground Example proposition")
    rationale = _string(rationale, "Ground Example rationale", empty=True)
    input_text = _string(
        input_text,
        "Ground Example exact input",
        empty=True,
    )
    expected_output = _string(
        expected_output,
        "Ground Example expected output",
        empty=True,
    )
    if bool(input_text) != bool(expected_output):
        raise GroundError(
            "An exact-output Example requires both input and expected output."
        )
    if (
        case_role not in _CASE_ROLES
        or disposition not in _DISPOSITIONS
        or origin not in _ORIGINS
    ):
        raise GroundError("Invalid native Ground Example classification.")
    if len(set(rule_selectors)) != len(rule_selectors):
        raise GroundError("A Ground Example Rule was supplied more than once.")
    rules = tuple(_find_rule(session, selector) for selector in rule_selectors)
    if len({rule.uid for rule in rules}) != len(rules):
        raise GroundError("Ground Example Rule selectors are not unique.")
    if any(rule.status in {"REJECTED", "DEFERRED"} for rule in rules):
        raise GroundError("A Ground Example cannot link an inactive Rule.")

    if (source_context_uid is None) != (source_memory_uid is None):
        raise GroundError(
            "Ground Example source Context and Memory must be supplied together."
        )
    source_refs: tuple[GroundSourceRef, ...] = ()
    if source_context_uid is not None and source_memory_uid is not None:
        source_frame = next(
            (
                frame
                for frame in session.frames
                if frame.context_uid == source_context_uid
                and frame.role == "WORKING_CANDIDATES"
            ),
            None,
        )
        contexts_by_uid = _contexts_by_uid(contexts)
        if source_frame is None or source_context_uid not in contexts_by_uid:
            raise GroundError(
                "Ground Example evidence must use the bound candidate Context."
            )
        memory = _find_memory(
            contexts_by_uid[source_context_uid],
            source_memory_uid,
        )
        source_refs = (
            GroundSourceRef(
                context_uid=source_context_uid,
                memory_uid=memory.uid,
                content_digest=_sha256_text(memory.content),
            ),
        )

    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if len(set(target_context_names)) != len(target_context_names) or any(
        name not in target_frame_by_name for name in target_context_names
    ):
        raise GroundError("Ground Example names an invalid target Context.")

    iteration = session.revision + 1
    example_uid = str(uuid.uuid4())
    example = GroundItem(
        uid=example_uid,
        kind="CASE",
        content=input_text or proposition,
        expected=expected_output,
        proposition=proposition,
        rationale=rationale,
        status="PROPOSED",
        origin=origin,
        iteration=iteration,
        related_uids=tuple(rule.uid for rule in rules),
        source_refs=source_refs,
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid for name in target_context_names
        ),
        case_role=case_role,
        disposition=disposition,
    )
    rule_uids = {rule.uid for rule in rules}
    linked_items = tuple(
        replace(item, related_uids=(*item.related_uids, example_uid))
        if item.uid in rule_uids
        else item
        for item in session.items
    )
    result = replace(
        session,
        revision=iteration,
        items=(*linked_items, example),
    )
    return GroundSession.from_dict(result.to_dict())


def select_ground_candidate(
    session: GroundSession,
    position: int,
    *,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Move the durable workbench cursor without changing semantic revision."""
    if not ground_matches_workbench(session, current_contexts):
        raise GroundError("Grounding workbench is stale.")
    if isinstance(position, bool) or not isinstance(position, int):
        raise GroundError("Grounding candidate position must be an integer.")
    candidate_frame = next(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    if position < 0 or position >= candidate_frame.direct_memory_count:
        raise GroundError("Grounding candidate position is out of range.")
    selected = replace(session, cursor_position=position)
    return GroundSession.from_dict(selected.to_dict())


def propose_ground_round(
    session: GroundSession,
    *,
    rule: str,
    case: str,
    source_context_uid: str,
    source_memory_uid: str,
    target_context_names: tuple[str, ...],
    expected: str,
    rationale: str,
    current_contexts: Iterable[Context],
    case_role: GroundCaseRole = "FIT",
    disposition: GroundDisposition = "INCLUDE",
    rule_provenance: GroundRuleProvenance = "DISTILLED",
) -> GroundSession:
    """Record one related Rule/Memory proposal as a single revision."""
    contexts = _proposal_contexts(session, current_contexts)
    rule = _string(rule, "grounding proposed rule")
    case = _string(case, "proposed Ground Memory")
    rationale = _string(rationale, "grounding proposal rationale")
    expected = _string(
        expected,
        "grounding proposed expected result",
        empty=disposition != "INCLUDE",
    )
    if (
        case_role not in _CASE_ROLES
        or disposition not in _DISPOSITIONS
        or rule_provenance not in _RULE_PROVENANCE
        or rule_provenance == "JOINTLY_REVISED"
    ):
        raise GroundError("Invalid Ground Memory classification.")

    source_frame = next(
        (
            frame
            for frame in session.frames
            if frame.context_uid == source_context_uid
            and frame.role == "WORKING_CANDIDATES"
        ),
        None,
    )
    contexts_by_uid = _contexts_by_uid(contexts)
    if source_frame is None or source_context_uid not in contexts_by_uid:
        raise GroundError(
            "Ground Memories must use the bound working-candidate Context."
        )
    memory = _find_memory(
        contexts_by_uid[source_context_uid],
        source_memory_uid,
    )
    if case != memory.content:
        raise GroundError(
            "Ground Memory content must exactly match its bound source "
            "Context Memory; put rewritten output in expected."
        )

    target_frame_by_name = {
        frame.context_name: frame
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    if (
        not target_context_names
        or len(set(target_context_names)) != len(target_context_names)
        or any(name not in target_frame_by_name for name in target_context_names)
    ):
        raise GroundError("Grounding proposal names an invalid target Context.")

    iteration = session.revision + 1
    rule_uid = str(uuid.uuid4())
    case_uid = str(uuid.uuid4())
    proposed_rule = GroundItem(
        uid=rule_uid,
        kind="RULE",
        content=rule,
        expected="",
        rationale=rationale,
        status="PROPOSED",
        origin=("USER" if rule_provenance == "USER_STATED" else "AGENT"),
        iteration=iteration,
        related_uids=(case_uid,),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid for name in target_context_names
        ),
        rule_provenance=rule_provenance,
    )
    proposed_case = GroundItem(
        uid=case_uid,
        kind="CASE",
        content=case,
        expected=expected,
        rationale=rationale,
        status="PROPOSED",
        origin="AGENT",
        iteration=iteration,
        related_uids=(rule_uid,),
        source_refs=(
            GroundSourceRef(
                context_uid=source_context_uid,
                memory_uid=memory.uid,
                content_digest=_sha256_text(memory.content),
            ),
        ),
        target_context_uids=tuple(
            target_frame_by_name[name].context_uid for name in target_context_names
        ),
        case_role=case_role,
        disposition=disposition,
    )
    result = replace(
        session,
        revision=iteration,
        items=(*session.items, proposed_rule, proposed_case),
    )
    return GroundSession.from_dict(result.to_dict())


def review_ground_item(
    session: GroundSession,
    item_uid: str,
    *,
    action: str,
    response: str = "",
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Accept, refine, defer, or reject one proposal in one saved revision."""
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before deciding."
        )
    action = _string(action, "grounding review action", limit=20).upper()
    if action not in _REVIEW_ACTIONS:
        raise GroundError("Invalid grounding review action.")
    item_uid = _string(item_uid, "grounding decision selector", limit=100)
    candidates = [item for item in session.items if item.uid.startswith(item_uid)]
    if len(candidates) != 1:
        raise GroundError("Grounding decision target is missing or ambiguous.")
    target = candidates[0]
    if target.kind not in {"RULE", "CASE"} or (
        target.status != "PROPOSED"
        and not (action == "REFINE" and target.status == "ACCEPTED")
    ):
        raise GroundError(
            "Only a proposed Rule/Ground Memory, or an accepted item being "
            "reopened with REFINE, can be reviewed."
        )
    if action == "REFINE" and not response.strip():
        raise GroundError("REFINE requires replacement text.")

    iteration = session.revision + 1
    replacement = target
    if action == "ACCEPT":
        replacement = replace(
            target,
            status="ACCEPTED",
            origin="JOINT",
            iteration=iteration,
        )
    elif action == "DEFER":
        replacement = replace(target, status="DEFERRED", origin="JOINT")
    elif action == "REJECT":
        replacement = replace(target, status="REJECTED", origin="JOINT")
    elif target.kind == "RULE":
        replacement = replace(
            target,
            content=_string(response, "refined grounding rule"),
            status="PROPOSED",
            origin="JOINT",
            iteration=iteration,
            rule_provenance="JOINTLY_REVISED",
        )
    elif session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
        replacement = replace(
            target,
            proposition=_string(response, "refined Ground Example proposition"),
            status="PROPOSED",
            origin="JOINT",
            iteration=iteration,
        )
    else:
        replacement = replace(
            target,
            expected=_string(response, "refined Ground Memory output"),
            status="PROPOSED",
            origin="JOINT",
            iteration=iteration,
        )

    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content=f"{action} {target.kind}",
        expected=response,
        rationale=(
            response
            if action != "REFINE"
            else (
                "The user refined and reopened the judgment. Previous value: "
                + (
                    target.content
                    if target.kind == "RULE"
                    else (
                        target.proposition
                        if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                        else target.expected
                    )
                )
            )
        ),
        status="RESOLVED",
        origin="USER",
        iteration=iteration,
        related_uids=(target.uid,),
    )
    items = tuple(
        replacement if item.uid == target.uid else item for item in session.items
    )
    reviewed = replace(
        session,
        revision=iteration,
        items=(*items, decision),
    )
    return GroundSession.from_dict(reviewed.to_dict())


def set_ground_example_use(
    session: GroundSession,
    item_uid: str,
    *,
    use: str,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Set whether one active Example participates in semantic evaluation.

    USE is a durable semantic-input decision, not a presentation preference.
    Keep it on the same revisioned/CAS-protected Ground boundary as review so
    Fit and Ground Distill can freeze one unambiguous Example set.
    """

    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before changing Example USE."
        )
    use = _string(use, "Ground Example USE", limit=20).upper()
    if use not in {"INCLUDE", "EXCLUDE"}:
        raise GroundError("Ground Example USE must be INCLUDE or EXCLUDE.")
    selector = _string(item_uid, "Ground Example selector", limit=100)
    candidates = [
        item
        for item in session.items
        if item.kind == "CASE" and item.uid.startswith(selector)
    ]
    if len(candidates) != 1:
        raise GroundError("Ground Example USE target is missing or ambiguous.")
    target = candidates[0]
    if target.status not in {"PROPOSED", "ACCEPTED"}:
        raise GroundError("Only a PROPOSED or ACCEPTED Ground Example can change USE.")
    if target.disposition == use:
        raise GroundError("Ground Example USE is already set to that value.")

    iteration = session.revision + 1
    replacement = replace(
        target,
        disposition=use,
        origin="JOINT",
        iteration=iteration,
    )
    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content=f"SET EXAMPLE USE {use}",
        expected=use,
        rationale=(
            "The user explicitly changed whether this Example participates "
            "in Fit and Ground Distill."
        ),
        status="RESOLVED",
        origin="USER",
        iteration=iteration,
        related_uids=(target.uid,),
    )
    result = replace(
        session,
        revision=iteration,
        items=tuple(
            replacement if item.uid == target.uid else item for item in session.items
        )
        + (decision,),
    )
    return GroundSession.from_dict(result.to_dict())


def resolve_ground_requirement(
    session: GroundSession,
    requirement_selector: str,
) -> GroundTargetRequirement:
    """Resolve one target requirement by exact Context name or UID prefix."""
    requirement_selector = _string(
        requirement_selector,
        "grounding requirement selector",
        limit=500,
    )
    frame_name_by_uid = {
        frame.context_uid: frame.context_name
        for frame in session.frames
        if frame.role in _TARGET_FRAME_ROLES
    }
    exact_matches = [
        requirement
        for requirement in session.requirements
        if requirement.target_context_uid in frame_name_by_uid
        and frame_name_by_uid[requirement.target_context_uid] == requirement_selector
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise GroundError("Grounding requirement target is missing or ambiguous.")
    prefix_matches = [
        requirement
        for requirement in session.requirements
        if requirement.target_context_uid in frame_name_by_uid
        and requirement.uid.startswith(requirement_selector)
    ]
    if len(prefix_matches) != 1:
        raise GroundError("Grounding requirement target is missing or ambiguous.")
    return prefix_matches[0]


def revise_ground_requirement(
    session: GroundSession,
    requirement_selector: str,
    *,
    description: str | None = None,
    minimum_accepted_cases: int | None = None,
    blocked_reason: str | None = None,
    reason: str,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Revise the negotiable Goal layer and record why it changed.

    The copied task brief and evidence frames stay fixed.  Requirements are
    working hypotheses: awkward lower cases may reveal that a category,
    minimum, or blocking assumption should change.  Such changes are explicit
    revisions so accepted cases can be regression-checked against them later.
    """
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before revising it."
        )
    current = resolve_ground_requirement(session, requirement_selector)
    if (
        description is None
        and minimum_accepted_cases is None
        and blocked_reason is None
    ):
        raise GroundError("A requirement revision must change a field.")

    revised_description = (
        current.description
        if description is None
        else _string(description, "revised grounding target description")
    )
    revised_minimum = (
        current.minimum_accepted_cases
        if minimum_accepted_cases is None
        else _integer(
            minimum_accepted_cases,
            "revised grounding target minimum",
        )
    )
    if revised_minimum < 1:
        raise GroundError("Invalid revised grounding target minimum.")
    revised_blocked_reason = (
        current.blocked_reason
        if blocked_reason is None
        else _string(
            blocked_reason,
            "revised grounding blocked reason",
            empty=True,
        )
    )
    revised = replace(
        current,
        description=revised_description,
        minimum_accepted_cases=revised_minimum,
        blocked_reason=revised_blocked_reason,
    )
    if revised == current:
        raise GroundError("Grounding requirement revision is a no-op.")

    iteration = session.revision + 1
    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content="REFINE TARGET REQUIREMENT",
        expected=(
            f"{revised.description} | minimum="
            f"{revised.minimum_accepted_cases} | blocked="
            f"{revised.blocked_reason or 'no'}"
        ),
        rationale=_string(reason, "grounding requirement revision reason"),
        status="RESOLVED",
        origin="JOINT",
        iteration=iteration,
        related_uids=(current.uid,),
    )
    result = replace(
        session,
        revision=iteration,
        requirements=tuple(
            revised if requirement.uid == current.uid else requirement
            for requirement in session.requirements
        ),
        items=(*session.items, decision),
    )
    return GroundSession.from_dict(result.to_dict())


def revise_ground_goal(
    session: GroundSession,
    goal: str,
    *,
    reason: str,
    current_contexts: Iterable[Context],
) -> GroundSession:
    """Revise the top-level working goal while retaining the source brief."""
    contexts = tuple(current_contexts)
    if not ground_matches_workbench(session, contexts):
        raise GroundError(
            "Grounding workbench is stale. Create a new named Ground, or "
            "explicitly replace and rebind this one before revising its goal."
        )
    goal = validate_ground_goal(goal, label="revised grounding goal")
    if goal == session.goal:
        raise GroundError("Grounding goal revision is a no-op.")
    iteration = session.revision + 1
    decision = GroundItem(
        uid=str(uuid.uuid4()),
        kind="DECISION",
        content="REFINE GOAL",
        expected=goal,
        rationale=_string(reason, "grounding goal revision reason"),
        status="RESOLVED",
        origin="JOINT",
        iteration=iteration,
        related_uids=(),
    )
    result = replace(
        session,
        goal=goal,
        revision=iteration,
        items=(*session.items, decision),
    )
    return GroundSession.from_dict(result.to_dict())


def accepted_ground_case_count(
    session: GroundSession,
    target_context_uid: str,
) -> int:
    """Count accepted INCLUDE Ground Memories backed by an accepted Rule."""
    accepted_rule_uids = {
        item.uid
        for item in session.items
        if item.kind == "RULE" and item.status == "ACCEPTED"
    }
    evidence = {
        (
            item.source_refs[0].context_uid,
            item.source_refs[0].memory_uid,
        )
        for item in session.items
        if item.kind == "CASE"
        and item.status == "ACCEPTED"
        and item.disposition == "INCLUDE"
        and target_context_uid in item.target_context_uids
        and any(uid in accepted_rule_uids for uid in item.related_uids)
    }
    return len(evidence)


def target_requirement_status(
    session: GroundSession,
    requirement: GroundTargetRequirement,
) -> GroundTargetStatus:
    """Derive one target state from accepted reviewed Ground Memories."""
    if requirement.blocked_reason:
        return "BLOCKED"
    accepted = accepted_ground_case_count(
        session,
        requirement.target_context_uid,
    )
    if accepted >= requirement.minimum_accepted_cases:
        return "COVERED"
    if accepted:
        return "PARTIAL"
    return "EMPTY"
