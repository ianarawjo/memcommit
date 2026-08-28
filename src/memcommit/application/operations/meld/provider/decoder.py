"""Strict provider-response decoding into typed Meld assessments."""

from __future__ import annotations

import json
import uuid

from memcommit.application.operations.meld.model import (
    MELD_TEXT_LIMIT,
    MeldAssessment,
    MeldError,
    MeldIssue,
    MeldOption,
    MeldProposal,
    MeldRelation,
    MeldSession,
)
from memcommit.application.capabilities.semantic_execution import (
    CoverageError,
    decode_exact_source_assignments,
)

from .contract import (
    MELD_KEY_LIMIT,
    MELD_OPTION_LIMIT,
    MELD_RESPONSE_CHAR_LIMIT,
    MeldProviderError,
    _DISPOSITIONS,
    _PRIORITIES,
    _RELATIONS,
    _STATUSES,
)
from .projection import _ProviderView


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise MeldProviderError(f"Codex meld returned an invalid {label}.")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise MeldProviderError(f"Codex meld returned an invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = MELD_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise MeldProviderError(f"Codex meld returned an invalid {label}.")
    return value


def _key(value: object, label: str) -> str:
    return _string(value, label, limit=MELD_KEY_LIMIT)


def _literal(value: object, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise MeldProviderError(f"Codex meld returned an invalid {label}.")
    return value


def _keys(
    value: object,
    label: str,
    *,
    empty: bool = False,
) -> tuple[str, ...]:
    values = _array(value, label)
    if not empty and not values:
        raise MeldProviderError(f"Codex meld returned an invalid {label}.")
    result = tuple(_key(item, label) for item in values)
    if len(result) != len(set(result)):
        raise MeldProviderError(f"Codex meld returned duplicate {label}.")
    return result


def _mapped(
    values: tuple[str, ...],
    mapping: dict[str, str],
    label: str,
) -> tuple[str, ...]:
    if any(value not in mapping for value in values):
        raise MeldProviderError(f"Codex meld returned an unknown {label}.")
    return tuple(mapping[value] for value in values)

def _stable_uid(
    session_uid: str,
    turn_uid: str,
    kind: str,
    key: str,
) -> str:
    return str(
        uuid.uuid5(
            uuid.UUID(session_uid),
            f"{turn_uid}\x1f{kind}\x1f{key}",
        )
    )


def _parse_assessment(
    raw: object,
    *,
    session: MeldSession,
    view: _ProviderView,
) -> MeldAssessment:
    if (
        not isinstance(raw, str)
        or not raw.strip()
        or len(raw) > MELD_RESPONSE_CHAR_LIMIT
    ):
        raise MeldProviderError("Codex meld returned invalid structured output.")
    try:
        value = json.loads(raw, object_pairs_hook=_strict_json_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise MeldProviderError(
            "Codex meld returned invalid structured output."
        ) from error
    legacy_relation_shape = isinstance(value, dict) and "relations" in value
    source_assignment_shape = (
        isinstance(value, dict) and "source_assignments" in value
    )
    if legacy_relation_shape and source_assignment_shape:
        raise MeldProviderError("Codex meld returned mixed relation formats.")
    response_keys = {
        "overview",
        "issues",
        "results",
        "ready_to_apply",
    }
    response_keys.update(
        {"relations"}
        if legacy_relation_shape
        else {"paired_relations", "distinct_relations"}
    )
    if source_assignment_shape:
        response_keys.add("source_assignments")
    data = _exact_dict(
        value,
        response_keys,
        "meld response",
    )
    if not isinstance(data["ready_to_apply"], bool):
        raise MeldProviderError("Codex meld returned invalid readiness.")
    current = session.current_turn
    assert current is not None

    if legacy_relation_shape:
        legacy_records = _array(data["relations"], "meld relations")
        raw_paired_relations = [
            item
            for item in legacy_records
            if isinstance(item, dict) and item.get("kind") != "DISTINCT"
        ]
        raw_distinct_relations = []
        legacy_distinct_records = [
            item
            for item in legacy_records
            if isinstance(item, dict) and item.get("kind") == "DISTINCT"
        ]
    else:
        raw_paired_relations = _array(
            data["paired_relations"],
            "paired meld relations",
        )
        raw_distinct_relations = _array(
            data["distinct_relations"],
            "distinct meld relations",
        )
        legacy_distinct_records = []
    if not raw_paired_relations and not raw_distinct_relations:
        raise MeldProviderError("Codex meld returned an invalid number of relations.")
    relation_records: list[tuple[str, dict[str, object]]] = []
    for item in raw_paired_relations:
        relation_fields = {
            "relation_key",
            "kind",
            "status",
            "summary",
            "reason",
        }
        if not source_assignment_shape:
            relation_fields.update({"left_memory_ids", "right_memory_ids"})
        record = _exact_dict(
            item,
            relation_fields,
            "meld relation",
        )
        if record["kind"] == "DISTINCT":
            raise MeldProviderError(
                "Codex meld returned DISTINCT in paired_relations."
            )
        relation_records.append(
            (_key(record["relation_key"], "meld relation key"), record)
        )
    for item in legacy_distinct_records:
        record = _exact_dict(
            item,
            {
                "relation_key",
                "left_memory_ids",
                "right_memory_ids",
                "kind",
                "status",
                "summary",
                "reason",
            },
            "meld relation",
        )
        relation_records.append(
            (_key(record["relation_key"], "meld relation key"), record)
        )
    for item in raw_distinct_relations:
        distinct_fields = {
            "relation_key",
            "side",
            "kind",
            "status",
            "summary",
            "reason",
        }
        if not source_assignment_shape:
            distinct_fields.add("memory_ids")
        record = _exact_dict(
            item,
            distinct_fields,
            "distinct meld relation",
        )
        side = _literal(
            record["side"],
            {"LEFT", "RIGHT"},
            "distinct meld relation side",
        )
        if record["kind"] != "DISTINCT":
            raise MeldProviderError(
                "Codex meld returned a non-DISTINCT one-sided relation."
            )
        if source_assignment_shape:
            normalized = record
        else:
            memory_ids = list(
                _keys(record["memory_ids"], "distinct Memory ids")
            )
            normalized = {
                "relation_key": record["relation_key"],
                "left_memory_ids": memory_ids if side == "LEFT" else [],
                "right_memory_ids": memory_ids if side == "RIGHT" else [],
                "kind": "DISTINCT",
                "status": record["status"],
                "summary": record["summary"],
                "reason": record["reason"],
            }
        relation_records.append(
            (
                _key(record["relation_key"], "meld relation key"),
                normalized,
            )
        )
    relation_keys = [key for key, _ in relation_records]
    if not relation_records or len(relation_keys) != len(set(relation_keys)):
        raise MeldProviderError("Codex meld returned duplicate or empty relation keys.")
    if source_assignment_shape:
        try:
            assignments = decode_exact_source_assignments(
                data["source_assignments"],
                tuple(view.memory_by_id),
            )
        except CoverageError as error:
            raise MeldProviderError(
                "Codex meld source assignments must cover every source Memory "
                "exactly once."
            ) from error
        assignment_by_source: dict[str, str] = {}
        relation_key_set = set(relation_keys)
        for source_id, raw_relation_key in assignments:
            relation_key = _key(
                raw_relation_key,
                "meld source assignment relation key",
            )
            if relation_key not in relation_key_set:
                raise MeldProviderError(
                    "Codex meld assigned a source Memory to an unknown relation."
                )
            assignment_by_source[source_id] = relation_key
        left_frame_uid = session.frames[0].uid
        assigned_members = {
            key: {"LEFT": [], "RIGHT": []} for key in relation_keys
        }
        # Model row order is presentation noise; canonical Source order keeps
        # durable relation members stable across equivalent completions.
        for source_id, member in view.memory_by_id.items():
            side = "LEFT" if member.frame_uid == left_frame_uid else "RIGHT"
            assigned_members[assignment_by_source[source_id]][side].append(
                source_id
            )
        normalized_records: list[tuple[str, dict[str, object]]] = []
        for key, record in relation_records:
            left_ids = assigned_members[key]["LEFT"]
            right_ids = assigned_members[key]["RIGHT"]
            if record["kind"] == "DISTINCT":
                declared_side = _literal(
                    record["side"],
                    {"LEFT", "RIGHT"},
                    "distinct meld relation side",
                )
                actual_side = (
                    "LEFT"
                    if left_ids and not right_ids
                    else "RIGHT"
                    if right_ids and not left_ids
                    else None
                )
                if actual_side != declared_side:
                    raise MeldProviderError(
                        "Codex meld assigned a DISTINCT relation to invalid "
                        "source sides."
                    )
            normalized_records.append(
                (
                    key,
                    {
                        "relation_key": record["relation_key"],
                        "left_memory_ids": left_ids,
                        "right_memory_ids": right_ids,
                        "kind": record["kind"],
                        "status": record["status"],
                        "summary": record["summary"],
                        "reason": record["reason"],
                    },
                )
            )
        relation_records = normalized_records
    else:
        # A legacy follow-up may return only relations it changed. Carry forward
        # an omitted prior relation only when none of its members appears in the
        # response. New source-indexed responses are always cumulative instead.
        returned_memory_ids: set[str] = set()
        for _key_value, record in relation_records:
            returned_memory_ids.update(
                _keys(record["left_memory_ids"], "left Memory ids", empty=True)
            )
            returned_memory_ids.update(
                _keys(record["right_memory_ids"], "right Memory ids", empty=True)
            )
        returned_relation_keys = set(relation_keys)
        for key, record in view.prior_relation_records.items():
            if key in returned_relation_keys:
                continue
            prior_member_ids = {
                *_keys(record["left_memory_ids"], "left Memory ids", empty=True),
                *_keys(record["right_memory_ids"], "right Memory ids", empty=True),
            }
            if prior_member_ids.isdisjoint(returned_memory_ids):
                relation_records.append((key, record))
                relation_keys.append(key)
    relation_uid_by_key = {
        key: (
            view.prior_relation_by_id[key]
            if key in view.prior_relation_by_id
            else _stable_uid(
                session.uid,
                current.uid,
                "relation",
                key,
            )
        )
        for key in relation_keys
    }
    relations: list[MeldRelation] = []
    covered_memory_ids: list[str] = []
    for key, record in relation_records:
        left_ids = _keys(
            record["left_memory_ids"],
            "left Memory ids",
            empty=True,
        )
        right_ids = _keys(
            record["right_memory_ids"],
            "right Memory ids",
            empty=True,
        )
        memory_ids = (*left_ids, *right_ids)
        kind = _literal(
            record["kind"],
            _RELATIONS,
            "meld relation kind",
        )
        if not memory_ids or any(
            memory_id not in view.memory_by_id for memory_id in memory_ids
        ):
            raise MeldProviderError(
                "Codex meld returned an unknown or empty relation member."
            )
        left_frame_uid = session.frames[0].uid
        right_frame_uid = session.frames[1].uid
        if any(
            view.memory_by_id[memory_id].frame_uid != left_frame_uid
            for memory_id in left_ids
        ) or any(
            view.memory_by_id[memory_id].frame_uid != right_frame_uid
            for memory_id in right_ids
        ):
            raise MeldProviderError(
                "Codex meld placed a source Memory on the wrong side."
            )
        if kind == "DISTINCT":
            if bool(left_ids) == bool(right_ids):
                raise MeldProviderError(
                    "Codex meld returned a DISTINCT relation with invalid source sides."
                )
        elif not left_ids or not right_ids:
            raise MeldProviderError(
                "Codex meld returned an invalid paired relation "
                f"'{key}' ({kind}; left={len(left_ids)}, right={len(right_ids)})."
            )
        covered_memory_ids.extend(memory_ids)
        relations.append(
            MeldRelation.from_dict(
                {
                    "uid": relation_uid_by_key[key],
                    "kind": kind,
                    "status": _literal(
                        record["status"],
                        _STATUSES,
                        "meld relation status",
                    ),
                    "members": [
                        view.memory_by_id[memory_id].to_dict()
                        for memory_id in memory_ids
                    ],
                    "summary": _string(
                        record["summary"],
                        "meld relation summary",
                    ),
                    "reason": _string(
                        record["reason"],
                        "meld relation reason",
                    ),
                }
            )
        )
    if set(covered_memory_ids) != set(view.memory_by_id) or len(
        covered_memory_ids
    ) != len(view.memory_by_id):
        raise MeldProviderError(
            "Codex meld must cover every source Memory exactly once."
        )

    raw_issues = _array(data["issues"], "meld issues")
    issue_records: list[tuple[str, dict[str, object]]] = []
    for item in raw_issues:
        record = _exact_dict(
            item,
            {
                "issue_key",
                "relation_keys",
                "priority",
                "title",
                "question",
                "why_it_matters",
                "options",
            },
            "meld issue",
        )
        issue_records.append((_key(record["issue_key"], "meld issue key"), record))
    issue_keys = [key for key, _ in issue_records]
    if len(issue_keys) != len(set(issue_keys)):
        raise MeldProviderError("Codex meld returned duplicate issue keys.")
    issue_uid_by_key = {
        key: (
            view.prior_issue_by_id[key]
            if key in view.prior_issue_by_id
            else _stable_uid(session.uid, current.uid, "issue", key)
        )
        for key in issue_keys
    }
    issues: list[MeldIssue] = []
    for key, record in issue_records:
        related_keys = _keys(
            record["relation_keys"],
            "meld issue relation keys",
        )
        relation_uids = _mapped(
            related_keys,
            relation_uid_by_key,
            "meld issue relation key",
        )
        raw_options = _array(record["options"], "meld issue options")
        if len(raw_options) > MELD_OPTION_LIMIT:
            raise MeldProviderError(
                "Codex meld returned too many options for one issue."
            )
        options: list[MeldOption] = []
        for index, item in enumerate(
            raw_options,
            start=1,
        ):
            option = _exact_dict(
                item,
                {"label", "text"},
                "meld issue option",
            )
            options.append(
                MeldOption.from_dict(
                    {
                        "uid": str(
                            uuid.uuid5(
                                uuid.UUID(issue_uid_by_key[key]),
                                f"option:{index}",
                            )
                        ),
                        "label": _string(
                            option["label"],
                            "meld option label",
                        ),
                        "text": _string(
                            option["text"],
                            "meld option text",
                        ),
                    }
                )
            )
        issues.append(
            MeldIssue.from_dict(
                {
                    "uid": issue_uid_by_key[key],
                    "relation_uids": list(relation_uids),
                    "priority": _literal(
                        record["priority"],
                        _PRIORITIES,
                        "meld issue priority",
                    ),
                    "title": _string(
                        record["title"],
                        "meld issue title",
                    ),
                    "question": _string(
                        record["question"],
                        "meld issue question",
                    ),
                    "why_it_matters": _string(
                        record["why_it_matters"],
                        "meld issue consequence",
                    ),
                    "options": [option.to_dict() for option in options],
                }
            )
        )

    raw_results = _array(data["results"], "meld results")
    multi_target = len(view.target_context_by_id) > 1
    result_records: list[tuple[str, dict[str, object]]] = []
    for item in raw_results:
        result_keys = {
            "result_key",
            "disposition",
            "content",
            "reason",
            "relation_keys",
            "source_memory_ids",
            "grounded_turn_ids",
        }
        if session.mode == "DIRECTIONAL":
            result_keys.update({"operation", "target_memory_ids"})
            if multi_target:
                result_keys.add("target_context_id")
        record = _exact_dict(
            item,
            result_keys,
            "meld result",
        )
        result_records.append((_key(record["result_key"], "meld result key"), record))
    result_keys = [key for key, _ in result_records]
    if len(result_keys) != len(set(result_keys)):
        raise MeldProviderError("Codex meld returned duplicate result keys.")
    proposals: list[MeldProposal] = []
    for key, record in result_records:
        relation_uids = _mapped(
            _keys(
                record["relation_keys"],
                "meld result relation keys",
                empty=True,
            ),
            relation_uid_by_key,
            "meld result relation key",
        )
        source_ids = _keys(
            record["source_memory_ids"],
            "meld result source Memory ids",
            empty=True,
        )
        if any(source_id not in view.memory_by_id for source_id in source_ids):
            raise MeldProviderError(
                "Codex meld returned an unknown result source Memory."
            )
        turn_uids = _mapped(
            _keys(
                record["grounded_turn_ids"],
                "meld result grounding turn ids",
                empty=True,
            ),
            view.turn_by_id,
            "meld result grounding turn id",
        )
        disposition = _literal(
            record["disposition"],
            _DISPOSITIONS,
            "meld result disposition",
        )
        if disposition == "USER_ADD":
            if source_ids or not turn_uids:
                raise MeldProviderError(
                    "Codex meld returned a USER_ADD with invalid evidence."
                )
        elif not source_ids:
            raise MeldProviderError(
                "Codex meld returned a source-derived result without source "
                "Memory evidence."
            )
        proposal_uid = (
            view.prior_proposal_by_id[key]
            if key in view.prior_proposal_by_id
            else _stable_uid(session.uid, current.uid, "proposal", key)
        )
        operation = "ADD"
        proposal_source_ids = source_ids
        owner_identity: tuple[str, str] | None = None
        memory_uid = str(
            uuid.uuid5(
                uuid.UUID(session.uid),
                f"memory:{proposal_uid}",
            )
        )
        if session.mode == "DIRECTIONAL":
            if multi_target:
                target_context_id = _key(
                    record["target_context_id"],
                    "meld result target Context id",
                )
                owner_identity = view.target_context_by_id.get(target_context_id)
                if owner_identity is None:
                    raise MeldProviderError(
                        "Codex meld returned a result outside the BASELINE subtree."
                    )
            else:
                owner_identity = next(iter(view.target_context_by_id.values()))
            operation = _literal(
                record["operation"],
                {"ADD", "EDIT"},
                "meld result operation",
            )
            target_ids = _keys(
                record["target_memory_ids"],
                "meld result target Memory ids",
                empty=True,
            )
            if operation == "ADD":
                if target_ids:
                    raise MeldProviderError(
                        "Codex meld returned an ADD with an edit target."
                    )
            else:
                if len(target_ids) != 1:
                    raise MeldProviderError(
                        "Codex meld returned an EDIT without one target."
                    )
                target_id = target_ids[0]
                target_member = view.memory_by_id.get(target_id)
                if target_member is None:
                    raise MeldProviderError(
                        "Codex meld returned an EDIT with an unknown target."
                    )
                if target_member.frame_uid != session.frames[1].uid:
                    raise MeldProviderError(
                        "Codex meld returned an EDIT outside the BASELINE."
                    )
                target_owner = view.memory_owner_by_id.get(target_id)
                if target_owner is not None and target_owner != owner_identity:
                    raise MeldProviderError(
                        "Codex meld returned an EDIT under the wrong target Context."
                    )
                memory_uid = target_member.memory_uid
                # `target_memory_ids` is already an explicit, validated
                # BASELINE citation. Store it once in the proposal evidence
                # even when the model sensibly omits that duplicate alias from
                # `source_memory_ids`.
                proposal_source_ids = (
                    source_ids if target_id in source_ids else (*source_ids, target_id)
                )
        proposal_value: dict[str, object] = {
            "uid": proposal_uid,
            "operation": operation,
            "disposition": disposition,
            "memory_uid": memory_uid,
            "content": _string(
                record["content"],
                "meld result content",
            ),
            "reason": _string(
                record["reason"],
                "meld result reason",
            ),
            "relation_uids": list(relation_uids),
            "source_members": [
                view.memory_by_id[source_id].to_dict()
                for source_id in proposal_source_ids
            ],
            "grounded_by_turn_uids": list(turn_uids),
        }
        if owner_identity is not None:
            proposal_value["owner_context"] = {
                "uid": owner_identity[0],
                "name": owner_identity[1],
            }
        proposals.append(MeldProposal.from_dict(proposal_value))

    try:
        return MeldAssessment.from_dict(
            {
                "overview": _string(
                    data["overview"],
                    "meld overview",
                ),
                "relations": [relation.to_dict() for relation in relations],
                "issues": [issue.to_dict() for issue in issues],
                "proposals": [proposal.to_dict() for proposal in proposals],
                "ready_to_apply": data["ready_to_apply"],
            }
        )
    except MeldError as error:
        raise MeldProviderError(str(error)) from error


def _expand_directional_comparison_response(
    raw: object,
    *,
    view: _ProviderView,
) -> str:
    """Reattach the trusted Compare ledger to one compact Directional result."""

    if (
        not isinstance(raw, str)
        or not raw.strip()
        or len(raw) > MELD_RESPONSE_CHAR_LIMIT
    ):
        raise MeldProviderError("Codex meld returned invalid structured output.")
    try:
        value = json.loads(raw, object_pairs_hook=_strict_json_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise MeldProviderError(
            "Codex meld returned invalid structured output."
        ) from error
    compact = _exact_dict(
        value,
        {"overview", "additional_issues", "results", "ready_to_apply"},
        "directional comparison meld response",
    )
    basis = _exact_dict(
        view.payload.get("comparison_basis"),
        {
            "overview",
            "paired_relations",
            "distinct_relations",
            "issues",
            "results",
            "ready_to_apply",
        },
        "directional comparison basis",
    )
    additional_issues = _array(
        compact["additional_issues"],
        "directional meld additional issues",
    )
    imported_issues = _array(
        basis["issues"],
        "directional meld imported issues",
    )
    # The ordinary decoder remains the single authority for relation aliases,
    # issue references, result ownership, and exact application invariants.
    return json.dumps(
        {
            "overview": compact["overview"],
            "paired_relations": basis["paired_relations"],
            "distinct_relations": basis["distinct_relations"],
            "issues": [*imported_issues, *additional_issues],
            "results": compact["results"],
            "ready_to_apply": compact["ready_to_apply"],
        },
        ensure_ascii=False,
    )
