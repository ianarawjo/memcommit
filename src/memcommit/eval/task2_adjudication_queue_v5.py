"""Read-only adjudication queue for fixed-input Task 2 v5 judge ledgers.

The queue is diagnostic evidence, not a relabeling mechanism.  Every supplied
ledger is first validated by the strict v5 record comparator, including a
self-comparison and a same-freeze comparison against the first ledger.  Only
then does this module join predictions to the locally locked fixture text.

The relation sidecar is a reviewed *partition*.  Consequently, a cross-group
candidate is shown as a partition-induced negative, never as independently
reviewed pair Gold.  Multi-member positive edges likewise carry the existing
group-induced enum boundary.  Only one-to-one positive edges are described as
direct reviewed relationships.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import TypeAlias

from memcommit.eval.task2_discovery import (
    Task2DiscoveryInput,
    Task2GoldRelation,
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_judge_replay_v5 import (
    TASK2_ACCEPTED_JUDGE_LABELS,
    TASK2_GROUP_INDUCED_GOLD_BOUNDARY,
    TASK2_JUDGE_REPLAY_V5_KIND,
    Task2JudgeReplayV5Error,
    compare_task2_judge_replay_v5_records,
)


TASK2_ADJUDICATION_QUEUE_V5_KIND = (
    "memcommit.semantic-eval.task2-judge-adjudication-queue-v5"
)
TASK2_ADJUDICATION_QUEUE_V5_SCHEMA_VERSION = 1

REVIEWED_DIRECT_POSITIVE_BOUNDARY = "REVIEWED_ONE_TO_ONE_DIRECT_POSITIVE"
GROUP_INDUCED_POSITIVE_BOUNDARY = (
    "GROUP_INDUCED_MULTI_MEMBER_POSITIVE_NOT_INDEPENDENT_CARTESIAN_PAIR_GOLD"
)
PARTITION_INDUCED_NEGATIVE_BOUNDARY = (
    "PARTITION_INDUCED_CROSS_HYPERGROUP_NEGATIVE_NOT_INDEPENDENTLY_"
    "REVIEWED_PAIR_GOLD"
)

COMMON_ACCEPT_PARTITION_NEGATIVE = (
    "ALL_PROVIDERS_ACCEPT_PARTITION_INDUCED_NEGATIVE"
)
PROVIDER_DISAGREEMENT = "PROVIDER_DISAGREEMENT"
DIRECT_TEACHER_ERROR = "REVIEWED_DIRECT_POSITIVE_REFERENCE_TEACHER_ERROR"
DIRECT_STUDENT_ERROR = "REVIEWED_DIRECT_POSITIVE_STUDENT_ERROR"
MULTI_POSITIVE_REJECTED = "MULTI_MEMBER_GROUP_POSITIVE_REJECTED"
MULTI_POSITIVE_ENUM_MISMATCH = "MULTI_MEMBER_GROUP_INDUCED_ENUM_MISMATCH"
MULTI_PARTITION_NEGATIVE_ACCEPTED = (
    "MULTI_MEMBER_SOURCE_PARTITION_NEGATIVE_ACCEPTED"
)

_BAND_TO_LABEL = {
    "Near Duplicate": "NEAR_DUPLICATE",
    "Same-Principle Variant": "SAME_PRINCIPLE",
    "Context-Dependent Variant": "CONTEXT_VARIANT",
    "Conflict": "CONFLICT",
    "Compatible Complement": "COMPLEMENT_OR_JOINT_PART",
}

JudgeLedgerInput: TypeAlias = Mapping[str, object] | str | Path


class Task2AdjudicationQueueV5Error(RuntimeError):
    """The requested queue cannot be proven to use one valid replay freeze."""


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(value: object, *, indent: int | None = None) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=indent,
            separators=(",", ":") if indent is None else None,
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication data is not strict JSON."
        ) from error


def _load_ledger(value: JudgeLedgerInput) -> dict[str, object]:
    if isinstance(value, Mapping):
        record = dict(value)
    elif isinstance(value, (str, Path)):
        path = Path(value)
        try:
            decoded = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_strict_object,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise Task2AdjudicationQueueV5Error(
                "Task 2 judge ledger is not strict UTF-8 JSON."
            ) from error
        if not isinstance(decoded, dict):
            raise Task2AdjudicationQueueV5Error(
                "Task 2 judge ledger must be a JSON object."
            )
        record = decoded
    else:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 judge ledger must be a mapping or path."
        )
    # Mapping inputs receive the same finite, JSON-only boundary as files.
    _strict_json(record)
    return record


def _strictly_validate_one_freeze(
    records: Sequence[Mapping[str, object]],
) -> None:
    try:
        for record in records:
            compare_task2_judge_replay_v5_records(record, record)
        first = records[0]
        for record in records[1:]:
            compare_task2_judge_replay_v5_records(first, record)
    except Task2JudgeReplayV5Error as error:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication requires strictly valid ledgers from one "
            "frozen judge replay."
        ) from error


def _model_sort_key(
    record: Mapping[str, object], *, teacher_run_id: str
) -> tuple[object, ...]:
    identity = record["provider"]
    assert isinstance(identity, Mapping)  # Guaranteed by the strict comparator.
    run_id = record["run_id"]
    assert isinstance(run_id, str)
    return (
        0 if run_id == teacher_run_id else 1,
        str(identity.get("provider", "")),
        str(identity.get("model", "")),
        str(identity.get("reasoning_effort", "")),
        str(record.get("effective_thinking", "")),
        run_id,
    )


def _optional_identity_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _model_identities(
    records: Sequence[Mapping[str, object]], *, teacher_run_id: str
) -> tuple[list[dict[str, object]], dict[str, str]]:
    ordered = sorted(
        records,
        key=lambda record: _model_sort_key(record, teacher_run_id=teacher_run_id),
    )
    identities: list[dict[str, object]] = []
    model_id_by_run: dict[str, str] = {}
    for index, record in enumerate(ordered, start=1):
        run_id = record["run_id"]
        identity = record["provider"]
        assert isinstance(run_id, str) and isinstance(identity, Mapping)
        model_id = f"m{index:02d}"
        model_id_by_run[run_id] = model_id
        identities.append(
            {
                "model_id": model_id,
                "role": (
                    "REFERENCE_TEACHER"
                    if run_id == teacher_run_id
                    else "STUDENT_UNDER_TEST"
                ),
                "run_id": run_id,
                "provider": identity["provider"],
                "model": identity["model"],
                "model_digest": _optional_identity_string(
                    identity.get("model_digest")
                ),
                "runtime": _optional_identity_string(identity.get("runtime")),
                "reasoning_effort": _optional_identity_string(
                    identity.get("reasoning_effort")
                ),
                "effective_thinking": _optional_identity_string(
                    record.get("effective_thinking")
                ),
            }
        )
    return identities, model_id_by_run


def _fixture_maps(
    value: Task2DiscoveryInput,
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, tuple[Task2GoldRelation, str]],
]:
    fixtures: dict[str, dict[str, str]] = {}
    for side, items in (("LEFT", value.left_items), ("RIGHT", value.right_items)):
        for item in items:
            fixture_id = value.alias_to_fixture_id[item["id"]]
            fixtures[fixture_id] = {
                "fixture_id": fixture_id,
                "side": side,
                "topic": item["topic"],
                "content": item["content"],
            }
    relations: dict[str, tuple[Task2GoldRelation, str]] = {}
    for relation in value.expected:
        relations.update(
            {fixture_id: (relation, "LEFT") for fixture_id in relation.left_fixture_ids}
        )
        relations.update(
            {
                fixture_id: (relation, "RIGHT")
                for fixture_id in relation.right_fixture_ids
            }
        )
    return fixtures, relations


def _expected_boundary(
    *,
    source_fixture_id: str,
    target_fixture_id: str,
    relation_by_fixture: Mapping[str, tuple[Task2GoldRelation, str]],
) -> dict[str, object]:
    source_relation, source_side = relation_by_fixture[source_fixture_id]
    target_relation, target_side = relation_by_fixture[target_fixture_id]
    same_hypergroup = source_relation.pair_id == target_relation.pair_id
    if source_side == target_side:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication candidate does not cross advisor sides."
        )
    source_is_multi = (
        len(source_relation.left_fixture_ids) > 1
        or len(source_relation.right_fixture_ids) > 1
    )
    if not same_hypergroup:
        return {
            "basis": PARTITION_INDUCED_NEGATIVE_BOUNDARY,
            "label": "UNRELATED",
            "same_hypergroup": False,
            "independently_reviewed_pair_label": False,
            "source_hypergroup_id": source_relation.pair_id,
            "target_hypergroup_id": target_relation.pair_id,
            "relationship_band": None,
            "source_group_is_multi_member": source_is_multi,
        }
    is_direct = (
        len(source_relation.left_fixture_ids)
        == len(source_relation.right_fixture_ids)
        == 1
    )
    return {
        "basis": (
            REVIEWED_DIRECT_POSITIVE_BOUNDARY
            if is_direct
            else GROUP_INDUCED_POSITIVE_BOUNDARY
        ),
        "label": _BAND_TO_LABEL[source_relation.band],
        "same_hypergroup": True,
        "independently_reviewed_pair_label": is_direct,
        "source_hypergroup_id": source_relation.pair_id,
        "target_hypergroup_id": target_relation.pair_id,
        "relationship_band": source_relation.band,
        "source_group_is_multi_member": source_is_multi,
    }


def _decision_map(record: Mapping[str, object]) -> dict[tuple[str, str, str], str]:
    decisions = record["decisions"]
    assert isinstance(decisions, list)  # Guaranteed by the strict comparator.
    result: dict[tuple[str, str, str], str] = {}
    for decision in decisions:
        assert isinstance(decision, Mapping)
        key = (
            str(decision["direction"]),
            str(decision["source_fixture_id"]),
            str(decision["target_fixture_id"]),
        )
        result[key] = str(decision["label"])
    return result


def _reason(
    code: str,
    priority: str,
    explanation: str,
    *,
    model_ids: Sequence[str] = (),
    disagreement_scope: str | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "priority": priority,
        "model_ids": list(model_ids),
        "disagreement_scope": disagreement_scope,
        "explanation": explanation,
    }


_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


def _pair_reasons(
    *,
    expected: Mapping[str, object],
    predictions: Sequence[Mapping[str, object]],
    teacher_model_id: str,
) -> list[dict[str, object]]:
    labels = {str(item["label"]) for item in predictions}
    accepted_ids = [
        str(item["model_id"]) for item in predictions if item["accepted"] is True
    ]
    rejected_ids = [
        str(item["model_id"]) for item in predictions if item["accepted"] is False
    ]
    mismatched_ids = [
        str(item["model_id"])
        for item in predictions
        if item["matches_existing_expected_enum"] is False
    ]
    reasons: list[dict[str, object]] = []
    if (
        expected["basis"] == PARTITION_INDUCED_NEGATIVE_BOUNDARY
        and len(accepted_ids) == len(predictions)
    ):
        reasons.append(
            _reason(
                COMMON_ACCEPT_PARTITION_NEGATIVE,
                "P0",
                "All providers accept this pair, while the current rejection "
                "is induced only by cross-hypergroup partition membership; "
                "adjudicate the boundary before attributing model error.",
                model_ids=accepted_ids,
            )
        )
    if len(labels) > 1:
        binary_values = {bool(item["accepted"]) for item in predictions}
        scope = "ACCEPT_REJECT" if len(binary_values) > 1 else "ENUM_ONLY"
        reasons.append(
            _reason(
                PROVIDER_DISAGREEMENT,
                "P1" if scope == "ACCEPT_REJECT" else "P2",
                "Providers returned different fixed-input judgments.",
                model_ids=[str(item["model_id"]) for item in predictions],
                disagreement_scope=scope,
            )
        )
    if expected["basis"] == REVIEWED_DIRECT_POSITIVE_BOUNDARY:
        if teacher_model_id in mismatched_ids:
            reasons.append(
                _reason(
                    DIRECT_TEACHER_ERROR,
                    "P0",
                    "The reference teacher does not match the reviewed direct "
                    "one-to-one relationship enum.",
                    model_ids=[teacher_model_id],
                )
            )
        student_errors = sorted(
            model_id for model_id in mismatched_ids if model_id != teacher_model_id
        )
        if student_errors:
            reasons.append(
                _reason(
                    DIRECT_STUDENT_ERROR,
                    "P1",
                    "At least one student does not match the reviewed direct "
                    "one-to-one relationship enum.",
                    model_ids=student_errors,
                )
            )
    if expected["source_group_is_multi_member"] is True:
        if expected["same_hypergroup"] is True:
            if rejected_ids:
                reasons.append(
                    _reason(
                        MULTI_POSITIVE_REJECTED,
                        "P1",
                        "At least one provider rejects an edge induced by the "
                        "reviewed multi-member hypergroup.",
                        model_ids=rejected_ids,
                    )
                )
            accepted_enum_mismatches = sorted(
                model_id
                for model_id in mismatched_ids
                if model_id not in rejected_ids
            )
            if accepted_enum_mismatches:
                reasons.append(
                    _reason(
                        MULTI_POSITIVE_ENUM_MISMATCH,
                        "P2",
                        "At least one accepting provider differs from the "
                        "existing group-induced relationship enum; this enum is "
                        "not independent Cartesian-pair Gold.",
                        model_ids=accepted_enum_mismatches,
                    )
                )
        elif accepted_ids:
            reasons.append(
                _reason(
                    MULTI_PARTITION_NEGATIVE_ACCEPTED,
                    "P2",
                    "At least one provider accepts a candidate whose current "
                    "negative status is induced by the source hypergroup's "
                    "partition boundary, not an independently reviewed pair.",
                    model_ids=accepted_ids,
                )
            )
    return sorted(
        reasons,
        key=lambda item: (
            _PRIORITY_RANK[str(item["priority"])],
            str(item["code"]),
            tuple(str(value) for value in item["model_ids"]),
        ),
    )


def build_task2_judge_adjudication_queue_v5(
    ledgers: Sequence[JudgeLedgerInput],
    *,
    teacher_run_id: str,
) -> dict[str, object]:
    """Return a deterministic, read-only review queue for one replay freeze.

    ``teacher_run_id`` assigns a reference role for direct-positive error
    routing only.  It does not make that model Gold and cannot change any
    expected label.
    """
    if isinstance(ledgers, (str, bytes, Path)) or len(ledgers) < 2:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication requires at least two judge ledgers."
        )
    if not isinstance(teacher_run_id, str) or not teacher_run_id:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication requires an explicit teacher run ID."
        )
    records = [_load_ledger(ledger) for ledger in ledgers]
    run_ids = [record.get("run_id") for record in records]
    if (
        any(not isinstance(run_id, str) or not run_id for run_id in run_ids)
        or len(set(run_ids)) != len(run_ids)
    ):
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication requires distinct nonempty run IDs."
        )
    if teacher_run_id not in run_ids:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication teacher run ID is not among the ledgers."
        )
    _strictly_validate_one_freeze(records)

    identities, model_id_by_run = _model_identities(
        records, teacher_run_id=teacher_run_id
    )
    record_by_run = {str(record["run_id"]): record for record in records}
    ordered_records = [record_by_run[str(item["run_id"])] for item in identities]
    teacher_model_id = model_id_by_run[teacher_run_id]

    first = ordered_records[0]
    corpus_info = first["corpus"]
    bundle = first["candidate_bundle"]
    assert isinstance(corpus_info, Mapping) and isinstance(bundle, Mapping)
    language = str(corpus_info["language"])
    group_count = int(corpus_info["group_count"])
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language=language),
        group_count=group_count,
    )
    fixtures, relations = _fixture_maps(value)
    decisions_by_run = {
        str(record["run_id"]): _decision_map(record) for record in ordered_records
    }
    raw_pairs = bundle["pairs"]
    assert isinstance(raw_pairs, list)

    items: list[dict[str, object]] = []
    for raw_pair in raw_pairs:
        assert isinstance(raw_pair, Mapping)
        direction = str(raw_pair["direction"])
        source_fixture_id = str(raw_pair["source_fixture_id"])
        target_fixture_id = str(raw_pair["target_fixture_id"])
        key = (direction, source_fixture_id, target_fixture_id)
        expected = _expected_boundary(
            source_fixture_id=source_fixture_id,
            target_fixture_id=target_fixture_id,
            relation_by_fixture=relations,
        )
        predictions: list[dict[str, object]] = []
        for identity in identities:
            run_id = str(identity["run_id"])
            label = decisions_by_run[run_id][key]
            accepted = label in TASK2_ACCEPTED_JUDGE_LABELS
            predictions.append(
                {
                    "model_id": identity["model_id"],
                    "role": identity["role"],
                    "label": label,
                    "accepted": accepted,
                    "matches_existing_expected_enum": label == expected["label"],
                    "matches_existing_accept_reject_boundary": (
                        accepted is expected["same_hypergroup"]
                    ),
                }
            )
        reasons = _pair_reasons(
            expected=expected,
            predictions=predictions,
            teacher_model_id=teacher_model_id,
        )
        if not reasons:
            continue
        priority = min(
            (str(reason["priority"]) for reason in reasons),
            key=_PRIORITY_RANK.__getitem__,
        )
        items.append(
            {
                "item_id": (
                    f"aq-{direction.lower()}-{source_fixture_id}-{target_fixture_id}"
                ),
                "priority": priority,
                "reason_codes": [str(reason["code"]) for reason in reasons],
                "reasons": reasons,
                "direction": direction,
                "source": fixtures[source_fixture_id],
                "target": fixtures[target_fixture_id],
                "existing_expected_boundary": expected,
                "predictions": predictions,
                "adjudication_state": "UNADJUDICATED_EXISTING_LABEL_UNCHANGED",
            }
        )

    items.sort(
        key=lambda item: (
            _PRIORITY_RANK[str(item["priority"])],
            tuple(str(code) for code in item["reason_codes"]),
            str(item["direction"]),
            str(item["source"]["fixture_id"]),  # type: ignore[index]
            str(item["target"]["fixture_id"]),  # type: ignore[index]
        )
    )
    reason_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    boundary_counts: Counter[str] = Counter()
    for item in items:
        priority_counts[str(item["priority"])] += 1
        expected = item["existing_expected_boundary"]
        assert isinstance(expected, Mapping)
        boundary_counts[str(expected["basis"])] += 1
        reason_counts.update(str(code) for code in item["reason_codes"])

    report: dict[str, object] = {
        "kind": TASK2_ADJUDICATION_QUEUE_V5_KIND,
        "schema_version": TASK2_ADJUDICATION_QUEUE_V5_SCHEMA_VERSION,
        "source_kind": TASK2_JUDGE_REPLAY_V5_KIND,
        "mode": "READ_ONLY_NO_RELABELING",
        "replay_freeze_digest": bundle["replay_freeze_digest"],
        "candidate_bundle_digest": bundle["digest"],
        "group_count": group_count,
        "reference_teacher_model_id": teacher_model_id,
        "model_identities": identities,
        "expected_boundary_notes": {
            "reviewed_direct_positive": REVIEWED_DIRECT_POSITIVE_BOUNDARY,
            "group_induced_positive": GROUP_INDUCED_POSITIVE_BOUNDARY,
            "group_induced_enum_boundary": TASK2_GROUP_INDUCED_GOLD_BOUNDARY,
            "partition_induced_negative": PARTITION_INDUCED_NEGATIVE_BOUNDARY,
            "cross_group_negative_is_independently_reviewed_pair_gold": False,
            "queue_can_relabel": False,
            "teacher_is_gold": False,
        },
        "summary": {
            "ledger_count": len(records),
            "candidate_pair_count": len(raw_pairs),
            "queue_item_count": len(items),
            "counts_by_priority": dict(sorted(priority_counts.items())),
            "counts_by_reason": dict(sorted(reason_counts.items())),
            "counts_by_existing_boundary": dict(sorted(boundary_counts.items())),
        },
        "items": items,
    }
    # Keep the public output serializable and reject accidental NaN or custom
    # objects without introducing a write side effect.
    _strict_json(report)
    return report


def render_task2_judge_adjudication_queue_v5(
    report: Mapping[str, object],
) -> str:
    """Render deterministic JSON without creating or changing any file."""
    if report.get("kind") != TASK2_ADJUDICATION_QUEUE_V5_KIND:
        raise Task2AdjudicationQueueV5Error(
            "Task 2 adjudication report kind is invalid."
        )
    return _strict_json(report, indent=2) + "\n"
