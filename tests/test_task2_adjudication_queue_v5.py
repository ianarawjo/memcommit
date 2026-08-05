"""Read-only Task 2 v5 adjudication queue contracts."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from memcommit.eval.task2_adjudication_queue_v5 import (
    COMMON_ACCEPT_PARTITION_NEGATIVE,
    DIRECT_STUDENT_ERROR,
    DIRECT_TEACHER_ERROR,
    GROUP_INDUCED_POSITIVE_BOUNDARY,
    MULTI_PARTITION_NEGATIVE_ACCEPTED,
    MULTI_POSITIVE_REJECTED,
    PARTITION_INDUCED_NEGATIVE_BOUNDARY,
    PROVIDER_DISAGREEMENT,
    REVIEWED_DIRECT_POSITIVE_BOUNDARY,
    Task2AdjudicationQueueV5Error,
    build_task2_judge_adjudication_queue_v5,
    render_task2_judge_adjudication_queue_v5,
)
from memcommit.eval.task2_discovery import (
    build_task2_discovery_input,
    load_task2_discovery_corpus,
)
from memcommit.eval.task2_judge_replay_v5 import (
    _PAYLOAD_MARKER,
    build_task2_judge_replay_v5_input,
    run_task2_judge_replay_v5_campaign,
)
from memcommit.eval.task2_retrieval_v4 import (
    LEFT_TO_RIGHT,
    RIGHT_TO_LEFT,
    run_task2_retrieval_v4_campaign,
)
from memcommit.provider_types import ProviderIdentity
from tests.test_task2_judge_replay_v5 import JudgeTeacher, V4ParentTeacher


class ControlledJudge(JudgeTeacher):
    """Fixture teacher with explicit pair-level diagnostic mistakes."""

    def __init__(self, value, *, name: str, overrides) -> None:
        super().__init__(value)
        self.identity = ProviderIdentity(
            provider=name,
            model=f"{name}-model",
            model_digest=(name[0] * 64),
            runtime="pytest",
        )
        self.overrides = dict(overrides)
        self.left_fixture_ids = {
            value.alias_to_fixture_id[item["id"]] for item in value.left_items
        }

    def _answer(self, prompt: str) -> str:
        decoded = json.loads(super()._answer(prompt))
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        for pair, judgment in zip(
            payload["pairs"], decoded["judgments"], strict=True
        ):
            source = self.fixture_by_text[
                (pair["source"]["topic"], pair["source"]["content"])
            ]
            target = self.fixture_by_text[
                (pair["target"]["topic"], pair["target"]["content"])
            ]
            direction = (
                LEFT_TO_RIGHT if source in self.left_fixture_ids else RIGHT_TO_LEFT
            )
            key = (direction, source, target)
            if key in self.overrides:
                judgment["label"] = self.overrides[key]
        return json.dumps(decoded)


def _different_accept_label(label: str) -> str:
    return "CONFLICT" if label != "CONFLICT" else "NEAR_DUPLICATE"


@pytest.fixture
def queue_records(tmp_path):
    value = build_task2_discovery_input(
        load_task2_discovery_corpus(language="en"), group_count=26
    )
    parents = [
        run_task2_retrieval_v4_campaign(
            V4ParentTeacher(value, reverse_fillers=reverse),  # type: ignore[arg-type]
            ledger_dir=tmp_path,
            provider_connection_seconds=0.0,
            group_count=26,
        )
        for reverse in (False, True)
    ]
    replay = build_task2_judge_replay_v5_input(parents)
    relation_by_fixture = {
        fixture_id: relation
        for relation in value.expected
        for fixture_id in (*relation.left_fixture_ids, *relation.right_fixture_ids)
    }
    direct = [
        relation
        for relation in value.expected
        if len(relation.left_fixture_ids) == len(relation.right_fixture_ids) == 1
    ]
    multi = next(
        relation
        for relation in value.expected
        if len(relation.left_fixture_ids) > 1
        or len(relation.right_fixture_ids) > 1
    )
    direct_teacher = (
        LEFT_TO_RIGHT,
        direct[0].left_fixture_ids[0],
        direct[0].right_fixture_ids[0],
    )
    direct_student = (
        LEFT_TO_RIGHT,
        direct[1].left_fixture_ids[0],
        direct[1].right_fixture_ids[0],
    )
    multi_positive = (
        LEFT_TO_RIGHT,
        multi.left_fixture_ids[0],
        multi.right_fixture_ids[0],
    )
    multi_sources = set(multi.left_fixture_ids) | set(multi.right_fixture_ids)
    common_cross = next(
        (pair.direction, pair.source_fixture_id, pair.target_fixture_id)
        for pair in replay.candidate_pairs
        if pair.source_fixture_id in multi_sources
        and relation_by_fixture[pair.source_fixture_id].pair_id
        != relation_by_fixture[pair.target_fixture_id].pair_id
    )
    direct_teacher_label = {
        relation.pair_id: {
            "Near Duplicate": "NEAR_DUPLICATE",
            "Same-Principle Variant": "SAME_PRINCIPLE",
            "Context-Dependent Variant": "CONTEXT_VARIANT",
            "Conflict": "CONFLICT",
            "Compatible Complement": "COMPLEMENT_OR_JOINT_PART",
        }[relation.band]
        for relation in value.expected
    }[direct[0].pair_id]

    teacher = run_task2_judge_replay_v5_campaign(
        ControlledJudge(
            value,
            name="teacher",
            overrides={
                common_cross: "SAME_PRINCIPLE",
                direct_teacher: _different_accept_label(direct_teacher_label),
            },
        ),  # type: ignore[arg-type]
        parent_ledgers=parents,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    student_a = run_task2_judge_replay_v5_campaign(
        ControlledJudge(
            value,
            name="student-a",
            overrides={
                common_cross: "SAME_PRINCIPLE",
                direct_student: "UNRELATED",
                multi_positive: "UNRELATED",
            },
        ),  # type: ignore[arg-type]
        parent_ledgers=parents,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    student_b = run_task2_judge_replay_v5_campaign(
        ControlledJudge(
            value,
            name="student-b",
            overrides={common_cross: "SAME_PRINCIPLE"},
        ),  # type: ignore[arg-type]
        parent_ledgers=parents,
        ledger_dir=tmp_path,
        provider_connection_seconds=0.0,
    )
    return {
        "records": (teacher, student_a, student_b),
        "teacher_run_id": teacher["run_id"],
        "keys": {
            "common_cross": common_cross,
            "direct_teacher": direct_teacher,
            "direct_student": direct_student,
            "multi_positive": multi_positive,
        },
    }


def _item_by_key(report, key):
    direction, source, target = key
    return next(
        item
        for item in report["items"]
        if item["direction"] == direction
        and item["source"]["fixture_id"] == source
        and item["target"]["fixture_id"] == target
    )


def test_queue_is_deterministic_and_preserves_every_expected_boundary(queue_records):
    teacher, student_a, student_b = queue_records["records"]
    teacher_run_id = queue_records["teacher_run_id"]
    first = build_task2_judge_adjudication_queue_v5(
        [student_b, teacher, student_a], teacher_run_id=teacher_run_id
    )
    second = build_task2_judge_adjudication_queue_v5(
        [teacher, student_a, student_b], teacher_run_id=teacher_run_id
    )
    assert first == second
    assert first["mode"] == "READ_ONLY_NO_RELABELING"
    assert first["expected_boundary_notes"]["teacher_is_gold"] is False
    assert first["expected_boundary_notes"][
        "cross_group_negative_is_independently_reviewed_pair_gold"
    ] is False
    assert first["model_identities"][0]["role"] == "REFERENCE_TEACHER"
    assert all(
        item["adjudication_state"]
        == "UNADJUDICATED_EXISTING_LABEL_UNCHANGED"
        for item in first["items"]
    )

    cross = _item_by_key(first, queue_records["keys"]["common_cross"])
    assert COMMON_ACCEPT_PARTITION_NEGATIVE in cross["reason_codes"]
    assert MULTI_PARTITION_NEGATIVE_ACCEPTED in cross["reason_codes"]
    assert cross["priority"] == "P0"
    assert cross["existing_expected_boundary"] == {
        "basis": PARTITION_INDUCED_NEGATIVE_BOUNDARY,
        "label": "UNRELATED",
        "same_hypergroup": False,
        "independently_reviewed_pair_label": False,
        "source_hypergroup_id": cross["existing_expected_boundary"][
            "source_hypergroup_id"
        ],
        "target_hypergroup_id": cross["existing_expected_boundary"][
            "target_hypergroup_id"
        ],
        "relationship_band": None,
        "source_group_is_multi_member": True,
    }
    assert all(prediction["accepted"] for prediction in cross["predictions"])
    assert cross["source"]["topic"] and cross["source"]["content"]
    assert cross["target"]["topic"] and cross["target"]["content"]

    teacher_error = _item_by_key(
        first, queue_records["keys"]["direct_teacher"]
    )
    assert DIRECT_TEACHER_ERROR in teacher_error["reason_codes"]
    assert PROVIDER_DISAGREEMENT in teacher_error["reason_codes"]
    assert teacher_error["existing_expected_boundary"]["basis"] == (
        REVIEWED_DIRECT_POSITIVE_BOUNDARY
    )
    assert teacher_error["existing_expected_boundary"][
        "independently_reviewed_pair_label"
    ] is True

    student_error = _item_by_key(
        first, queue_records["keys"]["direct_student"]
    )
    assert DIRECT_STUDENT_ERROR in student_error["reason_codes"]
    assert PROVIDER_DISAGREEMENT in student_error["reason_codes"]

    multi_failure = _item_by_key(
        first, queue_records["keys"]["multi_positive"]
    )
    assert MULTI_POSITIVE_REJECTED in multi_failure["reason_codes"]
    assert PROVIDER_DISAGREEMENT in multi_failure["reason_codes"]
    assert multi_failure["existing_expected_boundary"]["basis"] == (
        GROUP_INDUCED_POSITIVE_BOUNDARY
    )
    assert multi_failure["existing_expected_boundary"][
        "independently_reviewed_pair_label"
    ] is False

    rendered = render_task2_judge_adjudication_queue_v5(first)
    assert rendered == render_task2_judge_adjudication_queue_v5(second)
    assert json.loads(rendered) == first


def test_queue_fails_closed_on_tampering_duplicates_and_unknown_teacher(
    queue_records,
):
    teacher, student_a, student_b = queue_records["records"]
    teacher_run_id = queue_records["teacher_run_id"]
    tampered = copy.deepcopy(student_a)
    tampered["decisions"][0]["label"] = (
        "CONFLICT"
        if tampered["decisions"][0]["label"] == "UNRELATED"
        else "UNRELATED"
    )
    with pytest.raises(Task2AdjudicationQueueV5Error, match="strictly valid"):
        build_task2_judge_adjudication_queue_v5(
            [teacher, tampered, student_b], teacher_run_id=teacher_run_id
        )

    with pytest.raises(Task2AdjudicationQueueV5Error, match="distinct"):
        build_task2_judge_adjudication_queue_v5(
            [teacher, teacher], teacher_run_id=teacher_run_id
        )
    with pytest.raises(Task2AdjudicationQueueV5Error, match="not among"):
        build_task2_judge_adjudication_queue_v5(
            [teacher, student_a], teacher_run_id="missing-run"
        )


def test_paths_and_rendering_are_read_only(queue_records, tmp_path):
    records = queue_records["records"]
    paths = [Path(str(record["ledger_path"])) for record in records]
    before = {path: path.read_bytes() for path in paths}
    before_files = sorted(path for path in tmp_path.rglob("*") if path.is_file())

    report = build_task2_judge_adjudication_queue_v5(
        list(reversed(paths)), teacher_run_id=queue_records["teacher_run_id"]
    )
    rendered = render_task2_judge_adjudication_queue_v5(report)

    assert rendered.endswith("\n")
    assert sorted(path for path in tmp_path.rglob("*") if path.is_file()) == before_files
    assert {path: path.read_bytes() for path in paths} == before
