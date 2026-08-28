from __future__ import annotations

from memcommit.study_scenarios.legacy.authoring.sheet import (
    build_study_workbook_spec,
)


def test_bilingual_workbook_spec_pairs_every_fixture() -> None:
    spec = build_study_workbook_spec()

    assert spec.schema_version == 1
    assert spec.canonical_language == "en"
    assert spec.translation_language == "ko"
    assert (spec.ordinary_count, spec.query_only_count, spec.total_count) == (
        1_081,
        228,
        1_309,
    )
    assert len(spec.sheets) == 26

    by_dataset_language = {
        (sheet.dataset, sheet.language): sheet for sheet in spec.sheets
    }
    assert len(by_dataset_language) == 26
    for dataset in {sheet.dataset for sheet in spec.sheets}:
        korean = by_dataset_language[(dataset, "ko")]
        english = by_dataset_language[(dataset, "en")]
        assert len(korean.rows) == len(english.rows)
        assert [column.key for column in korean.columns] == [
            column.key for column in english.columns
        ]


def test_workbook_spec_preserves_review_and_operation_metadata() -> None:
    spec = build_study_workbook_spec()
    sheets = {(sheet.dataset, sheet.language): sheet for sheet in spec.sheets}

    task1 = sheets[("task1-construction-updates", "ko")]
    keys = [column.key for column in task1.columns]
    assert keys[:10] == [
        "verified",
        "fixture_id",
        "location",
        "all",
        "visitor",
        "student",
        "staff",
        "operations",
        "purpose",
        "content",
    ]
    assert keys[10:] == [
        "target_location",
        "target_memory",
        "operation",
        "update_detail",
        "before",
        "after",
        "source",
    ]
    # T1-U-009 intentionally updates multiple baseline Memories but remains
    # one source Memory row in the review sheet.
    fixture_index = keys.index("fixture_id")
    action_index = keys.index("target_memory")
    reservation = next(
        row for row in task1.rows if row[fixture_index] == "T1-U-009"
    )
    assert "\n" in reservation[action_index]

    advisor = sheets[("task2-advisor1", "en")]
    advisor_keys = [column.key for column in advisor.columns]
    assert "relation" in advisor_keys
    assert "counterparts" in advisor_keys
    relation_index = advisor_keys.index("relation")
    assert {row[relation_index] for row in advisor.rows} >= {
        "Conflict",
        "Compatible Complement",
        "Near Duplicate",
    }

    guidelines = sheets[("task2-proposal-guidelines", "en")]
    assert "relation" not in [column.key for column in guidelines.columns]


def test_workbook_spec_uses_checkboxes_only_for_designer_flags() -> None:
    spec = build_study_workbook_spec()

    for sheet in spec.sheets:
        checkbox_keys = {
            column.key for column in sheet.columns if column.checkbox
        }
        assert "verified" in checkbox_keys
        if sheet.dataset.startswith("task1-"):
            assert checkbox_keys == {
                "verified",
                "all",
                "visitor",
                "student",
                "staff",
                "operations",
            }
        else:
            assert checkbox_keys == {"verified"}
