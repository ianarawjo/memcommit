"""Contract checks for the human-reviewed atomize golden corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "memcommit"
    / "eval"
    / "fixtures"
    / "atomize.json"
)

CLASSIFICATIONS = {
    "ATOMIC",
    "COMPOSITE",
    "UNCERTAIN",
    "NON_PROPOSITIONAL",
}
RULE_CODES = {
    "A01_ONE_FOCUS",
    "A02_SCOPE_ATTACHED",
    "A03_RELATION_PRESERVED",
    "A04_SOURCE_GROUNDED",
    "A05_MINIMAL_EXPANSION",
    "A06_NO_HIDDEN_CONTEXT",
    "A07_RETAIN_NON_CLAIMS",
    "A08_PRESERVE_OCCURRENCES",
    "A09_SIZE_IS_LINT",
    "A10_STAGE_BOUNDARY",
}
SPEECH_ACTS = {
    "ASSERTION",
    "DIRECTIVE",
    "QUESTION",
}
SCOPE_KEYS = {
    "subject",
    "audience",
    "place",
    "time",
    "modality",
    "condition",
    "exception",
    "cause",
}


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_fixture() -> dict:
    return json.loads(
        FIXTURE_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


def test_atomize_fixture_has_a_consistent_reviewable_schema() -> None:
    fixture = load_fixture()

    assert set(fixture) == {
        "command",
        "schema_version",
        "ruleset_version",
        "profile",
        "description",
        "cases",
    }
    assert fixture["command"] == "atomize"
    assert fixture["schema_version"] == 1
    assert fixture["ruleset_version"] == "atomize-v2-reviewed-frame-draft"
    assert fixture["cases"]

    profile = fixture["profile"]
    assert set(profile) == {
        "id",
        "version",
        "locale",
        "segmenter_version",
        "size_review_chars",
        "size_review_segments",
        "fingerprint",
    }
    profile_payload = {
        key: value
        for key, value in profile.items()
        if key != "fingerprint"
    }
    canonical_profile = json.dumps(
        profile_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    expected_fingerprint = hashlib.sha256(
        canonical_profile.encode("utf-8")
    ).hexdigest()
    assert profile["fingerprint"] == f"sha256:{expected_fingerprint}"

    case_ids: set[str] = set()
    for case in fixture["cases"]:
        assert set(case) == {
            "id",
            "description",
            "source",
            "declared_frames",
            "expected",
            "known_wrong",
        }
        assert case["id"] not in case_ids
        case_ids.add(case["id"])

        assert case["description"].strip()
        assert case["source"].strip()

        frame_ids: set[str] = set()
        for frame in case["declared_frames"]:
            assert set(frame) == {
                "id",
                "content",
                "fingerprint",
            }
            assert frame["id"] not in frame_ids
            frame_ids.add(frame["id"])
            assert frame["content"].strip()
            frame_digest = hashlib.sha256(
                frame["content"].encode("utf-8")
            ).hexdigest()
            assert frame["fingerprint"] == f"sha256:{frame_digest}"

        expected = case["expected"]
        assert set(expected) == {
            "classification",
            "result",
            "qa",
            "reason_codes",
            "lint",
        }
        classification = expected["classification"]
        assert classification in CLASSIFICATIONS
        assert expected["reason_codes"]
        assert set(expected["reason_codes"]) <= RULE_CODES
        assert isinstance(expected["lint"], list)

        result = expected["result"]
        assert isinstance(result, list)
        assert all(isinstance(child, str) and child.strip() for child in result)
        if classification == "COMPOSITE":
            assert len(result) >= 2
        else:
            assert result == [case["source"]]

        qa = expected["qa"]
        assert isinstance(qa, list)
        occurrence_ids: set[str] = set()
        mapped_children: set[int] = set()
        for check in qa:
            assert set(check) == {
                "occurrence_id",
                "source_spans",
                "speech_act",
                "focal_predicate",
                "scope",
                "frame_ids",
                "child_index",
                "question",
                "answer",
            }
            assert check["occurrence_id"] not in occurrence_ids
            occurrence_ids.add(check["occurrence_id"])
            assert check["source_spans"]
            assert all(
                isinstance(span, str)
                and span.strip()
                and span in case["source"]
                for span in check["source_spans"]
            )
            assert check["speech_act"] in SPEECH_ACTS
            assert check["focal_predicate"].strip()
            assert set(check["scope"]) == SCOPE_KEYS
            assert all(
                isinstance(values, list)
                and all(
                    isinstance(value, str) and value.strip()
                    for value in values
                )
                for values in check["scope"].values()
            )
            assert isinstance(check["frame_ids"], list)
            assert all(
                isinstance(frame_id, str) and frame_id.strip()
                for frame_id in check["frame_ids"]
            )
            assert set(check["frame_ids"]) <= frame_ids
            assert 0 <= check["child_index"] < len(result)
            mapped_children.add(check["child_index"])
            assert check["question"].strip()
            assert check["answer"].strip()

        if classification in {"ATOMIC", "COMPOSITE"}:
            assert mapped_children == set(range(len(result)))
        else:
            assert qa == []

        assert case["known_wrong"]
        for wrong in case["known_wrong"]:
            assert set(wrong) == {
                "result",
                "violates",
                "reason",
            }
            assert wrong["result"]
            assert all(
                isinstance(child, str) and child.strip()
                for child in wrong["result"]
            )
            assert wrong["violates"]
            assert set(wrong["violates"]) <= RULE_CODES
            assert wrong["reason"].strip()


def test_atomize_fixture_guards_length_and_stage_boundaries() -> None:
    cases = {case["id"]: case for case in load_fixture()["cases"]}

    long_atomic = cases["long-but-atomic-conditional"]
    assert len(long_atomic["source"]) > 80
    assert long_atomic["expected"]["classification"] == "ATOMIC"
    assert "SIZE_REVIEW" in long_atomic["expected"]["lint"]

    short_composite = cases["short-but-composite"]
    assert len(short_composite["source"]) < 80
    assert short_composite["expected"]["classification"] == "COMPOSITE"

    duplicate = cases["duplicate-occurrences-preserved"]
    assert duplicate["expected"]["classification"] == "COMPOSITE"
    assert duplicate["expected"]["result"][0] == duplicate["expected"]["result"][1]
    assert "A08_PRESERVE_OCCURRENCES" in duplicate["expected"]["reason_codes"]

    deictic = cases["undeclared-deictic-frame"]
    assert deictic["expected"]["classification"] == "UNCERTAIN"
    assert "A06_NO_HIDDEN_CONTEXT" in deictic["expected"]["reason_codes"]

    framed = cases["declared-frame-grounds-shared-scope"]
    assert framed["expected"]["classification"] == "COMPOSITE"
    assert framed["declared_frames"]
    assert all(
        check["frame_ids"] == ["construction-period"]
        for check in framed["expected"]["qa"]
    )
