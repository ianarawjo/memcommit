"""Contracts for participant-readable Task 2 Advisor rationale neighborhoods."""

from __future__ import annotations

from collections import Counter
import csv

from memcommit.application.evaluation.study_fixtures import default_fixture_root, load_study_fixture


CONFLICT_IDS = {
    "T2-001",
    "T2-009",
    "T2-014",
    "T2-018",
    "T2-019",
    "T2-022",
    "T2-023",
    "T2-026",
}

RATIONALE_NEIGHBORHOODS = {
    "opening-length": {
        "left": {"T2-L-001", "T2-L-054", "T2-L-070", "T2-L-080"},
        "right": {"T2-R-001", "T2-R-054", "T2-R-070", "T2-R-080"},
    },
    "subheading-flow": {
        "left": {
            "T2-L-018",
            "T2-L-083",
            "T2-L-084",
            "T2-L-095",
            "T2-L-096",
            "T2-L-097",
        },
        "right": {
            "T2-R-018",
            "T2-R-083",
            "T2-R-093",
            "T2-R-094",
            "T2-R-095",
            "T2-R-096",
        },
    },
    "author-voice": {
        "left": {"T2-L-019", "T2-L-057", "T2-L-106", "T2-L-107", "T2-L-108"},
        "right": {"T2-R-019", "T2-R-057", "T2-R-104", "T2-R-105", "T2-R-106"},
    },
    "target-count": {
        "left": {"T2-L-022", "T2-L-034", "T2-L-115", "T2-L-116", "T2-L-117"},
        "right": {
            "T2-R-022",
            "T2-R-034",
            "T2-R-113",
            "T2-R-114",
            "T2-R-115",
            "T2-R-116",
            "T2-R-117",
        },
    },
    "budget-placement": {
        "left": {
            "T2-L-023",
            "T2-L-031",
            "T2-L-066",
            "T2-L-079",
            "T2-L-141",
            "T2-L-142",
            "T2-L-143",
        },
        "right": {
            "T2-R-023",
            "T2-R-031",
            "T2-R-066",
            "T2-R-079",
            "T2-R-142",
            "T2-R-143",
            "T2-R-144",
        },
    },
}


def _records(language: str, dataset: str):
    return {
        memory.fixture_id: memory
        for memory in load_study_fixture(dataset, language=language).records
    }


def test_eight_conflicts_are_identical_in_english_and_korean_sidecars() -> None:
    root = default_fixture_root()
    for language in ("en", "ko"):
        path = root / language / f"task-2-pair-relations-{language}.tsv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = tuple(csv.DictReader(stream, delimiter="\t"))
        distribution = Counter(row["relationship_band"] for row in rows)
        assert distribution == {
            "Near Duplicate": 65,
            "Same-Principle Variant": 26,
            "Context-Dependent Variant": 37,
            "Conflict": 8,
            "Compatible Complement": 2,
        }
        assert {
            row["pair_id"]
            for row in rows
            if row["relationship_band"] == "Conflict"
        } == CONFLICT_IDS


def test_five_new_choices_have_non_rule_support_in_the_same_context_subtree() -> None:
    for language in ("en", "ko"):
        sides = {
            "left": _records(language, "task2-advisor1"),
            "right": _records(language, "task2-advisor2"),
        }
        for neighborhood in RATIONALE_NEIGHBORHOODS.values():
            for side, fixture_ids in neighborhood.items():
                memories = [sides[side][fixture_id] for fixture_id in fixture_ids]
                # The builder maps the first locator segment to one direct
                # descendant Context. Keeping target and support together makes
                # parent-scoped Rationale useful without inventing provenance.
                assert len({memory.locator.split("/", 1)[0] for memory in memories}) == 1
                assert any(memory.purpose != "PP" for memory in memories)


def test_advisor_memory_voice_matches_reader_user_and_self_perspectives() -> None:
    english_left = _records("en", "task2-advisor1")
    english_right = _records("en", "task2-advisor2")
    korean_left = _records("ko", "task2-advisor1")
    korean_right = _records("ko", "task2-advisor2")

    for records in (english_left, english_right):
        assert not any(
            memory.content.startswith(
                ("This advisor", "The agent", "The user writing this proposal")
            )
            for memory in records.values()
        )
    for records in (korean_left, korean_right):
        assert not any(
            memory.content.startswith(
                ("이 advisor는", "the agent는", "이 제안서를 작성하는 사용자는")
            )
            for memory in records.values()
        )

    assert english_left["T2-L-057"].content.startswith(
        "When a commitment is phrased passively"
    )
    assert korean_left["T2-L-057"].content.startswith("약속을 수동태로 표현하면")
    assert english_left["T2-L-107"].purpose == "PP"
    assert english_right["T2-R-105"].purpose == "PP"
    assert "should not alternate between “I” and “we”" in english_left[
        "T2-L-107"
    ].content
    assert "should not mix them" in english_right["T2-R-105"].content
    assert english_left["T2-L-034"].purpose == "OM"
    assert english_right["T2-R-034"].purpose == "OM"
    assert english_left["T2-L-105"].content.startswith("The user")
    assert korean_left["T2-L-105"].content.startswith("사용자는")
    for records in (english_left, english_right):
        assert not any(memory.content.startswith("I ") for memory in records.values())
    for records in (korean_left, korean_right):
        assert not any(memory.content.startswith("나는 ") for memory in records.values())
