"""Contracts for loading the Task 1--3 Markdown study fixtures."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from memcommit.eval.study_fixtures import (
    EXPECTED_CORPUS_COUNT,
    AudienceRole,
    FixtureDataset,
    FixtureSyntax,
    PurposeSidecarKey,
    StudyFixtureError,
    StudyFixtureSpec,
    load_study_fixture,
    load_study_fixture_corpus,
    pair_fixture_translations,
)


EXPECTED_DATASETS = {
    "task1-construction-updates": (
        75,
        {"KB": 35, "PP": 16, "SM": 8, "UM": 6, "WM": 4, "OM": 6},
    ),
    "task1-campus-wiki": (
        300,
        {
            "KB": 162,
            "PP": 41,
            "SM": 41,
            "UM": 29,
            "WM": 15,
            "OM": 12,
        },
    ),
    "task1-campus-wiki-details": (
        78,
        {"KB": 34, "PP": 38, "OM": 6},
    ),
    "task2-advisor1": (
        150,
        {"KB": 10, "PP": 95, "SM": 8, "UM": 8, "WM": 8, "OM": 21},
    ),
    "task2-advisor2": (
        150,
        {"KB": 10, "PP": 95, "SM": 8, "UM": 8, "WM": 8, "OM": 21},
    ),
    "task2-proposal-guidelines": (
        75,
        {"KB": 2, "PP": 57, "SM": 2, "UM": 2, "WM": 2, "OM": 10},
    ),
    "task3-personal-memory": (
        300,
        {
            "KB": 30,
            "PP": 20,
            "SM": 20,
            "UM": 184,
            "WM": 16,
            "OM": 30,
        },
    ),
    "task3-guardrails": (
        75,
        {"KB": 8, "PP": 47, "SM": 4, "WM": 5, "OM": 11},
    ),
    "task3-healthcare-info-request": (
        75,
        {"KB": 5, "PP": 42, "SM": 8, "WM": 7, "OM": 13},
    ),
}


def test_korean_study_corpus_has_expected_counts_and_purposes() -> None:
    corpus = load_study_fixture_corpus(language="ko")

    assert len(corpus.records) == EXPECTED_CORPUS_COUNT
    assert set(corpus.by_name()) == set(EXPECTED_DATASETS)
    for name, (expected_count, expected_purposes) in EXPECTED_DATASETS.items():
        dataset = corpus.by_name()[name]
        assert len(dataset.records) == expected_count
        assert Counter(record.purpose for record in dataset.records) == (
            expected_purposes
        )

    assert len({record.canonical_locator for record in corpus.records}) == (
        EXPECTED_CORPUS_COUNT
    )


def test_loader_preserves_content_and_normalizes_available_metadata() -> None:
    corpus = load_study_fixture_corpus(language="ko").by_name()

    update = corpus["task1-construction-updates"].records[0]
    assert update.fixture_id == "T1-U-001"
    assert update.locator == "construction-updates/building-access/01"
    assert update.canonical_locator == update.locator
    assert update.purpose == "KB"
    assert update.audiences == (AudienceRole.ALL,)
    assert update.verified is None
    assert update.content == "공사기간 3층 후문은 일반 통행에 사용할 수 없다."

    advisor = corpus["task2-advisor1"].records[0]
    assert advisor.fixture_id == "T2-L-001"
    assert advisor.locator == "structure/problem"
    assert advisor.canonical_locator == "advisor1/structure/problem"
    assert advisor.purpose == "PP"

    personal = corpus["task3-personal-memory"].records[0]
    assert personal.fixture_id is None
    assert personal.identity_key == "personal-memory/2024-01/01"
    assert personal.canonical_locator == "personal-memory/2024-01/01"
    assert personal.purpose == "KB"


def test_english_block_labels_verified_and_compound_audience_are_supported(
    tmp_path: Path,
) -> None:
    language_root = tmp_path / "en"
    language_root.mkdir()
    (language_root / "sample-en.md").write_text(
        "\n".join(
            [
                "# Sample",
                "",
                "### T1-U-001",
                "",
                "- Memory Location: ctx/item",
                "- Content: Keep the source meaning.",
                (
                    "- Audience: Visitors · "
                    "Construction/Facilities Personnel"
                ),
                "- Verified: true",
            ]
        ),
        encoding="utf-8",
    )
    (language_root / "sample-purpose-en.tsv").write_text(
        "fixture_id\tMemory Location\tPurpose\n"
        "T1-U-001\tctx/item\tPP\n",
        encoding="utf-8",
    )
    spec = StudyFixtureSpec(
        name="sample",
        task=1,
        file_stem="sample",
        expected_count=1,
        syntax=FixtureSyntax.TASK1_BLOCK,
        context_name="ctx",
        purpose_sidecar_stem="sample-purpose",
        purpose_sidecar_count=1,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T1-U-",
        fixture_ids_required=True,
    )

    record = load_study_fixture(spec, language="en", root=tmp_path).records[0]

    assert record.content == "Keep the source meaning."
    assert record.purpose == "PP"
    assert record.audiences == (
        AudienceRole.VISITOR,
        AudienceRole.CONSTRUCTION_FACILITIES,
    )
    assert record.verified is True


def test_loader_rejects_duplicate_canonical_locators(tmp_path: Path) -> None:
    language_root = tmp_path / "ko"
    language_root.mkdir()
    (language_root / "sample-ko.md").write_text(
        "\n".join(
            [
                "### T1-U-001",
                "- Memory 위치: ctx/same",
                "- 본문: 첫째.",
                "- 열람 대상: 전체",
                "### T1-U-002",
                "- Memory 위치: ctx/same",
                "- 본문: 둘째.",
                "- 열람 대상: 전체",
            ]
        ),
        encoding="utf-8",
    )
    (language_root / "sample-purpose-ko.tsv").write_text(
        "fixture_id\tMemory 위치\t목적 코드\n"
        "T1-U-001\tctx/same\tKB\n"
        "T1-U-002\tctx/same\tKB\n",
        encoding="utf-8",
    )
    spec = StudyFixtureSpec(
        name="sample",
        task=1,
        file_stem="sample",
        expected_count=2,
        syntax=FixtureSyntax.TASK1_BLOCK,
        context_name="ctx",
        purpose_sidecar_stem="sample-purpose",
        purpose_sidecar_count=2,
        purpose_sidecar_key=PurposeSidecarKey.FIXTURE_ID,
        sidecar_prefix="T1-U-",
        fixture_ids_required=True,
    )

    with pytest.raises(StudyFixtureError, match="Duplicate canonical Memory"):
        load_study_fixture(spec, language="ko", root=tmp_path)


def test_translation_pairing_exposes_one_uid_key_and_rejects_drift() -> None:
    korean = load_study_fixture("task3-guardrails", language="ko")
    english = FixtureDataset(
        spec=korean.spec,
        language="en",
        records=tuple(
            replace(
                record,
                language="en",
                content=f"EN: {record.content}",
            )
            for record in korean.records
        ),
    )

    pairs = pair_fixture_translations(english, korean)

    assert len(pairs) == 75
    assert pairs[0].uid_key == (
        "task3-guardrails:guardrails/purpose-and-scope/01"
    )
    assert pairs[0].canonical.content.startswith("EN: ")
    assert pairs[0].translation.content.startswith("사용자가")

    drifted_records = list(korean.records)
    drifted_records[0] = replace(drifted_records[0], purpose="KB")
    drifted = FixtureDataset(
        spec=korean.spec,
        language="ko-drift",
        records=tuple(drifted_records),
    )
    with pytest.raises(StudyFixtureError, match="Purpose drift"):
        pair_fixture_translations(english, drifted)
