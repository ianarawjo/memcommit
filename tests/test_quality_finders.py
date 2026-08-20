"""Contracts for read-only duplicate, ambiguity, and conflict finders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import MemoryRef, QueryContextRef
from memcommit.findings import (
    FindingsError,
    collect_direct_memories,
    enumerate_pairs,
    find_ambiguities,
    find_conflicts,
    find_duplicates,
)
from memcommit.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "QUALITY FIND PAYLOAD:\n"
FIXTURE_DIR = (
    Path(__file__).parents[1] / "memcommit" / "eval" / "fixtures"
)


class PayloadProvider:
    """Return structured findings chosen from one complete operation payload."""

    def __init__(self, responder):
        self.responder = responder
        self.calls: list[tuple[str, str, dict[str, object] | None, dict]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.calls.append((prompt, operation, output_schema, payload))
        return json.dumps(self.responder(operation, payload))


class ForbiddenProvider:
    def __call__(self):
        raise AssertionError("provider should not be connected")


def _pair_id_for_contents(payload: dict, left: str, right: str) -> str:
    contents = {
        memory["candidate_id"]: memory["content"]
        for memory in payload["memories"]
    }
    for pair in payload["pairs"]:
        pair_contents = {
            contents[pair["left_id"]],
            contents[pair["right_id"]],
        }
        if pair_contents == {left, right}:
            return pair["pair_id"]
    raise AssertionError(f"pair not found: {left!r}, {right!r}")


def _candidate_id_for_content(payload: dict, content: str) -> str:
    for memory in payload["memories"]:
        if memory["content"] == content:
            return memory["candidate_id"]
    raise AssertionError(f"candidate not found: {content!r}")


def test_direct_collection_excludes_refs_children_and_query_only_items():
    source = ops.init("source")
    referenced = ops.add(source, "referenced fact")
    child = ops.init("child")
    ops.add(child, "nested fact")
    root = ops.init("root")
    first = ops.add(root, "first direct fact")
    root.add(
        MemoryRef(
            uid="memory-ref",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=referenced.uid,
            target=referenced,
        )
    )
    root.add(
        QueryContextRef(
            uid="query-ref",
            name="restricted-policy",
            target_source_uid="secret-source",
            provider="codex_chatgpt",
        )
    )
    root.add(child)
    second = ops.add(root, "second direct fact")

    candidates = collect_direct_memories(root)

    assert [candidate.memory for candidate in candidates] == [first, second]
    assert [candidate.candidate_id for candidate in candidates] == [
        "m000001",
        "m000002",
    ]


def test_pair_enumeration_is_complete_unordered_and_canonical():
    ctx = ops.init("pairs")
    for content in ["A", "B", "C", "D"]:
        ops.add(ctx, content)

    pairs = enumerate_pairs(collect_direct_memories(ctx))

    assert len(pairs) == 6
    assert [
        (
            pair.pair_id,
            pair.left.memory.content,
            pair.right.memory.content,
        )
        for pair in pairs
    ] == [
        ("p000001", "A", "B"),
        ("p000002", "A", "C"),
        ("p000003", "A", "D"),
        ("p000004", "B", "C"),
        ("p000005", "B", "D"),
        ("p000006", "C", "D"),
    ]


def test_find_duplicates_scans_representatives_without_pair_targets(
    monkeypatch,
):
    ctx = ops.init("duplicates")
    for content in [
        "Same content.",
        "Same content.",
        "  Surface   equivalent. ",
        "Surface equivalent.",
        "The garage is closed.",
        "The parking garage is unavailable.",
    ]:
        ops.add(ctx, content)

    def respond(operation, payload):
        assert operation == "find_duplicates"
        return {
            "findings": [
                {
                    "candidate_ids": [
                        _candidate_id_for_content(
                            payload,
                            "The parking garage is unavailable.",
                        ),
                        _candidate_id_for_content(
                            payload,
                            "The garage is closed.",
                        ),
                    ],
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "Both state the same garage closure.",
                }
            ]
        }

    monkeypatch.setattr(
        "memcommit.findings.enumerate_pairs",
        lambda candidates: pytest.fail(
            "duplicate discovery must not enumerate pair targets"
        ),
    )
    provider = PayloadProvider(respond)
    report = find_duplicates(ctx, lambda: provider)

    assert report.memory_count == 6
    assert [finding.relation for finding in report.findings] == [
        "SURFACE_EQUIVALENT",
        "SEMANTIC_EQUIVALENT",
    ]
    assert (
        report.findings[-1].left.content,
        report.findings[-1].right.content,
    ) == (
        "The garage is closed.",
        "The parking garage is unavailable.",
    )
    assert len(provider.calls) == 1
    _, operation, schema, payload = provider.calls[0]
    assert operation == "find_duplicates"
    assert payload["context"]["direct_memory_count"] == 6
    assert len(payload["memories"]) == 4
    assert "pairs" not in payload
    assert "unresolved_pairs" not in payload
    item_schema = schema["properties"]["findings"]["items"]
    assert "candidate_ids" in item_schema["properties"]
    assert "pair_id" not in item_schema["properties"]
    assert "uniqueItems" not in item_schema["properties"]["candidate_ids"]
    assert schema["properties"]["findings"]["maxItems"] == 2


def test_find_duplicates_keeps_each_stored_memory_indivisible():
    ctx = ops.init("partial-overlap")
    ops.add(ctx, "abc")
    ops.add(ctx, "bcd")
    provider = PayloadProvider(
        lambda operation, payload: {"findings": []}
    )

    report = find_duplicates(ctx, lambda: provider)

    assert report.findings == ()
    assert len(provider.calls) == 1
    prompt, _operation, schema, payload = provider.calls[0]
    assert [memory["content"] for memory in payload["memories"]] == [
        "abc",
        "bcd",
    ]
    assert "complete stored content as one indivisible judgment unit" in prompt
    assert "Atomize must first" in prompt
    assert schema["properties"]["findings"]["items"]["properties"][
        "relation"
    ]["enum"] == ["SEMANTIC_EQUIVALENT"]


def test_find_duplicates_avoids_provider_for_one_mechanical_component():
    ctx = ops.init("duplicates")
    ops.add(ctx, "same")
    ops.add(ctx, "same")

    report = find_duplicates(ctx, ForbiddenProvider())

    assert report.findings == ()


def test_mechanical_duplicate_forest_is_linear_and_preserves_relation_tiers():
    ctx = ops.init("mechanical-forest")
    for content in ["same", "same", " same ", " same "]:
        ops.add(ctx, content)

    report = find_duplicates(ctx, ForbiddenProvider())

    assert len(report.findings) == 1
    assert [
        (
            finding.left.content,
            finding.right.content,
            finding.relation,
        )
        for finding in report.findings
    ] == [
        ("same", " same ", "SURFACE_EQUIVALENT"),
    ]


def test_surface_equivalence_collapses_only_horizontal_whitespace():
    horizontal = ops.init("horizontal")
    ops.add(horizontal, "  Access\tcard\u00a0required. ")
    ops.add(horizontal, "Access card required.")
    horizontal_report = find_duplicates(horizontal, ForbiddenProvider())

    assert [
        finding.relation
        for finding in horizontal_report.findings
    ] == ["SURFACE_EQUIVALENT"]

    for separator in ["\v", "\f", "\x85", "\u2028", "\u2029"]:
        vertical = ops.init(f"vertical-{ord(separator)}")
        ops.add(vertical, f"Access{separator}card required.")
        ops.add(vertical, "Access card required.")
        provider = PayloadProvider(
            lambda operation, payload: {"findings": []}
        )

        report = find_duplicates(vertical, lambda: provider)

        assert report.findings == ()
        assert len(provider.calls) == 1


def test_find_ambiguities_calls_provider_once_and_restores_context_order():
    ctx = ops.init("ambiguities")
    first = ops.add(ctx, "Ask the coordinator.")
    ops.add(ctx, "The main entrance closes at 5 p.m.")
    third = ops.add(ctx, "It's 216.")

    def respond(operation, payload):
        assert operation == "find_ambiguities"
        ids = {
            memory["content"]: memory["candidate_id"]
            for memory in payload["memories"]
        }
        return {
            "findings": [
                {
                    "candidate_id": ids["It's 216."],
                    "interpretation": "COMPETING",
                    "clarification": "REQUIRED",
                    "ordinary_readings": [
                        "Room number 216.",
                        "Price 216.",
                    ],
                    "reason": "The referent changes the booking action.",
                    "question": "Does 216 mean the room or the price?",
                },
                {
                    "candidate_id": ids["Ask the coordinator."],
                    "interpretation": "SINGLE",
                    "clarification": "REQUIRED",
                    "ordinary_readings": [
                        "Contact the responsible coordinator.",
                    ],
                    "reason": "No contact route is provided.",
                    "question": "How can the coordinator be contacted?",
                },
            ]
        }

    provider = PayloadProvider(respond)
    report = find_ambiguities(ctx, lambda: provider)

    assert report.memory_count == 3
    assert [finding.memory for finding in report.findings] == [first, third]
    assert len(provider.calls) == 1
    assert provider.calls[0][1] == "find_ambiguities"
    assert len(provider.calls[0][3]["memories"]) == 3
    prompt = provider.calls[0][0]
    assert (
        "Write every ordinary reading, reason, and question in English"
        in prompt
    )
    assert "clean SINGLE/NONE and must be omitted" in prompt
    assert "after that time a card is required" in prompt
    assert "Never expose candidate IDs" in prompt
    assert "what cannot be determined reliably" in prompt
    assert "what remains possible" in prompt


def test_find_conflicts_sends_every_pair_once_and_sorts_findings():
    ctx = ops.init("conflicts")
    first = ops.add(ctx, "The main entrance closes after 5 p.m.")
    second = ops.add(ctx, "Staff may use the main entrance after 5 p.m.")
    third = ops.add(ctx, "The separate staff entrance stays open.")

    def respond(operation, payload):
        assert operation == "find_conflicts"
        yes_pair = _pair_id_for_contents(
            payload,
            first.content,
            second.content,
        )
        may_pair = _pair_id_for_contents(
            payload,
            second.content,
            third.content,
        )
        return {
            "findings": [
                {
                    "pair_id": may_pair,
                    "conflict": "MAY",
                    "scope_dimensions": ["PLACE"],
                    "reason": "The named entrance may or may not be the same.",
                    "question": "Do both Memories concern the staff entrance?",
                },
                {
                    "pair_id": yes_pair,
                    "conflict": "YES",
                    "scope_dimensions": [],
                    "reason": "The same entrance is both closed and permitted.",
                    "question": "",
                },
            ]
        }

    provider = PayloadProvider(respond)
    report = find_conflicts(ctx, lambda: provider)

    assert report.memory_count == 3
    assert report.pair_count == 3
    assert [(finding.left, finding.right) for finding in report.findings] == [
        (first, second),
        (second, third),
    ]
    assert [finding.conflict for finding in report.findings] == ["YES", "MAY"]
    assert len(provider.calls) == 1
    payload = provider.calls[0][3]
    assert [pair["pair_id"] for pair in payload["pairs"]] == [
        "p000001",
        "p000002",
        "p000003",
    ]


def test_aggregate_finder_payload_keeps_original_context_for_each_memory():
    aggregate = ops.init("quality-find-frame")
    left = ops.add(aggregate, "The entrance opens at 8:00.")
    right = ops.add(aggregate, "The entrance stays closed until 9:00.")
    provider = PayloadProvider(lambda operation, payload: {"findings": []})

    report = find_conflicts(
        aggregate,
        lambda: provider,
        context_name_by_uid={
            left.uid: "schedule/public",
            right.uid: "schedule/staff",
        },
    )

    assert report.pair_count == 1
    assert [
        (memory["content"], memory["context_name"])
        for memory in provider.calls[0][3]["memories"]
    ] == [
        (left.content, "schedule/public"),
        (right.content, "schedule/staff"),
    ]
    assert "including cross-Context pairs" in provider.calls[0][0]


def test_empty_and_singleton_inputs_do_not_connect_provider():
    empty = ops.init("empty")
    singleton = ops.init("singleton")
    ops.add(singleton, "only one")

    assert find_ambiguities(empty, ForbiddenProvider()).findings == ()
    assert find_duplicates(empty, ForbiddenProvider()).findings == ()
    assert find_conflicts(empty, ForbiddenProvider()).findings == ()
    assert find_duplicates(singleton, ForbiddenProvider()).findings == ()
    assert find_conflicts(singleton, ForbiddenProvider()).findings == ()


@pytest.mark.parametrize(
    ("finder_name", "raw"),
    [
        ("ambiguities", None),
        ("ambiguities", "not json"),
        ("ambiguities", '{"findings": [], "findings": []}'),
        ("ambiguities", json.dumps({"wrong": []})),
        (
            "ambiguities",
            json.dumps(
                {
                    "findings": [
                        {
                            "candidate_id": "unknown",
                            "interpretation": "COMPETING",
                            "clarification": "REQUIRED",
                            "ordinary_readings": ["one", "two"],
                            "reason": "reason",
                            "question": "question?",
                        }
                    ]
                }
            ),
        ),
        (
            "conflicts",
            json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": "unknown",
                            "conflict": "YES",
                            "scope_dimensions": [],
                            "reason": "reason",
                            "question": "",
                        }
                    ]
                }
            ),
        ),
        (
            "duplicates",
            json.dumps(
                {
                    "findings": [
                        {
                            "candidate_ids": ["m000001", "m000002"],
                            "relation": "OVERLAP",
                            "reason": "not a duplicate",
                        }
                    ]
                }
            ),
        ),
    ],
)
def test_finders_reject_invalid_or_unknown_structured_output(finder_name, raw):
    ctx = ops.init("invalid")
    ops.add(ctx, "first")
    ops.add(ctx, "second")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return raw

    finder = {
        "ambiguities": find_ambiguities,
        "conflicts": find_conflicts,
        "duplicates": find_duplicates,
    }[finder_name]
    with pytest.raises(FindingsError):
        finder(ctx, lambda: Provider())


def test_find_conflicts_rejects_duplicate_pair_findings():
    ctx = ops.init("duplicate-output")
    ops.add(ctx, "first")
    ops.add(ctx, "second")

    def respond(operation, payload):
        finding = {
            "pair_id": payload["pairs"][0]["pair_id"],
            "conflict": "YES",
            "scope_dimensions": [],
            "reason": "reason",
            "question": "",
        }
        return {"findings": [finding, finding]}

    with pytest.raises(FindingsError, match="duplicate"):
        find_conflicts(ctx, lambda: PayloadProvider(respond))


@pytest.mark.parametrize(
    "groups",
    [
        [["m000001", "unknown"]],
        [["m000001", "m000001"]],
        [
            ["m000001", "m000002"],
            ["m000002", "m000003"],
        ],
    ],
)
def test_find_duplicates_rejects_invalid_or_overlapping_groups(groups):
    ctx = ops.init("invalid-duplicate-groups")
    for content in ["first", "second", "third"]:
        ops.add(ctx, content)

    def respond(operation, payload):
        return {
            "findings": [
                {
                    "candidate_ids": candidate_ids,
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "same claim",
                }
                for candidate_ids in groups
            ]
        }

    with pytest.raises(FindingsError, match="duplicate group"):
        find_duplicates(ctx, lambda: PayloadProvider(respond))


def test_find_duplicates_canonicalizes_semantic_group_and_emits_linear_evidence():
    ctx = ops.init("semantic-group")
    memories = [
        ops.add(ctx, content)
        for content in ["first wording", "second wording", "third wording"]
    ]

    def respond(operation, payload):
        ids = [
            _candidate_id_for_content(payload, memory.content)
            for memory in memories
        ]
        return {
            "findings": [
                {
                    "candidate_ids": list(reversed(ids)),
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "All three are mutually substitutable.",
                }
            ]
        }

    report = find_duplicates(ctx, lambda: PayloadProvider(respond))

    assert [
        (finding.left, finding.right)
        for finding in report.findings
    ] == [
        (memories[0], memories[1]),
        (memories[0], memories[2]),
    ]


def test_cli_finders_are_read_only_and_each_use_one_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("quality")
    ops.add(ctx, "The entrance closes at 5 p.m.")
    ops.add(ctx, "Staff may enter after 5 p.m.")
    store.save(ctx)
    store.set_current(ctx.name)
    context_path = store._context_file(ctx.name)
    context_before = context_path.read_bytes()
    checkpoints_before = store.list_checkpoints(ctx.name)

    provider = PayloadProvider(
        lambda operation, payload: {"findings": []}
    )
    for module_name in [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]:
        monkeypatch.setattr(
            f"memcommit.commands.{module_name}."
            "connect_codex_chatgpt_provider",
            lambda: provider,
        )

    duplicate_result = runner.invoke(app, ["dedun"])
    ambiguity_result = runner.invoke(app, ["find-ambiguities"])
    conflict_result = runner.invoke(app, ["find-conflicts"])

    assert duplicate_result.exit_code == 0
    assert ambiguity_result.exit_code == 0
    assert conflict_result.exit_code == 0
    assert "pair" not in duplicate_result.output
    assert "2 direct memories, 0 findings" in duplicate_result.output
    assert "no ambiguity findings" in ambiguity_result.output
    assert "no conflict findings" in conflict_result.output
    assert [call[1] for call in provider.calls] == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    assert context_path.read_bytes() == context_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before
    assert store.current_context_name() == ctx.name


def test_cli_explicit_context_does_not_switch_current(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    active = ops.init("active")
    target = ops.init("target")
    ops.add(target, "same")
    ops.add(target, "same")
    store.save(active)
    store.save(target)
    store.set_current(active.name)
    monkeypatch.setattr(
        "memcommit.commands.find_duplicates."
        "connect_codex_chatgpt_provider",
        lambda: pytest.fail("mechanical duplicates need no provider"),
    )

    result = runner.invoke(
        app,
        ["dedun", "--context", target.name],
    )

    assert result.exit_code == 0
    assert "Context: target" in result.output
    assert "0 findings" in result.output
    assert "EXACT" not in result.output
    assert store.current_context_name() == active.name


def test_cli_direct_scope_does_not_open_memory_ref_or_embedded_context_files(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    referenced = ops.add(source, "referenced content")
    child = ops.init("child")
    ops.add(child, "nested content")
    root = ops.init("root")
    ops.add(root, "first direct")
    root.add(
        MemoryRef(
            uid="memory-ref",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=referenced.uid,
            target=referenced,
        )
    )
    root.add(child)
    ops.add(root, "second direct")
    for context in [source, child, root]:
        store.save(context)
    store.set_current(root.name)

    # A direct-only scan must remain usable even when out-of-scope targets are
    # unreadable. Query-only sources are never opened by either load path.
    store._context_file(source.name).write_text("{invalid")
    store._context_file(child.name).write_text("{invalid")
    provider = PayloadProvider(
        lambda operation, payload: {"findings": []}
    )
    for module_name in [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]:
        monkeypatch.setattr(
            f"memcommit.commands.{module_name}."
            "connect_codex_chatgpt_provider",
            lambda: provider,
        )

    results = [
        runner.invoke(app, [command])
        for command in [
            "dedun",
            "find-ambiguities",
            "find-conflicts",
        ]
    ]

    assert [result.exit_code for result in results] == [0, 0, 0]
    assert all("2 direct memories" in result.output for result in results)
    assert [call[1] for call in provider.calls] == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    assert all(
        [
            item["content"]
            for item in call[3]["memories"]
        ] == ["first direct", "second direct"]
        for call in provider.calls
    )


def test_conflicts_enumerates_all_pairs_without_count_gate():
    ctx = ops.init("large")
    for index in range(4):
        ops.add(ctx, str(index))
    provider = PayloadProvider(lambda _operation, _payload: {"findings": []})

    report = find_conflicts(ctx, lambda: provider)

    assert report.findings == ()
    assert len(provider.calls[0][3]["pairs"]) == 6


def test_duplicate_scan_does_not_allocate_pair_records(monkeypatch):
    ctx = ops.init("linear-duplicates")
    for index in range(4):
        ops.add(ctx, str(index))
    monkeypatch.setattr(
        "memcommit.findings.MemoryPair",
        lambda *args, **kwargs: pytest.fail(
            "duplicate discovery allocated a pair record"
        ),
    )
    provider = PayloadProvider(
        lambda operation, payload: {"findings": []}
    )

    report = find_duplicates(ctx, lambda: provider)

    assert report.memory_count == 4
    assert report.findings == ()
    assert len(provider.calls) == 1
    assert "pairs" not in provider.calls[0][3]


def test_enumerate_pairs_has_no_fixed_pair_count_gate():
    ctx = ops.init("large")
    for index in range(4):
        ops.add(ctx, str(index))
    candidates = collect_direct_memories(ctx)
    pairs = enumerate_pairs(candidates)

    assert len(pairs) == 6
    assert [pair.pair_id for pair in pairs] == [
        "p000001",
        "p000002",
        "p000003",
        "p000004",
        "p000005",
        "p000006",
    ]


def test_ambiguity_fixture_covers_the_complete_three_by_three_matrix():
    data = json.loads((FIXTURE_DIR / "ambiguity.json").read_text())
    combinations = {
        (
            case["expected"]["interpretation"],
            case["expected"]["clarification"],
        )
        for case in data["cases"]
    }

    assert data["schema_version"] == 1
    assert any(
        case["id"] == "single-none-context-resolved-time"
        and case["expected"]["clarification"] == "NONE"
        for case in data["cases"]
    )
    assert combinations == {
        (interpretation, clarification)
        for interpretation in ["SINGLE", "DOMINANT", "COMPETING"]
        for clarification in ["NONE", "HELPFUL", "REQUIRED"]
    }
    assert all(
        isinstance(case["expected"]["question"], str)
        for case in data["cases"]
    )


def test_conflict_and_duplicate_fixtures_cover_all_calibration_boundaries():
    conflict = json.loads((FIXTURE_DIR / "conflict.json").read_text())
    duplicates = json.loads((FIXTURE_DIR / "duplicates.json").read_text())

    assert {
        case["expected"]["conflict"]
        for case in conflict["cases"]
    } == {"YES", "MAY", "NO"}
    assert all(
        set(case["expected"]["scope_dimensions"]) <= {"PLACE"}
        for case in conflict["cases"]
    )
    assert {
        case["expected"]["relation"]
        for case in duplicates["cases"]
    } == {
        "EXACT",
        "SURFACE_EQUIVALENT",
        "SEMANTIC_EQUIVALENT",
        "OVERLAP",
        "UNKNOWN",
        "DISTINCT",
    }
